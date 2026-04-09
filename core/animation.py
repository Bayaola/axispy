import json
import os
import pygame
from core.resources import ResourceManager

class AnimationClip:
    def __init__(self, name: str):
        self.name = name
        self.type = "spritesheet" # "spritesheet" or "images"
        self.fps = 12.0
        self.loop = True
        
        # Spritesheet params
        self.sheet_path = ""
        self.frame_width = 32
        self.frame_height = 32
        self.margin = 0
        self.spacing = 0
        self.start_frame = 0
        self.frame_count = 0
        
        # Image sequence params
        self.image_paths = []
        
        # Runtime data
        self.frames = []

    def load_frames(self):
        self.frames = []
        if self.type == "spritesheet" and self.sheet_path:
            all_frames = ResourceManager.slice_spritesheet(
                self.sheet_path,
                self.frame_width,
                self.frame_height,
                0,
                self.margin,
                self.spacing
            )
            if all_frames:
                clip_start = max(0, int(self.start_frame))
                if clip_start < len(all_frames):
                    if self.frame_count and self.frame_count > 0:
                        clip_end = min(len(all_frames), clip_start + int(self.frame_count))
                    else:
                        clip_end = len(all_frames)
                    self.frames = all_frames[clip_start:clip_end]
                    
        elif self.type == "images" and self.image_paths:
            for path in self.image_paths:
                image = ResourceManager.load_image(path)
                if image:
                    self.frames.append(image)

    def to_data(self) -> dict:
        data = {
            "type": self.type,
            "fps": self.fps,
            "loop": self.loop
        }
        if self.type == "spritesheet":
            data.update({
                "sheet_path": self.sheet_path,
                "frame_width": self.frame_width,
                "frame_height": self.frame_height,
                "margin": self.margin,
                "spacing": self.spacing,
                "start_frame": self.start_frame,
                "frame_count": self.frame_count
            })
        elif self.type == "images":
            data.update({
                "image_paths": self.image_paths
            })
        return data

    @staticmethod
    def from_data(name: str, data: dict) -> 'AnimationClip':
        clip = AnimationClip(name)
        clip.type = data.get("type", "spritesheet")
        clip.fps = data.get("fps", 12.0)
        clip.loop = data.get("loop", True)
        
        if clip.type == "spritesheet":
            clip.sheet_path = data.get("sheet_path", "")
            clip.frame_width = data.get("frame_width", 32)
            clip.frame_height = data.get("frame_height", 32)
            clip.margin = data.get("margin", 0)
            clip.spacing = data.get("spacing", 0)
            clip.start_frame = data.get("start_frame", 0)
            clip.frame_count = data.get("frame_count", 0)
        elif clip.type == "images":
            clip.image_paths = data.get("image_paths", [])
            
        return clip

class AnimationNode:
    def __init__(self, name: str, clip_path: str = "", position: tuple = (0, 0)):
        self.name = name
        self.clip_path = clip_path
        self.position = position # Editor position
        self.clip = None # Runtime AnimationClip instance

class AnimationTransition:
    def __init__(self, from_node: str, to_node: str, conditions: list = None, trigger: str = "", on_finish: bool = False):
        self.from_node = from_node
        self.to_node = to_node
        self.conditions = conditions or []
        self.trigger = str(trigger or "")
        self.on_finish = bool(on_finish)

