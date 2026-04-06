from core.ecs import Component
import os
from core.logger import get_logger
from core.coroutine_manager import CoroutineManager
from core.tween import TweenManager

_script_logger = get_logger("script")

class ScriptComponent(Component):
    """
    Component for attaching Python scripts to entities.
    
    Scripts automatically receive the following injected attributes:
    - entity: The entity this script is attached to
    - logger: A logger instance with the name "script.<ClassName>"
    
    Example:
        class MyScript:
            def on_start(self):
                # logger is automatically available!
                self.logger.info("Script started")
                print(self.entity.name)  # entity is also available
    """
    def __init__(self, script_path: str = "", class_name: str = ""):
        self.script_path = script_path
        self.class_name = class_name
        self.instance = None
        self.started = False
        self._module_key = ""
        self._loaded_script_path = ""
        self._loaded_class_name = ""
        self._loaded_mtime = None
        self._coroutine_manager = CoroutineManager()
        self._tween_manager = TweenManager()
        
    def find(self, name: str):
        """Finds an entity by name in the current world."""
        if self.entity and self.entity.world:
            return self.entity.world.get_entity_by_name(name)
        return None

    def get_children(self, name: str) -> list:
        """Returns the children list of an entity found by name."""
        entity = self.find(name)
        if entity:
            return entity.children
        return []

    def destroy(self):
        if self.entity:
            self.entity.destroy()

    def hide(self):
        if self.entity:
            self.entity.hide()

    def show(self):
        if self.entity:
            self.entity.show()

    def process_physics(self, enabled: bool):
        if self.entity:
            self.entity.process_physics(enabled)

    def change_scene(self, scene_name: str):
        if not self.entity or not self.entity.world:
            return
        self.entity.world.request_scene_change(scene_name)

    def call_group(self, group_name: str, method_name: str, *args, **kwargs):
        """
        Calls a method on all script components of entities in the specified group.
        """
        if not self.entity or not self.entity.world:
            return
            
        entities = self.entity.world.get_entities_in_group(group_name)
        for entity in entities:
            script = entity.get_component(ScriptComponent)
            if script and script.instance and hasattr(script.instance, method_name):
                try:
                    method = getattr(script.instance, method_name)
                    if callable(method):
                        method(*args, **kwargs)
                except Exception as e:
                    _script_logger.error("Error calling group method", method=method_name, entity=entity.name, group=group_name, error=str(e))

    # Event System Helpers
    
    def subscribe_to_event(self, event_name: str, callback, target_entity=None):
        """
        Subscribe to an event.
        :param event_name: Name of the event.
        :param callback: Method to call.
        :param target_entity: If provided, subscribes to that entity's event. 
                              If None, subscribes to the global World event.
        """
        if target_entity:
            target_entity.events.subscribe(event_name, callback)
        elif self.entity and self.entity.world:
            self.entity.world.events.subscribe(event_name, callback)

    def unsubscribe_from_event(self, event_name: str, callback, target_entity=None):
        """
        Unsubscribe from an event.
        """
        if target_entity:
            target_entity.events.unsubscribe(event_name, callback)
        elif self.entity and self.entity.world:
            self.entity.world.events.unsubscribe(event_name, callback)

    def emit_global_event(self, event_name: str, *args, **kwargs):
        """Emit an event globally to the World (queued, 1-frame latency)."""
        if self.entity and self.entity.world:
            self.entity.world.events.emit(event_name, *args, **kwargs)

    def emit_local_event(self, event_name: str, *args, **kwargs):
        """Emit an event on this entity (queued, 1-frame latency)."""
        if self.entity:
            self.entity.events.emit(event_name, *args, **kwargs)

    def emit_global_event_immediate(self, event_name: str, *args, **kwargs):
        """Emit an event globally and dispatch it synchronously (zero latency)."""
        if self.entity and self.entity.world:
            self.entity.world.events.emit_immediate(event_name, *args, **kwargs)

    def emit_local_event_immediate(self, event_name: str, *args, **kwargs):
        """Emit an event on this entity and dispatch it synchronously (zero latency)."""
        if self.entity:
            self.entity.events.emit_immediate(event_name, *args, **kwargs)

    def _resolve_prefab_path(self, prefab_path: str) -> str:
        if not prefab_path:
            return ""
        normalized = os.path.normpath(prefab_path)
        if os.path.isabs(normalized):
            return normalized
        candidates = []
        script_component = self.entity.get_component(ScriptComponent) if self.entity else None
        script_file = script_component.script_path if script_component else ""
        if script_file:
            candidates.append(os.path.normpath(os.path.join(os.path.dirname(script_file), normalized)))
        project_root = os.environ.get("AXISPY_PROJECT_PATH", "")
        if project_root:
            candidates.append(os.path.normpath(os.path.join(project_root, normalized)))
        candidates.append(os.path.normpath(os.path.join(os.getcwd(), normalized)))
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return normalized

    def instantiate_prefab(self, prefab_path: str, parent=None, name: str = None,
                           x: float = None, y: float = None, rotation: float = None,
                           scale_x: float = None, scale_y: float = None):
        if not self.entity or not self.entity.world:
            return None
        resolved_path = self._resolve_prefab_path(prefab_path)
        if not resolved_path or not os.path.exists(resolved_path):
            return None
        try:
            with open(resolved_path, "r") as f:
                from core.serializer import SceneSerializer
                spawned = SceneSerializer.entity_from_json(f.read(), self.entity.world)
            if not spawned:
                return None
            if parent:
                parent.add_child(spawned)
            if name:
                spawned.name = name
            from core.components import Transform
            transform = spawned.get_component(Transform)
            if transform:
                if x is not None:
                    transform.x = x
                if y is not None:
                    transform.y = y
                if rotation is not None:
                    transform.rotation = rotation
                if scale_x is not None:
                    transform.scale_x = scale_x
                if scale_y is not None:
                    transform.scale_y = scale_y
            return spawned
        except Exception:
            return None

    def spawn_prefab(self, prefab_path: str, parent=None, name: str = None,
                     x: float = None, y: float = None, rotation: float = None,
                     scale_x: float = None, scale_y: float = None):
        return self.instantiate_prefab(
            prefab_path=prefab_path,
            parent=parent,
            name=name,
            x=x,
            y=y,
            rotation=rotation,
            scale_x=scale_x,
            scale_y=scale_y
        )
    
    def start_coroutine(self, gen):
        """Schedule a coroutine (generator) on this script's coroutine manager."""
        self._coroutine_manager.start(gen)

    def stop_coroutines(self):
        """Cancel all running coroutines on this script."""
        self._coroutine_manager.stop_all()

    def tick_coroutines(self, dt: float):
        """Advance all coroutines by dt. Called by ScriptSystem each frame."""
        self._coroutine_manager.tick(dt)

    def tween(self, entity, attr_path: str, target: float,
              start: float | None = None, duration: float = 1.0,
              easing=None, on_complete=None, loops: int = 0,
              yoyo: bool = False):
        """Create a tween animation on an entity property."""
        return self._tween_manager.tween(
            entity, attr_path, target, start=start, duration=duration,
            easing=easing, on_complete=on_complete, loops=loops, yoyo=yoyo
        )

    def cancel_tweens(self, entity=None):
        """Cancel tweens. If entity is given, only that entity's tweens."""
        self._tween_manager.cancel_all(entity)

    def tick_tweens(self, dt: float):
        """Advance all tweens by dt. Called by ScriptSystem each frame."""
        self._tween_manager.tick(dt)

    def _inject_methods_to_instance(self):
        """Inject helper methods into the script instance."""
        if not self.instance:
            return
            
        # Inject event helper methods
        self.instance.subscribe_to_event = self.subscribe_to_event
        self.instance.unsubscribe_from_event = self.unsubscribe_from_event
        self.instance.emit_global_event = self.emit_global_event
        self.instance.emit_local_event = self.emit_local_event
        self.instance.emit_global_event_immediate = self.emit_global_event_immediate
        self.instance.emit_local_event_immediate = self.emit_local_event_immediate
        
        # Inject other helper methods
        self.instance.find = self.find
        self.instance.get_children = self.get_children
        self.instance.destroy = self.destroy
        self.instance.hide = self.hide
        self.instance.show = self.show
        self.instance.process_physics = self.process_physics
        self.instance.change_scene = self.change_scene
        self.instance.call_group = self.call_group
        self.instance.instantiate_prefab = self.instantiate_prefab
        self.instance.spawn_prefab = self.spawn_prefab
        self.instance.start_coroutine = self.start_coroutine
        self.instance.stop_coroutines = self.stop_coroutines
        self.instance.tween = self.tween
        self.instance.cancel_tweens = self.cancel_tweens
