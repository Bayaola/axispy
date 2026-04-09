import asyncio
import pygame
import sys
import os
import json
import math
from collections import deque
from core.scene import Scene
from core.systems import RenderSystem, AnimationSystem, ParticleSystem, LightingSystem
from core.systems.physics_system import PhysicsSystem
from core.systems.script_system import ScriptSystem
from core.systems.audio_system import AudioSystem
from core.systems.network_system import NetworkSystem
from core.systems.ui_system import UISystem
from core.systems.steering_system import SteeringSystem
from core.systems.timer_system import TimerSystem
from core.systems.event_dispatch_system import EventDispatchSystem
from core.serializer import SceneSerializer
from core.input import Input
from core.input_map import InputMap
from core.debug_overlay import DebugOverlay
from core.components import Transform, BoxCollider2D, CircleCollider2D, PolygonCollider2D
from core.vector import Vector2
from core.resources import ResourceManager
from core.scene_transition import SceneTransition
from core.logger import get_logger

# Check if running in editor mode
EDITOR_MODE = os.environ.get("AXISPY_EDITOR_MODE") == "1"

_player_logger = get_logger("player")

# In production builds, we don't want console output to interfere
if not EDITOR_MODE:
    # Suppress logger output in production
    import core.logger
    core.logger.set_min_level(core.logger.LogLevels.ERROR)
else:
    # In editor mode, enable all logging levels
    import core.logger
    core.logger.set_min_level(core.logger.LogLevels.DEBUG)

def editor_print(*args, **kwargs):
    """Print function that only outputs when running in editor mode."""
    if EDITOR_MODE:
        print(*args, **kwargs)

