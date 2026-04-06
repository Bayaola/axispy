"""Builds context about the user's project and current editor state for AI chat."""
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

from core.logger import get_logger

_logger = get_logger("ai.context")


class ContextBuilder:
    """Collects project structure, scene info, and user scripts to provide
    rich context to the AI assistant."""

    def __init__(self):
        self.project_path: str = ""
        self._scene_getter = None  # callable that returns current Scene
        self._selected_getter = None  # callable that returns selected entities

    def set_project_path(self, path: str):
        self.project_path = path or ""

    def set_scene_getter(self, getter):
        """Set a callable that returns the current Scene object."""
        self._scene_getter = getter

    def set_selected_entities_getter(self, getter):
        """Set a callable that returns the list of selected entities."""
        self._selected_getter = getter

    def build_context(self) -> str:
        """Build a context string describing the user's project and current state."""
        parts = []

        # Project structure
        structure = self._scan_project_structure()
        if structure:
            parts.append("## Current Project Structure\n" + structure)

        # Current scene info
        scene_info = self._get_scene_context()
        if scene_info:
            parts.append("## Current Scene\n" + scene_info)

        # Selected entity details
        selected_info = self._get_selected_entities_context()
        if selected_info:
            parts.append("## Currently Selected Entities\n" + selected_info)

        # Project config
        config_info = self._get_project_config()
        if config_info:
            parts.append("## Project Configuration\n" + config_info)

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Project scanning
    # ------------------------------------------------------------------

    def _scan_project_structure(self) -> str:
        if not self.project_path or not os.path.isdir(self.project_path):
            return ""

        lines = []
        scenes = []
        scripts = []
        prefabs = []
        assets = []

        for root, dirs, files in os.walk(self.project_path):
            # Skip hidden dirs and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            rel_root = os.path.relpath(root, self.project_path)

            for f in files:
                rel_path = os.path.join(rel_root, f) if rel_root != "." else f
                rel_path = rel_path.replace("\\", "/")

                if f.endswith(".scene"):
                    scenes.append(rel_path)
                elif f.endswith(".py") and not f.startswith("__"):
                    scripts.append(rel_path)
                elif f.endswith(".entity"):
                    prefabs.append(rel_path)
                elif f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".wav", ".ogg", ".mp3")):
                    assets.append(rel_path)

        if scenes:
            lines.append("**Scenes:** " + ", ".join(scenes))
        if scripts:
            lines.append("**Scripts:** " + ", ".join(scripts[:30]))
            if len(scripts) > 30:
                lines.append(f"  ... and {len(scripts) - 30} more scripts")
        if prefabs:
            lines.append("**Prefabs:** " + ", ".join(prefabs[:20]))
        if assets:
            lines.append(f"**Assets:** {len(assets)} files (images, audio, etc.)")

        return "\n".join(lines)

    def _get_scene_context(self) -> str:
        if not self._scene_getter:
            return ""
        try:
            scene = self._scene_getter()
            if not scene or not scene.world:
                return ""

            world = scene.world
            entities = world.entities
            
            # Build systems info
            systems_lines = []
            if hasattr(world, 'systems'):
                sys_count = len(world.systems)
                systems_lines.append(f"**Active Systems ({sys_count}):**")
                sys_names = [type(sys).__name__ for sys in world.systems]
                systems_lines.append(", ".join(sys_names))
            
            lines = []
            if systems_lines:
                lines.extend(systems_lines)
                lines.append("")
                
            lines.append(f"**Entity count:** {len(entities)}")

            for entity in entities[:50]:
                comp_names = ", ".join(type(c).__name__ for c in entity.components.values())
                parent_info = f" (parent: {entity.parent.name})" if entity.parent else ""
                groups_info = f" [groups: {', '.join(entity.groups)}]" if entity.groups else ""
                tags_info = f" [tags: {', '.join(entity.tags)}]" if entity.tags else ""
                lines.append(f"- **{entity.name}**{parent_info}: {comp_names}{groups_info}{tags_info}")

            if len(entities) > 50:
                lines.append(f"... and {len(entities) - 50} more entities")

            return "\n".join(lines)
        except Exception as e:
            _logger.warning("Error getting scene context", error=str(e))
            return ""

    def _get_selected_entities_context(self) -> str:
        if not self._selected_getter:
            return ""
        try:
            selected = self._selected_getter()
            if not selected:
                return "No entities selected."

            lines = []
            for entity in selected:
                lines.append(f"### {entity.name}")
                lines.append(f"- Layer: {entity.layer}")
                if entity.groups:
                    lines.append(f"- Groups: {', '.join(entity.groups)}")
                if entity.tags:
                    lines.append(f"- Tags: {', '.join(entity.tags)}")

                for comp_type, comp in entity.components.items():
                    comp_name = comp_type.__name__
                    props = self._get_component_properties(comp)
                    if props:
                        lines.append(f"- **{comp_name}**: {props}")
                    else:
                        lines.append(f"- **{comp_name}**")

            return "\n".join(lines)
        except Exception as e:
            _logger.warning("Error getting selected entities", error=str(e))
            return ""

    def _get_component_properties(self, comp) -> str:
        """Extract key properties from a component for display."""
        skip = {"entity", "instance", "started", "image", "_module_key",
                "_loaded_script_path", "_loaded_class_name", "_loaded_mtime",
                "_coroutine_manager", "_tween_manager", "_events",
                "_previous_transform_state", "_current_transform_state"}
        props = {}
        for key in dir(comp):
            if key.startswith("_") or key in skip:
                continue
            if callable(getattr(type(comp), key, None)) and isinstance(getattr(type(comp), key, None), property):
                try:
                    props[key] = getattr(comp, key)
                except Exception:
                    pass
            elif not callable(getattr(comp, key, None)):
                try:
                    val = getattr(comp, key)
                    if not callable(val):
                        props[key] = val
                except Exception:
                    pass

        if not props:
            return ""

        parts = []
        for k, v in list(props.items())[:10]:
            parts.append(f"{k}={v!r}")
        return ", ".join(parts)

    def _get_project_config(self) -> str:
        if not self.project_path:
            return ""
        config_path = os.path.join(self.project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            # Only include relevant keys
            relevant = {}
            for key in ("game_name", "resolution", "display", "layers", "groups",
                        "input_actions", "lighting"):
                if key in config:
                    relevant[key] = config[key]
            return json.dumps(relevant, indent=2)
        except Exception:
            return ""

    def get_user_script_content(self, script_path: str) -> str:
        """Read the content of a user script file."""
        if not script_path:
            return ""
        # Try absolute path first
        if os.path.isabs(script_path) and os.path.exists(script_path):
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return ""
        # Try relative to project path
        if self.project_path:
            full_path = os.path.join(self.project_path, script_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    pass
        return ""
