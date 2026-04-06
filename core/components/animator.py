import json
import os
from core.ecs import Component
from core.animation import AnimationController, AnimationClip
from core.logger import get_logger

_animator_logger = get_logger("components")


class AnimatorComponent(Component):
    def __init__(self, controller_path: str = None, play_on_start: bool = True, speed: float = 1.0):
        self.entity = None
        self.controller_path = controller_path
        self.play_on_start = play_on_start
        self.speed = speed
        
        self.controller: AnimationController | None = None
        self.current_state: str | None = None
        self.current_clip: AnimationClip | None = None
        
        self.current_frame_index = 0
        self._frame_timer = 0.0
        self.is_playing = False
        self.is_paused = False
        self._trigger_events = set()
        self._controller_file_path = ""
        self._controller_mtime = None
        
        if self.controller_path:
            self.load_controller(self.controller_path)

    def _resolve_controller_path(self, path: str):
        if not path:
            return ""
        return self._resolve_path_variants(path)

    def _resolve_path_variants(self, path: str, base_dir: str | None = None) -> str:
        if not path:
            return ""

        normalized = os.path.normpath(path)
        candidates = []

        if os.path.isabs(normalized):
            candidates.append(normalized)
        else:
            candidates.append(normalized)
            if base_dir:
                candidates.append(os.path.normpath(os.path.join(base_dir, normalized)))
            project_root = os.environ.get("AXISPY_PROJECT_PATH", "").strip()
            if project_root:
                candidates.append(os.path.normpath(os.path.join(project_root, normalized)))
            candidates.append(os.path.normpath(os.path.join(os.getcwd(), normalized)))

            parts = [part for part in normalized.replace("\\", "/").split("/") if part not in ("", ".")]
            if project_root and parts:
                for i in range(1, len(parts)):
                    candidates.append(os.path.normpath(os.path.join(project_root, *parts[i:])))
            if base_dir and parts:
                for i in range(1, len(parts)):
                    candidates.append(os.path.normpath(os.path.join(base_dir, *parts[i:])))

        seen = set()
        for candidate in candidates:
            key = os.path.normcase(os.path.abspath(candidate))
            if key in seen:
                continue
            seen.add(key)
            if os.path.exists(candidate):
                return os.path.normpath(candidate)
        return ""

    def load_controller(self, path: str, preserve_state: bool = False):
        resolved_path = self._resolve_controller_path(path)
        if not resolved_path:
            return

        prev_state = self.current_state if preserve_state else None
        prev_is_playing = self.is_playing if preserve_state else False
        prev_is_paused = self.is_paused if preserve_state else False

        try:
            with open(resolved_path, "r") as f:
                data = json.load(f)
                self.controller = AnimationController.from_data(data)
                
            # Load clips for all nodes
            base_dir = os.path.dirname(resolved_path)
            for node in self.controller.nodes.values():
                if node.clip_path:
                    clip_path = self._resolve_path_variants(node.clip_path, base_dir=base_dir)
                    if clip_path:
                        with open(clip_path, "r") as cf:
                            clip_data = json.load(cf)
                            node.clip = AnimationClip.from_data(node.name, clip_data)
                            clip_dir = os.path.dirname(clip_path)
                            if node.clip.type == "spritesheet" and node.clip.sheet_path:
                                resolved_sheet = self._resolve_path_variants(node.clip.sheet_path, base_dir=clip_dir)
                                if resolved_sheet:
                                    node.clip.sheet_path = resolved_sheet
                            elif node.clip.type == "images" and node.clip.image_paths:
                                resolved_images = []
                                for image_path in node.clip.image_paths:
                                    resolved_image = self._resolve_path_variants(image_path, base_dir=clip_dir)
                                    resolved_images.append(resolved_image if resolved_image else image_path)
                                node.clip.image_paths = resolved_images
                            node.clip.load_frames()

            self.controller_path = path
            self._controller_file_path = resolved_path
            try:
                self._controller_mtime = os.path.getmtime(resolved_path)
            except OSError:
                self._controller_mtime = None

            default_state = self.controller.get_default_state()
            self.current_frame_index = 0
            self._frame_timer = 0.0
            target_state = None
            if prev_state and prev_state in self.controller.nodes and prev_state != AnimationController.ROOT_NODE_NAME:
                target_state = prev_state
            elif default_state and default_state in self.controller.nodes:
                target_state = default_state

            if target_state:
                self.current_state = target_state
                self.current_clip = self.controller.nodes[target_state].clip
                has_frames = bool(self.current_clip and self.current_clip.frames)
                if preserve_state:
                    self.is_playing = bool(prev_is_playing and has_frames)
                    self.is_paused = bool(prev_is_paused and self.is_playing)
                else:
                    self.is_playing = bool(self.play_on_start and has_frames)
                    self.is_paused = False
            else:
                self.current_state = None
                self.current_clip = None
                self.is_playing = False
                self.is_paused = False

        except Exception as e:
            _animator_logger.error("Failed to load animation controller", path=resolved_path, error=str(e))

    def reload_controller_if_changed(self):
        if not self.controller_path:
            return
        resolved_path = self._resolve_controller_path(self.controller_path)
        if not resolved_path:
            return
        try:
            current_mtime = os.path.getmtime(resolved_path)
        except OSError:
            return
        if self._controller_file_path != resolved_path or self._controller_mtime != current_mtime:
            self.load_controller(self.controller_path, preserve_state=True)

    def play(self, state_name: str, restart: bool = False):
        if not self.controller or state_name not in self.controller.nodes:
            return
        if state_name == AnimationController.ROOT_NODE_NAME:
            return

        changed_state = state_name != self.current_state
        node = self.controller.nodes[state_name]
        if not node.clip:
            return

        self.current_state = state_name
        self.current_clip = node.clip
        
        self.is_playing = True
        self.is_paused = False
        
        if restart or changed_state:
            self.current_frame_index = 0
            self._frame_timer = 0.0

    def stop(self, reset: bool = False):
        self.is_playing = False
        self.is_paused = False
        if reset:
            self.current_frame_index = 0
            self._frame_timer = 0.0

    def set_trigger(self, trigger_name: str):
        name = str(trigger_name or "").strip()
        if name:
            self._trigger_events.add(name)

    def consume_trigger(self, trigger_name: str):
        name = str(trigger_name or "").strip()
        if not name:
            return False
        if name in self._trigger_events:
            self._trigger_events.remove(name)
            return True
        return False

    def keep_only_triggers(self, valid_triggers: set[str]):
        if not self._trigger_events:
            return
        self._trigger_events.intersection_update(valid_triggers)

    def pause(self):
        if self.is_playing:
            self.is_paused = True

    def resume(self):
        if self.is_playing:
            self.is_paused = False

    def get_current_frame(self):
        if not self.current_clip:
            return None
        frames = self.current_clip.frames
        if not frames:
            return None
        index = max(0, min(self.current_frame_index, len(frames) - 1))
        return frames[index]
