"""Engine-specific tools that the AI agent can call to inspect the project."""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional


# ------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ------------------------------------------------------------------

ENGINE_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_entities",
            "description": "List all entities in the current scene with their components.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of entities to return (default 50).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_info",
            "description": "Get detailed information about a specific entity by name, including all component properties.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "The name of the entity to inspect.",
                    },
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_script",
            "description": "Read the source code of a user script file from the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path to the script file, relative to the project root (e.g. 'scripts/player.py').",
                    },
                },
                "required": ["script_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_script",
            "description": "Create or overwrite a script file directly. Use this instead of writing code in chat when the user asks you to script something. This will create the actual .py file in the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path to the script file, relative to project root (e.g. 'scripts/player.py').",
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete Python code to write to the file.",
                    },
                },
                "required": ["script_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_script",
            "description": "Edit an existing script file by replacing specific text. Use for small modifications to existing scripts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path to the script file, relative to project root.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "The text to replace (must be unique in the file).",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The new text to insert.",
                    },
                },
                "required": ["script_path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_scene",
            "description": "Read the raw JSON content of a scene file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_path": {
                        "type": "string",
                        "description": "Path to the scene file, relative to project root (e.g. 'scenes/main.scene').",
                    },
                },
                "required": ["scene_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_entity",
            "description": "Create a new entity in the scene by editing the scene file directly. Creates the entity in the hierarchy with specified components.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Name for the new entity (must be unique).",
                    },
                    "components": {
                        "type": "object",
                        "description": "Component configuration dict. Keys are component names (Transform, SpriteRenderer, ScriptComponent, etc.), values are the component data.",
                    },
                    "layer": {
                        "type": "string",
                        "description": "Layer name (default: 'Default').",
                    },
                    "groups": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of physics groups to add the entity to.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tags to add to the entity.",
                    },
                    "parent_name": {
                        "type": "string",
                        "description": "Name of parent entity (optional, for creating child entities).",
                    },
                },
                "required": ["entity_name", "components"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_component_to_entity",
            "description": "Add a component to an existing entity by editing the scene file directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Name of the entity to modify.",
                    },
                    "component_name": {
                        "type": "string",
                        "description": "Component type name (e.g. 'Rigidbody2D', 'BoxCollider2D', 'ScriptComponent').",
                    },
                    "component_data": {
                        "type": "object",
                        "description": "Component properties dict.",
                    },
                },
                "required": ["entity_name", "component_name", "component_data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_component",
            "description": "Modify properties of an existing component on an entity by editing the scene file directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Name of the entity to modify.",
                    },
                    "component_name": {
                        "type": "string",
                        "description": "Component type name.",
                    },
                    "property_updates": {
                        "type": "object",
                        "description": "Dict of property names and new values to update.",
                    },
                },
                "required": ["entity_name", "component_name", "property_updates"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_scenes",
            "description": "List all scene files in the project.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_scripts",
            "description": "List all Python script files in the project.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_config",
            "description": "Get the project configuration (game name, resolution, layers, groups, input actions).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_components",
            "description": "Get a list of all available component types that can be added to entities.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get information about currently active systems in the world.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ------------------------------------------------------------------
# Tool executor
# ------------------------------------------------------------------

class ToolExecutor:
    """Executes engine tools using callbacks wired to the editor state."""

    def __init__(self):
        self._scene_getter: Optional[Callable] = None
        self._project_path: str = ""
        self._selected_getter: Optional[Callable] = None
        self._scene_reload_callback: Optional[Callable] = None
        self.action_tracker: Optional[Any] = None  # AIActionTracker instance

    def set_scene_getter(self, getter: Callable):
        self._scene_getter = getter

    def set_project_path(self, path: str):
        self._project_path = path or ""

    def set_selected_entities_getter(self, getter: Callable):
        self._selected_getter = getter

    def set_scene_reload_callback(self, callback: Callable):
        """Set callback to trigger scene reload after file edits."""
        self._scene_reload_callback = callback

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool by name and return the result as a string."""
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            result = handler(**arguments)
            return json.dumps(result, default=str, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_list_entities(self, limit: int = 50) -> Dict[str, Any]:
        scene = self._get_scene()
        if not scene:
            return {"error": "No scene loaded."}

        entities = scene.world.entities[:limit]
        result = []
        for e in entities:
            comp_names = [type(c).__name__ for c in e.components.values()]
            result.append({
                "name": e.name,
                "layer": e.layer,
                "groups": list(e.groups),
                "tags": list(e.tags),
                "components": comp_names,
                "children": [c.name for c in e.children],
                "visible": e.is_visible(),
            })
        return {"entities": result, "total": len(scene.world.entities)}

    def _tool_get_entity_info(self, entity_name: str) -> Dict[str, Any]:
        scene = self._get_scene()
        if not scene:
            return {"error": "No scene loaded."}

        entity = scene.world.get_entity_by_name(entity_name)
        if not entity:
            return {"error": f"Entity '{entity_name}' not found."}

        components = {}
        for comp_type, comp in entity.components.items():
            props = self._extract_properties(comp)
            components[comp_type.__name__] = props

        return {
            "name": entity.name,
            "id": entity.id,
            "layer": entity.layer,
            "groups": list(entity.groups),
            "tags": list(entity.tags),
            "visible": entity.is_visible(),
            "parent": entity.parent.name if entity.parent else None,
            "children": [c.name for c in entity.children],
            "components": components,
        }

    def _tool_read_script(self, script_path: str) -> Dict[str, Any]:
        if not self._project_path:
            return {"error": "No project loaded."}

        full_path = os.path.join(self._project_path, script_path)
        if not os.path.exists(full_path):
            return {"error": f"Script not found: {script_path}"}
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"path": script_path, "content": content}
        except Exception as e:
            return {"error": f"Failed to read script: {e}"}

    def _tool_list_scenes(self) -> Dict[str, Any]:
        if not self._project_path:
            return {"error": "No project loaded."}
        scenes = []
        for root, _, files in os.walk(self._project_path):
            for f in files:
                if f.endswith(".scene"):
                    rel = os.path.relpath(os.path.join(root, f), self._project_path)
                    scenes.append(rel.replace("\\", "/"))
        return {"scenes": scenes}

    def _tool_list_scripts(self) -> Dict[str, Any]:
        if not self._project_path:
            return {"error": "No project loaded."}
        scripts = []
        for root, dirs, files in os.walk(self._project_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    rel = os.path.relpath(os.path.join(root, f), self._project_path)
                    scripts.append(rel.replace("\\", "/"))
        return {"scripts": scripts}

    def _tool_get_project_config(self) -> Dict[str, Any]:
        if not self._project_path:
            return {"error": "No project loaded."}
        config_path = os.path.join(self._project_path, "project.config")
        if not os.path.exists(config_path):
            return {"error": "project.config not found."}
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            relevant = {}
            for key in ("game_name", "resolution", "display", "layers", "groups",
                        "input_actions", "lighting", "background_color"):
                if key in config:
                    relevant[key] = config[key]
            return relevant
        except Exception as e:
            return {"error": f"Failed to read config: {e}"}

    def _tool_get_available_components(self) -> Dict[str, Any]:
        """Get a list of all component types."""
        try:
            import core.components
            components = []
            for name in dir(core.components):
                if not name.startswith("_") and name[0].isupper():
                    components.append(name)
            return {"components": sorted(components)}
        except Exception as e:
            return {"error": f"Failed to get components: {e}"}

    def _tool_get_system_info(self) -> Dict[str, Any]:
        """Get information about active systems."""
        scene = self._get_scene()
        if not scene or not scene.world:
            return {"error": "No scene or world loaded."}
            
        systems = []
        for sys in scene.world.systems:
            systems.append({
                "name": type(sys).__name__,
                "priority": sys.priority,
                "phase": sys.update_phase
            })
            
        return {
            "system_count": len(systems),
            "systems": sorted(systems, key=lambda s: (s["phase"], s["priority"]))
        }

    def _tool_write_script(self, script_path: str, content: str) -> Dict[str, Any]:
        """Create or overwrite a script file."""
        if not self._project_path:
            return {"error": "No project loaded."}
        full_path = os.path.join(self._project_path, script_path)
        try:
            if self.action_tracker:
                self.action_tracker.snapshot_file(full_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": script_path, "message": f"Script written to {script_path}"}
        except Exception as e:
            return {"error": f"Failed to write script: {e}"}

    def _tool_edit_script(self, script_path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """Edit an existing script file."""
        if not self._project_path:
            return {"error": "No project loaded."}
        full_path = os.path.join(self._project_path, script_path)
        if not os.path.exists(full_path):
            return {"error": f"Script not found: {script_path}"}
        try:
            if self.action_tracker:
                self.action_tracker.snapshot_file(full_path)
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            if old_text not in content:
                return {"error": "old_text not found in file"}
            content = content.replace(old_text, new_text, 1)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "success": True,
                "path": script_path,
                "message": f"Script edited: {script_path}",
                "diff": {
                    "old_text": old_text,
                    "new_text": new_text
                }
            }
        except Exception as e:
            return {"error": f"Failed to edit script: {e}"}

    def _tool_read_scene(self, scene_path: str) -> Dict[str, Any]:
        """Read the raw JSON content of a scene file."""
        if not self._project_path:
            return {"error": "No project loaded."}
        full_path = os.path.join(self._project_path, scene_path)
        if not os.path.exists(full_path):
            return {"error": f"Scene not found: {scene_path}"}
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            return {"path": scene_path, "content": content}
        except Exception as e:
            return {"error": f"Failed to read scene: {e}"}

    def _tool_create_entity(self, entity_name: str, components: Dict[str, Any],
                            layer: str = "Default", groups: List[str] = None,
                            tags: List[str] = None, parent_name: str = None) -> Dict[str, Any]:
        """Create a new entity by editing the current scene file."""
        scene = self._get_scene()
        if not scene:
            return {"error": "No scene loaded."}

        # Check for duplicate name
        if scene.world.get_entity_by_name(entity_name):
            return {"error": f"Entity '{entity_name}' already exists."}

        # Find parent if specified
        parent_id = None
        if parent_name:
            parent = scene.world.get_entity_by_name(parent_name)
            if not parent:
                return {"error": f"Parent entity '{parent_name}' not found."}
            parent_id = parent.id

        # Generate new entity ID
        import random
        new_id = f"ent_{random.randint(100000, 999999)}"

        # Ensure Transform is present
        if "Transform" not in components:
            components["Transform"] = {"x": 0, "y": 0, "rotation": 0, "scale_x": 1.0, "scale_y": 1.0}

        entity_data = {
            "id": new_id,
            "name": entity_name,
            "layer": layer,
            "groups": list(groups) if groups else [],
            "tags": list(tags) if tags else [],
            "parent": parent_id,
            "visible": True,
            "process_physics": True,
            "components": components
        }

        # Get current scene file path and update it
        scene_path = getattr(scene, '_file_path', None)
        if not scene_path:
            return {"error": "Cannot determine scene file path."}

        full_path = os.path.join(self._project_path, scene_path)
        try:
            if self.action_tracker:
                self.action_tracker.snapshot_file(full_path)
            with open(full_path, "r", encoding="utf-8") as f:
                scene_data = json.load(f)

            if "entities" not in scene_data:
                scene_data["entities"] = []

            scene_data["entities"].append(entity_data)

            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(scene_data, f, indent=4)

            # Reload scene to reflect changes
            self._reload_scene(full_path)

            return {
                "success": True,
                "entity_name": entity_name,
                "id": new_id,
                "message": f"Entity '{entity_name}' created in scene."
            }
        except Exception as e:
            return {"error": f"Failed to create entity: {e}"}

    def _tool_add_component_to_entity(self, entity_name: str, component_name: str,
                                       component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a component to an existing entity."""
        scene = self._get_scene()
        if not scene:
            return {"error": "No scene loaded."}

        scene_path = getattr(scene, '_file_path', None)
        if not scene_path:
            return {"error": "Cannot determine scene file path."}

        full_path = os.path.join(self._project_path, scene_path)
        try:
            if self.action_tracker:
                self.action_tracker.snapshot_file(full_path)
            with open(full_path, "r", encoding="utf-8") as f:
                scene_data = json.load(f)

            # Find entity
            entity_found = False
            for entity in scene_data.get("entities", []):
                if entity.get("name") == entity_name:
                    if "components" not in entity:
                        entity["components"] = {}
                    entity["components"][component_name] = component_data
                    entity_found = True
                    break

            if not entity_found:
                return {"error": f"Entity '{entity_name}' not found."}

            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(scene_data, f, indent=4)

            self._reload_scene(full_path)

            return {
                "success": True,
                "message": f"Component '{component_name}' added to '{entity_name}'."
            }
        except Exception as e:
            return {"error": f"Failed to add component: {e}"}

    def _tool_modify_component(self, entity_name: str, component_name: str,
                               property_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Modify properties of an existing component."""
        scene = self._get_scene()
        if not scene:
            return {"error": "No scene loaded."}

        scene_path = getattr(scene, '_file_path', None)
        if not scene_path:
            return {"error": "Cannot determine scene file path."}

        full_path = os.path.join(self._project_path, scene_path)
        try:
            if self.action_tracker:
                self.action_tracker.snapshot_file(full_path)
            with open(full_path, "r", encoding="utf-8") as f:
                scene_data = json.load(f)

            # Find entity and component
            entity_found = False
            for entity in scene_data.get("entities", []):
                if entity.get("name") == entity_name:
                    if "components" not in entity or component_name not in entity["components"]:
                        return {"error": f"Component '{component_name}' not found on '{entity_name}'."}

                    # Update properties
                    for key, value in property_updates.items():
                        entity["components"][component_name][key] = value
                    entity_found = True
                    break

            if not entity_found:
                return {"error": f"Entity '{entity_name}' not found."}

            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(scene_data, f, indent=4)

            self._reload_scene(full_path)

            return {
                "success": True,
                "message": f"Component '{component_name}' on '{entity_name}' modified."
            }
        except Exception as e:
            return {"error": f"Failed to modify component: {e}"}

    def _reload_scene(self, full_path: str):
        """Helper to trigger scene reload in the editor."""
        if self._scene_reload_callback:
            try:
                self._scene_reload_callback(full_path)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_scene(self):
        if self._scene_getter:
            try:
                return self._scene_getter()
            except Exception:
                return None
        return None

    def _extract_properties(self, comp) -> Dict[str, Any]:
        """Extract serializable properties from a component."""
        skip = {"entity", "instance", "started", "image", "_module_key",
                "_loaded_script_path", "_loaded_class_name", "_loaded_mtime",
                "_coroutine_manager", "_tween_manager", "_events",
                "_previous_transform_state", "_current_transform_state"}
        props = {}
        for key in dir(comp):
            if key.startswith("_") or key in skip:
                continue
            try:
                val = getattr(comp, key)
                if callable(val):
                    continue
                # Make serializable
                if hasattr(val, '__dict__'):
                    val = str(val)
                props[key] = val
            except Exception:
                pass
        return props