class AnimationController:
    ROOT_NODE_NAME = "Root"

    def __init__(self):
        self.nodes = {}
        self.transitions = []
        self.default_node = None
        self.parameters = {}
        self.nodes[self.ROOT_NODE_NAME] = AnimationNode(self.ROOT_NODE_NAME, "", (80, 120))

    def add_node(self, name: str, clip_path: str, position: tuple = (0, 0)):
        if not name:
            return
        if name == self.ROOT_NODE_NAME and name in self.nodes:
            return
        self.nodes[name] = AnimationNode(name, clip_path, position)
        self._refresh_default_node()

    def add_transition(self, from_node: str, to_node: str, conditions: list = None, trigger: str = "", on_finish: bool = False):
        if from_node not in self.nodes or to_node not in self.nodes:
            return False
        if to_node == self.ROOT_NODE_NAME:
            return False
        if from_node == self.ROOT_NODE_NAME:
            self.transitions = [
                t for t in self.transitions
                if t.from_node != self.ROOT_NODE_NAME
            ]
        for transition in self.transitions:
            if transition.from_node == from_node and transition.to_node == to_node:
                return False
        self.transitions.append(AnimationTransition(from_node, to_node, conditions, trigger, on_finish))
        self._refresh_default_node()
        return True

    def remove_node(self, name: str):
        if name == self.ROOT_NODE_NAME or name not in self.nodes:
            return False
        del self.nodes[name]
        self.transitions = [
            t for t in self.transitions
            if t.from_node != name and t.to_node != name
        ]
        self._refresh_default_node()
        return True

    def rename_node(self, old_name: str, new_name: str):
        if not old_name or not new_name:
            return False
        if old_name == self.ROOT_NODE_NAME or old_name not in self.nodes:
            return False
        if new_name in self.nodes:
            return False
        node = self.nodes.pop(old_name)
        node.name = new_name
        self.nodes[new_name] = node
        for transition in self.transitions:
            if transition.from_node == old_name:
                transition.from_node = new_name
            if transition.to_node == old_name:
                transition.to_node = new_name
        self._refresh_default_node()
        return True

    def get_default_state(self):
        for transition in self.transitions:
            if transition.from_node == self.ROOT_NODE_NAME and transition.to_node in self.nodes:
                return transition.to_node
        return None

    def _normalize(self):
        idle_migrated = False
        if self.ROOT_NODE_NAME not in self.nodes:
            if "Idle" in self.nodes:
                node = self.nodes.pop("Idle")
                node.name = self.ROOT_NODE_NAME
                node.clip_path = ""
                self.nodes[self.ROOT_NODE_NAME] = node
                idle_migrated = True
            else:
                self.nodes[self.ROOT_NODE_NAME] = AnimationNode(self.ROOT_NODE_NAME, "", (80, 120))
        self.nodes[self.ROOT_NODE_NAME].clip_path = ""
        valid_names = set(self.nodes.keys())
        normalized = []
        has_root_transition = False
        for transition in self.transitions:
            from_node = transition.from_node
            to_node = transition.to_node
            if idle_migrated:
                if from_node == "Idle":
                    from_node = self.ROOT_NODE_NAME
                if to_node == "Idle":
                    to_node = self.ROOT_NODE_NAME
            if from_node not in valid_names or to_node not in valid_names:
                continue
            if to_node == self.ROOT_NODE_NAME:
                continue
            if from_node == self.ROOT_NODE_NAME:
                if has_root_transition:
                    continue
                has_root_transition = True
            if any(t.from_node == from_node and t.to_node == to_node for t in normalized):
                continue
            normalized.append(
                AnimationTransition(
                    from_node,
                    to_node,
                    transition.conditions,
                    transition.trigger,
                    transition.on_finish
                )
            )
        self.transitions = normalized
        self._refresh_default_node()

    def _refresh_default_node(self):
        self.default_node = self.get_default_state()

    def to_data(self) -> dict:
        self._normalize()
        return {
            "default_node": self.default_node,
            "nodes": [
                {
                    "name": node.name,
                    "clip_path": node.clip_path,
                    "position": node.position
                }
                for node in self.nodes.values()
            ],
            "transitions": [
                {
                    "from": t.from_node,
                    "to": t.to_node,
                    "conditions": t.conditions,
                    "trigger": t.trigger,
                    "on_finish": t.on_finish
                }
                for t in self.transitions
            ],
            "parameters": self.parameters
        }

    @staticmethod
    def from_data(data: dict) -> 'AnimationController':
        ctrl = AnimationController()
        ctrl.nodes = {}
        ctrl.transitions = []
        ctrl.parameters = data.get("parameters", {})

        # Only migrate legacy "Idle" → "Root" when no explicit Root node exists
        has_explicit_root = any(
            nd.get("name") == ctrl.ROOT_NODE_NAME
            for nd in data.get("nodes", [])
        )

        for node_data in data.get("nodes", []):
            node_name = node_data.get("name")
            if not node_name:
                continue
            if not has_explicit_root and node_name == "Idle":
                node_name = ctrl.ROOT_NODE_NAME
            if node_name in ctrl.nodes:
                continue
            clip_path = node_data.get("clip_path", "")
            if node_name == ctrl.ROOT_NODE_NAME:
                clip_path = ""
            ctrl.nodes[node_name] = AnimationNode(
                node_name,
                clip_path,
                tuple(node_data.get("position", (0, 0)))
            )

        for trans_data in data.get("transitions", []):
            from_node = trans_data.get("from")
            to_node = trans_data.get("to")
            if not has_explicit_root:
                if from_node == "Idle":
                    from_node = ctrl.ROOT_NODE_NAME
                if to_node == "Idle":
                    to_node = ctrl.ROOT_NODE_NAME
            ctrl.add_transition(
                from_node,
                to_node,
                trans_data.get("conditions"),
                trans_data.get("trigger", ""),
                trans_data.get("on_finish", False)
            )

        ctrl._normalize()
        return ctrl