class RuntimePlayer:
    """Encapsulates the runtime game loop, systems, and scene management."""

    def __init__(self, scene_path: str | None = None, web_mode: bool = False):
        self.scene_path = scene_path
        self.web_mode = web_mode
        self.project_dir = ""
        self.project_config: dict = {}

        # Display defaults
        self.window_width = 800
        self.window_height = 600
        self.design_width = 800
        self.design_height = 600
        self.window_resizable = True
        self.window_fullscreen = False
        self.stretch_mode = "fit"
        self.stretch_aspect = "keep"
        self.stretch_scale = "fractional"
        self.window_title = "AxisPy Engine - Player"
        self.bg_color = (33, 33, 33)
        self.game_icon_path = ""
        self.web_target_fps = 60

        # Pygame surfaces
        self.screen = None
        self.render_surface = None
        self.use_virtual_surface = True
        self.flags = 0
        self.presentation_rect = pygame.Rect(0, 0, 800, 600)

        # Systems (created once, reused across scene changes)
        self.physics_system = None
        self.script_system = None
        self.audio_system = None
        self.network_system = None
        self.animation_system = None
        self.particle_system = None
        self.ui_system = None
        self.steering_system = None
        self.timer_system = None
        self.event_dispatch_system = None
        self.render_system = None
        self.lighting_system = None

        # Scene state
        self.scene: Scene | None = None
        self.current_scene_path = ""
        self._pending_scene_path: str | None = None
        self._scene_transition = SceneTransition(duration=0.35, color=(0, 0, 0))

        # Loop state
        self.running = True
        self.fixed_dt = 1.0 / 60.0
        self.max_frame_dt = 0.25
        self.max_substeps = 8
        self.accumulator = 0.0
        self._dt_buffer: deque[float] = deque(maxlen=5)

        # Physics debug (editor mode)
        self.physics_debug_mode = False
        self.collider_drag_state = None
        self.collider_handle_min_screen_distance = 88

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _resolve_project_dir(self):
        if not self.scene_path:
            return
        scene_abs_path = os.path.abspath(self.scene_path)
        env_project_dir = os.environ.get("AXISPY_PROJECT_PATH", "").strip()
        if env_project_dir and os.path.exists(env_project_dir):
            self.project_dir = os.path.abspath(env_project_dir)
        else:
            scene_parent = os.path.dirname(scene_abs_path)
            if os.path.basename(scene_parent).lower() == "scenes":
                self.project_dir = os.path.dirname(scene_parent)
            else:
                self.project_dir = scene_parent
        if self.project_dir not in sys.path:
            sys.path.insert(0, self.project_dir)
            _player_logger.info("Added project directory to sys.path", path=self.project_dir)
        os.chdir(self.project_dir)
        _player_logger.info("Changed CWD", path=self.project_dir)
        ResourceManager.set_base_path(self.project_dir)

    def _read_config(self):
        if not self.scene_path:
            return
        config_path = os.path.join(self.project_dir, "project.config")
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                self.project_config = config
                res = config.get("resolution", {})
                display = config.get("display", {})
                virtual_resolution = display.get("virtual_resolution", {})
                self.design_width = int(virtual_resolution.get("width", res.get("width", self.design_width)))
                self.design_height = int(virtual_resolution.get("height", res.get("height", self.design_height)))
                window_cfg = display.get("window", {})
                stretch_cfg = display.get("stretch", {})
                self.window_width = int(window_cfg.get("width", res.get("width", self.window_width)))
                self.window_height = int(window_cfg.get("height", res.get("height", self.window_height)))
                self.window_resizable = bool(window_cfg.get("resizable", True))
                self.window_fullscreen = bool(window_cfg.get("fullscreen", False))
                self.stretch_mode = str(stretch_cfg.get("mode", "fit")).lower()
                self.stretch_aspect = str(stretch_cfg.get("aspect", "keep")).lower()
                self.stretch_scale = str(stretch_cfg.get("scale", "fractional")).lower()
                game_name = config.get("game_name")
                if game_name:
                    self.window_title = str(game_name)
                icon_value = str(config.get("game_icon", "")).strip()
                if icon_value:
                    native_icon = ResourceManager.to_os_path(icon_value)
                    if os.path.isabs(native_icon):
                        self.game_icon_path = native_icon
                    else:
                        self.game_icon_path = os.path.normpath(os.path.join(self.project_dir, native_icon))
                self.bg_color = tuple(config.get("background_color", [0, 0, 0]))
                # P11-8: Load input action mappings from config
                if "input_actions" in config:
                    InputMap.load_from_config(config)
        except Exception as e:
            _player_logger.error("Failed to read project.config", error=str(e))

    def _apply_web_overrides(self):
        if not self.web_mode:
            return
        web_cfg = self.project_config.get("web", {})
        resolution_scale = float(web_cfg.get("resolution_scale", 1.0))
        resolution_scale = max(0.25, min(1.0, resolution_scale))
        if resolution_scale < 1.0:
            self.design_width = max(1, int(self.design_width * resolution_scale))
            self.design_height = max(1, int(self.design_height * resolution_scale))
            _player_logger.info("Web resolution scaled", scale=resolution_scale, width=self.design_width, height=self.design_height)
        self.web_target_fps = int(web_cfg.get("target_fps", 30))
        self.web_target_fps = max(15, min(120, self.web_target_fps))
        # Browsers strictly reject API full-screen requests without a direct user DOM gesture.
        # Startup full-screen is impossible without throwing an error, so we disable it for initialization.
        self.window_fullscreen = False
        # Prevent scratchy audio in browsers by explicitly raising the SDL audio buffer size
        audio_buffer = 4096
        pygame.mixer.pre_init(44100, -16, 2, audio_buffer)

    def _init_display(self):
        pygame.init()
        self.flags = 0
        if self.window_resizable:
            self.flags |= pygame.RESIZABLE
        if self.window_fullscreen:
            self.flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((self.window_width, self.window_height), self.flags)
        if self.game_icon_path and os.path.exists(self.game_icon_path):
            try:
                pygame.display.set_icon(pygame.image.load(self.game_icon_path))
            except Exception as e:
                _player_logger.warning("Failed to set game icon", path=self.game_icon_path, error=str(e))
        pygame.display.set_caption(self.window_title)

    def _create_systems(self):
        self.physics_system = PhysicsSystem()
        self.script_system = ScriptSystem()
        self.audio_system = AudioSystem()
        self.network_system = NetworkSystem()
        self.animation_system = AnimationSystem()
        self.particle_system = ParticleSystem()
        self.ui_system = UISystem()
        self.steering_system = SteeringSystem()
        self.timer_system = TimerSystem()
        self.event_dispatch_system = EventDispatchSystem()

        self.use_virtual_surface = self.stretch_mode != "disabled"
        self.render_surface = pygame.Surface((self.design_width, self.design_height)) if self.use_virtual_surface else self.screen
        self.render_system = RenderSystem(self.render_surface)
        self.render_system.design_size = (self.design_width, self.design_height)
        if self.web_mode:
            self.render_system.smooth_present = False
        self.lighting_system = LightingSystem(self.render_surface, self.project_config)

    def _attach_systems(self, target_scene: Scene):
        target_scene.world.add_system(self.physics_system)
        target_scene.world.add_system(self.script_system)
        target_scene.world.add_system(self.audio_system)
        target_scene.world.add_system(self.network_system)
        target_scene.world.add_system(self.animation_system)
        target_scene.world.add_system(self.particle_system)
        target_scene.world.add_system(self.ui_system)
        target_scene.world.add_system(self.steering_system)
        target_scene.world.add_system(self.timer_system)
        target_scene.world.add_system(self.event_dispatch_system)
        target_scene.world.add_system(self.render_system)
        target_scene.world.add_system(self.lighting_system)

    # ------------------------------------------------------------------
    # Scene management
    # ------------------------------------------------------------------

    def _apply_project_world_settings(self, target_scene: Scene):
        config_layers = self.project_config.get("layers", ["Default"])
        normalized_layers = []
        seen_layers = set()
        if isinstance(config_layers, list):
            for layer in config_layers:
                name = str(layer).strip()
                if not name:
                    continue
                lowered = name.lower()
                if lowered in seen_layers:
                    continue
                seen_layers.add(lowered)
                normalized_layers.append(name)
        if "default" in seen_layers:
            normalized_layers = [layer for layer in normalized_layers if layer.lower() != "default"]
        normalized_layers.insert(0, "Default")
        target_scene.world.layers = normalized_layers

        config_groups = self.project_config.get("groups", [])
        normalized_groups = []
        seen_groups = set()
        if isinstance(config_groups, list):
            for group_name in config_groups:
                group_text = str(group_name).strip()
                if not group_text:
                    continue
                lowered = group_text.lower()
                if lowered in seen_groups:
                    continue
                seen_groups.add(lowered)
                normalized_groups.append(group_text)
        world = target_scene.world
        for group_name in list(world.groups.keys()):
            if group_name not in normalized_groups:
                members = list(world.groups.get(group_name, set()))
                for entity in members:
                    entity.remove_group(group_name)
        for group_name in normalized_groups:
            world.groups.setdefault(group_name, set())

        raw_matrix = self.project_config.get("physics_collision_matrix", {})
        if not isinstance(raw_matrix, dict):
            raw_matrix = {}
        normalized_matrix = {}
        for row_group in normalized_groups:
            targets = raw_matrix.get(row_group, normalized_groups)
            if not isinstance(targets, list):
                targets = normalized_groups
            allowed_targets = []
            seen_targets = set()
            for target in targets:
                target_name = str(target).strip()
                if target_name not in normalized_groups:
                    continue
                lowered_target = target_name.lower()
                if lowered_target in seen_targets:
                    continue
                seen_targets.add(lowered_target)
                allowed_targets.append(target_name)
            normalized_matrix[row_group] = allowed_targets
        for row_group in normalized_groups:
            for target in list(normalized_matrix.get(row_group, [])):
                peer = normalized_matrix.setdefault(target, [])
                if row_group not in peer:
                    peer.append(row_group)
        world.physics_group_order = list(normalized_groups)
        world.physics_collision_matrix = normalized_matrix

    def _resolve_scene_change_path(self, scene_name: str):
        requested = str(scene_name or "").strip()
        if not requested:
            return ""
        requested = os.path.normpath(requested)
        has_extension = bool(os.path.splitext(requested)[1])
        variants = [requested] if has_extension else [requested, requested + ".scn"]
        candidates = []
        for variant in variants:
            if os.path.isabs(variant):
                candidates.append(variant)
                continue
            if self.project_dir:
                candidates.append(os.path.normpath(os.path.join(self.project_dir, variant)))
                candidates.append(os.path.normpath(os.path.join(self.project_dir, "scenes", variant)))
            if self.current_scene_path:
                scene_dir = os.path.dirname(self.current_scene_path)
                candidates.append(os.path.normpath(os.path.join(scene_dir, variant)))
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return os.path.abspath(candidate)
        return ""

    def _load_scene(self, target_scene_path: str) -> Scene:
        if target_scene_path and os.path.exists(target_scene_path):
            try:
                with open(target_scene_path, "r") as f:
                    loaded_scene = SceneSerializer.from_json(f.read())
                self._apply_project_world_settings(loaded_scene)
                return loaded_scene
            except Exception as e:
                _player_logger.error("Failed to load scene", scene=target_scene_path, error=str(e))
        fallback_scene = Scene()
        fallback_scene.setup_default()
        self._apply_project_world_settings(fallback_scene)
        return fallback_scene

    def _teardown_scene(self):
        if not self.scene:
            return
        world = self.scene.world
        for entity in list(world.entities):
            world.destroy_entity(entity)
        if pygame.mixer.get_init():
            pygame.mixer.stop()
            pygame.mixer.music.stop()

    def _preload_and_cleanup(self):
        _preload = ResourceManager.preload_scene_assets(self.scene.world.entities)
        ResourceManager.unload_unused(
            _preload.get("used_image_paths"),
            _preload.get("used_sound_paths"),
        )

    # ------------------------------------------------------------------
    # Coordinate mapping & presentation
    # ------------------------------------------------------------------

    def update_presentation_rect(self):
        screen_w, screen_h = self.screen.get_size()
        if not self.use_virtual_surface:
            self.presentation_rect = pygame.Rect(0, 0, screen_w, screen_h)
            return

        base_w, base_h = self.render_surface.get_size()
        mode = self.stretch_mode if self.stretch_mode in ("stretch", "fit", "crop") else "fit"
        keep_aspect = self.stretch_aspect != "ignore"
        integer_scale = self.stretch_scale == "integer"

        if mode == "stretch" and not keep_aspect:
            self.presentation_rect = pygame.Rect(0, 0, screen_w, screen_h)
            return

        ratio_w = screen_w / max(1, base_w)
        ratio_h = screen_h / max(1, base_h)
        if mode == "crop":
            factor = max(ratio_w, ratio_h)
            if integer_scale:
                factor = max(1.0, math.ceil(factor))
        else:
            factor = min(ratio_w, ratio_h)
            if integer_scale:
                factor = max(1.0, math.floor(factor))
            factor = max(1.0 if integer_scale else 0.01, factor)

        target_w = max(1, int(base_w * factor))
        target_h = max(1, int(base_h * factor))
        offset_x = (screen_w - target_w) // 2
        offset_y = (screen_h - target_h) // 2
        self.presentation_rect = pygame.Rect(offset_x, offset_y, target_w, target_h)

    def window_to_render(self, window_x, window_y):
        if not self.use_virtual_surface:
            return window_x, window_y
        if self.presentation_rect.width <= 0 or self.presentation_rect.height <= 0:
            return None
        if (
            window_x < self.presentation_rect.x
            or window_x >= self.presentation_rect.x + self.presentation_rect.width
            or window_y < self.presentation_rect.y
            or window_y >= self.presentation_rect.y + self.presentation_rect.height
        ):
            return None
        normalized_x = (window_x - self.presentation_rect.x) / self.presentation_rect.width
        normalized_y = (window_y - self.presentation_rect.y) / self.presentation_rect.height
        render_x = normalized_x * self.render_surface.get_width()
        render_y = normalized_y * self.render_surface.get_height()
        return render_x, render_y

    def world_to_screen(self, world_x, world_y):
        return self.render_system.world_to_screen(world_x, world_y, entities=self.scene.world.entities)

    def screen_to_world(self, window_x, window_y):
        mapped = self.window_to_render(window_x, window_y)
        if mapped is None:
            return None
        return self.render_system.screen_to_world(mapped[0], mapped[1], entities=self.scene.world.entities)

    def present_frame(self):
        if not self.use_virtual_surface:
            return
        if self.presentation_rect.width <= 0 or self.presentation_rect.height <= 0:
            return
        self.screen.fill((0, 0, 0))
        scale_fn = pygame.transform.smoothscale if self.render_system.smooth_present else pygame.transform.scale
        scaled = scale_fn(
            self.render_surface,
            (self.presentation_rect.width, self.presentation_rect.height)
        )
        self.screen.blit(scaled, self.presentation_rect)

    # ------------------------------------------------------------------
    # Physics debug drawing & collider handles
    # ------------------------------------------------------------------

    def build_collider_handles(self):
        handles = []
        for entity in self.scene.world.entities:
            transform = entity.get_component(Transform)
            if not transform:
                continue

            box = entity.get_component(BoxCollider2D)
            circle = entity.get_component(CircleCollider2D)
            polygon = entity.get_component(PolygonCollider2D)
            if not box and not circle and not polygon:
                continue

            if box:
                center_x = transform.x + box.offset_x
                center_y = transform.y + box.offset_y
                half_w = max(0.5, abs(box.width) * 0.5)
                half_h = max(0.5, abs(box.height) * 0.5)
                handle_defs = [
                    ("width", 1, center_x + half_w, center_y),
                    ("width", -1, center_x - half_w, center_y),
                    ("height", 1, center_x, center_y + half_h),
                    ("height", -1, center_x, center_y - half_h),
                ]
                for attr, direction, world_x, world_y in handle_defs:
                    screen_x, screen_y = self.world_to_screen(world_x, world_y)
                    center_screen_x, center_screen_y = self.world_to_screen(center_x, center_y)
                    dx = screen_x - center_screen_x
                    dy = screen_y - center_screen_y
                    distance = math.hypot(dx, dy)
                    if distance < self.collider_handle_min_screen_distance:
                        if distance == 0:
                            if attr == "width":
                                dx = direction
                                dy = 0
                            else:
                                dx = 0
                                dy = direction
                            distance = 1.0
                        scale = self.collider_handle_min_screen_distance / distance
                        screen_x = center_screen_x + (dx * scale)
                        screen_y = center_screen_y + (dy * scale)
                    handles.append({
                        "entity": entity,
                        "transform": transform,
                        "component": box,
                        "attr": attr,
                        "direction": direction,
                        "center_x": center_x,
                        "center_y": center_y,
                        "screen_x": screen_x,
                        "screen_y": screen_y
                    })
                center_screen_x, center_screen_y = self.world_to_screen(center_x, center_y)
                move_offset = self.collider_handle_min_screen_distance * 0.75
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": box,
                    "attr": "offset",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": center_screen_x - move_offset,
                    "screen_y": center_screen_y - move_offset
                })

            if circle:
                center_x = transform.x + circle.offset_x
                center_y = transform.y + circle.offset_y
                radius = max(0.5, abs(circle.radius))
                handle_defs = [
                    ("radius", 1, center_x + radius, center_y),
                    ("radius", -1, center_x - radius, center_y),
                    ("radius", 1, center_x, center_y + radius),
                    ("radius", -1, center_x, center_y - radius),
                ]
                for _, direction, world_x, world_y in handle_defs:
                    screen_x, screen_y = self.world_to_screen(world_x, world_y)
                    center_screen_x, center_screen_y = self.world_to_screen(center_x, center_y)
                    dx = screen_x - center_screen_x
                    dy = screen_y - center_screen_y
                    distance = math.hypot(dx, dy)
                    if distance < self.collider_handle_min_screen_distance:
                        if distance == 0:
                            dx = direction
                            dy = 0
                            distance = 1.0
                        scale = self.collider_handle_min_screen_distance / distance
                        screen_x = center_screen_x + (dx * scale)
                        screen_y = center_screen_y + (dy * scale)
                    handles.append({
                        "entity": entity,
                        "transform": transform,
                        "component": circle,
                        "attr": "radius",
                        "direction": direction,
                        "center_x": center_x,
                        "center_y": center_y,
                        "screen_x": screen_x,
                        "screen_y": screen_y
                    })
                center_screen_x, center_screen_y = self.world_to_screen(center_x, center_y)
                move_offset = self.collider_handle_min_screen_distance * 0.75
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": circle,
                    "attr": "offset",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": center_screen_x - move_offset,
                    "screen_y": center_screen_y - move_offset
                })
            if polygon and len(polygon.points) >= 3:
                world_points = [
                    (transform.x + polygon.offset_x + point.x, transform.y + polygon.offset_y + point.y)
                    for point in polygon.points
                ]
                center_x = sum(point[0] for point in world_points) / len(world_points)
                center_y = sum(point[1] for point in world_points) / len(world_points)
                for index, (world_x, world_y) in enumerate(world_points):
                    screen_x, screen_y = self.world_to_screen(world_x, world_y)
                    handles.append({
                        "entity": entity,
                        "transform": transform,
                        "component": polygon,
                        "attr": "point",
                        "point_index": index,
                        "direction": 0,
                        "center_x": center_x,
                        "center_y": center_y,
                        "screen_x": screen_x,
                        "screen_y": screen_y
                    })
                center_screen_x, center_screen_y = self.world_to_screen(center_x, center_y)
                move_offset = self.collider_handle_min_screen_distance * 0.75
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": polygon,
                    "attr": "offset",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": center_screen_x - move_offset,
                    "screen_y": center_screen_y - move_offset
                })
        return handles

    def update_collider_resize(self, mouse_pos):
        if not self.collider_drag_state:
            return

        mapped_world = self.screen_to_world(mouse_pos[0], mouse_pos[1])
        if mapped_world is None:
            return
        world_x, world_y = mapped_world
        state = self.collider_drag_state
        comp = state["component"]
        attr = state["attr"]
        direction = state["direction"]
        cx = state["center_x"]
        cy = state["center_y"]

        if attr == "width":
            if direction > 0:
                comp.width = max(1.0, (world_x - cx) * 2.0)
            else:
                comp.width = max(1.0, (cx - world_x) * 2.0)
        elif attr == "height":
            if direction > 0:
                comp.height = max(1.0, (world_y - cy) * 2.0)
            else:
                comp.height = max(1.0, (cy - world_y) * 2.0)
        elif attr == "radius":
            dx = world_x - cx
            dy = world_y - cy
            comp.radius = max(0.5, math.hypot(dx, dy))
        elif attr == "offset":
            transform = state["transform"]
            center_x = world_x - state["grab_dx"]
            center_y = world_y - state["grab_dy"]
            comp.offset_x = center_x - transform.x
            comp.offset_y = center_y - transform.y
        elif attr == "point":
            transform = state["transform"]
            point_index = state["point_index"]
            if point_index < 0 or point_index >= len(comp.points):
                return
            new_points = [Vector2(point.x, point.y) for point in comp.points]
            new_points[point_index] = Vector2(
                world_x - transform.x - comp.offset_x,
                world_y - transform.y - comp.offset_y
            )
            comp.points = new_points

    def draw_physics_debug(self):
        collider_color = (80, 190, 255)

        for entity in self.scene.world.entities:
            transform = entity.get_component(Transform)
            if not transform:
                continue

            box = entity.get_component(BoxCollider2D)
            circle = entity.get_component(CircleCollider2D)
            polygon = entity.get_component(PolygonCollider2D)
            if not box and not circle and not polygon:
                continue

            if box:
                center_x = transform.x + box.offset_x
                center_y = transform.y + box.offset_y
                half_w = max(0.5, abs(box.width) * 0.5)
                half_h = max(0.5, abs(box.height) * 0.5)
                left_top = self.world_to_screen(center_x - half_w, center_y - half_h)
                right_bottom = self.world_to_screen(center_x + half_w, center_y + half_h)
                rect = pygame.Rect(
                    int(min(left_top[0], right_bottom[0])),
                    int(min(left_top[1], right_bottom[1])),
                    max(1, int(abs(right_bottom[0] - left_top[0]))),
                    max(1, int(abs(right_bottom[1] - left_top[1])))
                )
                pygame.draw.rect(self.render_system.surface, collider_color, rect, 2)

            if circle:
                center_x = transform.x + circle.offset_x
                center_y = transform.y + circle.offset_y
                screen_x, screen_y = self.world_to_screen(center_x, center_y)
                view = self.render_system.get_primary_camera_view(self.scene.world.entities)
                screen_radius = max(1, int(abs(circle.radius) * view["zoom"]))
                pygame.draw.circle(self.render_system.surface, collider_color, (int(screen_x), int(screen_y)), screen_radius, 2)
            if polygon and len(polygon.points) >= 3:
                screen_points = []
                for point in polygon.points:
                    world_x = transform.x + polygon.offset_x + point.x
                    world_y = transform.y + polygon.offset_y + point.y
                    screen_x, screen_y = self.world_to_screen(world_x, world_y)
                    screen_points.append((int(screen_x), int(screen_y)))
                if len(screen_points) >= 3:
                    pygame.draw.polygon(self.render_system.surface, collider_color, screen_points, 2)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        self._resolve_project_dir()
        self._read_config()
        self._apply_web_overrides()
        self._init_display()
        self._create_systems()

        self.current_scene_path = os.path.abspath(self.scene_path) if self.scene_path and os.path.exists(self.scene_path) else ""
        self.scene = self._load_scene(self.current_scene_path)
        editor_view_state = getattr(self.scene, "editor_view_state", {})
        self.physics_debug_mode = bool(editor_view_state.get("physics_debug_mode", False))

        self._attach_systems(self.scene)
        self._preload_and_cleanup()

        clock = pygame.time.Clock()
        last_tick_ms = pygame.time.get_ticks()

        self.presentation_rect = pygame.Rect(0, 0, self.screen.get_width(), self.screen.get_height())
        self.update_presentation_rect()
        Input.set_mouse_mapper(self.window_to_render)
        self.scene.world.sync_interpolation_state()

        web_min_frame_ms = (1000.0 / self.web_target_fps) if self.web_mode else 0

        while self.running:
            if self.web_mode:
                current_tick_ms = pygame.time.get_ticks()
                delta_ms = current_tick_ms - last_tick_ms
                if delta_ms < web_min_frame_ms:
                    await asyncio.sleep(0)
                    continue
                if delta_ms < 0:
                    delta_ms = 0
                last_tick_ms = current_tick_ms
                if delta_ms == 0:
                    delta_ms = 16
                raw_dt = min(self.max_frame_dt, delta_ms / 1000.0)
            else:
                raw_dt = min(self.max_frame_dt, clock.tick(240) / 1000.0)

            # Smooth delta time with a rolling average to reduce jitter
            self._dt_buffer.append(raw_dt)
            frame_dt = sum(self._dt_buffer) / len(self._dt_buffer)
            self.accumulator += frame_dt
            
            # Update Input manager
            Input.update()
            InputMap.update()
            
            for event in Input._events:
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE and self.window_resizable:
                    self.screen = pygame.display.set_mode((event.w, event.h), self.flags)
                    if not self.use_virtual_surface:
                        self.render_system.surface = self.screen
                    self.update_presentation_rect()

            requested_scene_name = getattr(self.scene.world, "_requested_scene_name", "")
            if requested_scene_name and self._pending_scene_path is None:
                self.scene.world._requested_scene_name = ""
                resolved_scene_path = self._resolve_scene_change_path(requested_scene_name)
                if resolved_scene_path:
                    self._pending_scene_path = resolved_scene_path
                    self._scene_transition.start_out()
                else:
                    _player_logger.warning("Scene change failed", scene=requested_scene_name)

            # When fade-out completes, swap scenes and begin fade-in
            if self._pending_scene_path is not None and self._scene_transition.is_fade_out_done():
                self._teardown_scene()
                self.scene = self._load_scene(self._pending_scene_path)
                self.current_scene_path = self._pending_scene_path
                self._pending_scene_path = None
                self._attach_systems(self.scene)
                self._preload_and_cleanup()
                self.physics_system._active_collisions.clear()
                self.scene.world.sync_interpolation_state()
                self.accumulator = 0.0
                self._scene_transition.start_in()

            self._scene_transition.update(frame_dt)
            
            step_count = 0
            while self.accumulator >= self.fixed_dt and step_count < self.max_substeps:
                self.scene.world.simulate(self.fixed_dt)
                self.accumulator -= self.fixed_dt
                step_count += 1
            if step_count == self.max_substeps and self.accumulator >= self.fixed_dt:
                self.accumulator = min(self.accumulator, self.fixed_dt)

            alpha = self.accumulator / self.fixed_dt

            self.render_system.surface.fill(self.bg_color)
            self.scene.world.render(frame_dt, alpha)
            if self.physics_debug_mode:
                self.draw_physics_debug()
            self._scene_transition.draw(self.render_system.surface)
            # P11-6: Debug overlay
            DebugOverlay.update(frame_dt, self.scene.world)
            DebugOverlay.draw(self.render_system.surface)
            self.present_frame()
            pygame.display.flip()
            if self.web_mode:
                await asyncio.sleep(0)
            
        self._teardown_scene()
        pygame.quit()
        if not self.web_mode:
            sys.exit()


async def _run(scene_path=None, web_mode: bool = False):
    player = RuntimePlayer(scene_path, web_mode)
    await player.run()


def run(scene_path=None):
    if sys.platform == "emscripten":
        try:
            running_loop = asyncio.get_running_loop()
            return running_loop.create_task(_run(scene_path, web_mode=True))
        except RuntimeError:
            return asyncio.run(_run(scene_path, web_mode=True))
    return asyncio.run(_run(scene_path, web_mode=False))

if __name__ == "__main__":
    scene_path = sys.argv[1] if len(sys.argv) > 1 else None
    run(scene_path)
