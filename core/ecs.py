import time
import uuid
from typing import Dict, List, Type, Any
from core.event_system import EventSystem
from core.logger import get_logger

_world_logger = get_logger("world")

class Component:
    """Base class for all components"""
    def on_destroy(self):
        return None

    def __repr__(self):
        return f"<{type(self).__name__}>"

class Entity:
    def __init__(self, name: str = "GameObject"):
        self.id = str(uuid.uuid4())
        self.name = name
        self.components: Dict[Type[Component], Component] = {}
        self.children: List['Entity'] = []
        self.parent: 'Entity' = None
        self.world: 'World' = None
        self._events: EventSystem = None
        self._previous_transform_state = None
        self._current_transform_state = None
        self._visible = True
        self._physics_processing = True
        self.layer: str = "Default"
        self.groups: set[str] = set()
        self.tags: set[str] = set()

    @property
    def events(self) -> EventSystem:
        if self._events is None:
            self._events = EventSystem()
        return self._events

    @events.setter
    def events(self, value):
        self._events = value

    def add_group(self, group: str):
        self.groups.add(group)
        if self.world:
            self.world.on_entity_group_changed(self, group, added=True)

    def remove_group(self, group: str):
        if group in self.groups:
            self.groups.remove(group)
            if self.world:
                self.world.on_entity_group_changed(self, group, added=False)
    
    def has_group(self, group: str) -> bool:
        return group in self.groups

    def add_tag(self, tag: str):
        """Add a lightweight tag (no world indexing)."""
        self.tags.add(tag)

    def remove_tag(self, tag: str):
        """Remove a tag if present."""
        self.tags.discard(tag)

    def has_tag(self, tag: str) -> bool:
        """Check if the entity has a tag."""
        return tag in self.tags

    def set_layer(self, layer: str):
        old_layer = self.layer
        self.layer = layer
        if self.world and old_layer != layer:
            self.world.on_entity_layer_changed(self, old_layer, layer)
            
        for child in self.children:
            child.set_layer(layer)

    def add_component(self, component: Component):
        component.entity = self
        self.components[type(component)] = component
        if self.world:
            self.world.on_component_added(self, component)
        return component

    def get_component(self, component_type: Type[Component]) -> Any:
        return self.components.get(component_type)

    def get_components(self, component_type: Type[Component]) -> List[Any]:
        """Returns a list of all components matching *component_type* (including subclasses).

        ``get_component()`` only returns the exact-type entry.  This method
        walks every attached component and collects those that are instances of
        *component_type*, which is useful when an entity may carry several
        components that share a common base class (e.g. multiple colliders).
        """
        return [c for c in self.components.values() if isinstance(c, component_type)]

    def remove_component(self, component_type: Type[Component]):
        if component_type in self.components:
            component = self.components[component_type]
            del self.components[component_type]
            if self.world:
                self.world._notify_component_destroy(self, component)
                self.world.on_component_removed(self, component)

    def add_child(self, child: 'Entity'):
        child.parent = self
        self.children.append(child)

    def remove_child(self, child: 'Entity'):
        try:
            self.children.remove(child)
            child.parent = None
        except ValueError:
            pass

    def get_child(self, name: str) -> 'Entity':
        """Returns the first child with the given name."""
        for child in self.children:
            if child.name == name:
                return child
        return None
    
    def get_children(self) -> list:
        """Returns the children list of this entity."""
        return self.children
    
    def get_children_copy(self) -> list:
        """Returns a copy of the children list."""
        return self.children.copy()

    def hide(self):
        was_visible = self._visible
        self._visible = False
        if was_visible:
            self._notify_visibility_change(False)
        for child in self.children:
            child.hide()

    def show(self):
        was_visible = self._visible
        self._visible = True
        if not was_visible:
            self._notify_visibility_change(True)
        for child in self.children:
            child.show()

    def _notify_visibility_change(self, enabled: bool):
        """Call on_enable/on_disable on any attached script instance."""
        from core.components.script import ScriptComponent
        script = self.components.get(ScriptComponent)
        if script and script.instance:
            method_name = "on_enable" if enabled else "on_disable"
            handler = getattr(script.instance, method_name, None)
            if handler:
                try:
                    handler()
                except Exception as e:
                    _world_logger.warning(
                        "Error in script callback",
                        entity=self.name,
                        method=method_name,
                        error=str(e)
                    )

    def is_visible(self) -> bool:
        return self._visible

    def process_physics(self, enabled: bool):
        self._physics_processing = bool(enabled)
        for child in self.children:
            child.process_physics(enabled)

    def is_physics_processing(self) -> bool:
        return self._physics_processing

    def __repr__(self):
        comp_names = ", ".join(type(c).__name__ for c in self.components.values())
        return f"<Entity '{self.name}' id={self.id[:8]} [{comp_names}]>"

    def destroy(self) -> bool:
        if self.world:
            self.world.destroy_entity(self)
            return True
        return False

class System:
    """Base class for all systems"""
    # Subclasses can set this to a tuple of Component types.
    # If set, the system's update() will be skipped when none of
    # the listed component types have any entities in the world.
    # An empty tuple means the system always runs.
    required_components: tuple[type, ...] = ()

    def __init__(self):
        self.world: 'World' = None
        self.update_phase = "simulation"
        self.priority: int = 0

    def update(self, dt: float, entities: List[Entity]):
        pass

    def on_added_to_world(self):
        """Called after the system is added to a World and self.world is set."""
        pass

    def on_removed_from_world(self):
        """Called just before the system is removed from a World."""
        pass

class EntityQuery:
    """Fluent query builder for filtering entities in a World."""

    def __init__(self, world: 'World'):
        self._world = world
        self._component_types: list[type] = []
        self._groups: list[str] = []
        self._tags: list[str] = []
        self._visible_only: bool = False
        self._with_physics: bool = False

    def with_component(self, *component_types) -> 'EntityQuery':
        """Filter to entities that have all listed component types."""
        self._component_types.extend(component_types)
        return self

    def in_group(self, group: str) -> 'EntityQuery':
        """Filter to entities belonging to *group*."""
        self._groups.append(group)
        return self

    def with_tag(self, tag: str) -> 'EntityQuery':
        """Filter to entities that have *tag*."""
        self._tags.append(tag)
        return self

    def visible(self) -> 'EntityQuery':
        """Filter to visible entities only."""
        self._visible_only = True
        return self

    def physics_enabled(self) -> 'EntityQuery':
        """Filter to entities with physics processing enabled."""
        self._with_physics = True
        return self

    def _resolve(self) -> list:
        """Execute the query and return matching entities."""
        w = self._world
        # Start with component-filtered set if any, else all entities
        if self._component_types:
            candidates = set(w.get_entities_with(*self._component_types))
        else:
            candidates = set(w.entities)

        # Group filter
        for group in self._groups:
            group_set = w.groups.get(group)
            if not group_set:
                return []
            candidates &= group_set

        # Tag filter
        if self._tags:
            candidates = {e for e in candidates if all(t in e.tags for t in self._tags)}

        # Visibility filter
        if self._visible_only:
            candidates = {e for e in candidates if e.is_visible()}

        # Physics filter
        if self._with_physics:
            candidates = {e for e in candidates if e.is_physics_processing()}

        return list(candidates)

    def all(self) -> list:
        """Return all matching entities."""
        return self._resolve()

    def first(self):
        """Return the first matching entity, or None."""
        results = self._resolve()
        return results[0] if results else None

    def count(self) -> int:
        """Return the number of matching entities."""
        return len(self._resolve())

class World:
    """Manages all entities and systems in a scene"""
    def __init__(self):
        self.entities: List[Entity] = []
        self._entity_index: Dict[Entity, int] = {}
        self._entity_set: set[Entity] = set()
        self.systems: List[System] = []
        self.events = EventSystem()
        self._component_cache: Dict[Type[Component], set[Entity]] = {}
        self._entity_id_index: Dict[str, Entity] = {}
        self._entity_name_index: Dict[str, List[Entity]] = {}
        self._transform_prev_states: Dict[str, tuple[float, float, float, float, float]] = {}
        self._transform_curr_states: Dict[str, tuple[float, float, float, float, float]] = {}
        self._transform_component_type = None
        
        self.layers: List[str] = ["Default"]
        self.groups: Dict[str, set[Entity]] = {}
        self._requested_scene_name: str = ""
        self.physics_group_order: List[str] = []
        self.physics_collision_matrix: Dict[str, List[str]] = {}
        self._profiling_enabled: bool = False
        self._system_timings: Dict[str, float] = {}

    def on_entity_layer_changed(self, entity: Entity, old_layer: str, new_layer: str):
        pass

    def on_entity_group_changed(self, entity: Entity, group: str, added: bool):
        if added:
            if group not in self.groups:
                self.groups[group] = set()
            self.groups[group].add(entity)
        else:
            if group in self.groups:
                self.groups[group].discard(entity)
                if not self.groups[group]:
                    del self.groups[group]

    def get_entities_in_group(self, group: str) -> List[Entity]:
        return list(self.groups.get(group, []))

    def request_scene_change(self, scene_name: str):
        """Request a scene change. The player loop will process this between frames."""
        requested = str(scene_name or "").strip()
        if requested:
            self._requested_scene_name = requested

    def _register_entity(self, entity: Entity):
        """Register an entity in all internal indices. Called by create_entity
        and can be called externally when re-adding an entity (e.g. undo)."""
        self._entity_set.add(entity)
        self._entity_id_index[entity.id] = entity
        if entity.name not in self._entity_name_index:
            self._entity_name_index[entity.name] = []
        if entity not in self._entity_name_index[entity.name]:
            self._entity_name_index[entity.name].append(entity)

    def _sync_entity_indices(self):
        """Rebuild entity -> index map after manual list inserts (e.g. editor undo)."""
        self._entity_index = {e: i for i, e in enumerate(self.entities)}

    def _remove_entity_from_list(self, entity: Entity) -> bool:
        """O(1) removal: swap with last element and pop. Preserves set membership elsewhere."""
        idx = self._entity_index.get(entity)
        if idx is None:
            try:
                idx = self.entities.index(entity)
            except ValueError:
                return False
        last_idx = len(self.entities) - 1
        if last_idx < 0:
            return False
        last_entity = self.entities[last_idx]
        if idx != last_idx:
            self.entities[idx] = last_entity
            self._entity_index[last_entity] = idx
        self.entities.pop()
        self._entity_index.pop(entity, None)
        return True

    def create_entity(self, name: str = "GameObject") -> Entity:
        entity = Entity(name)
        entity.world = self
        self.entities.append(entity)
        self._entity_index[entity] = len(self.entities) - 1
        self._register_entity(entity)
        
        # Register existing groups if any
        for group in entity.groups:
            self.on_entity_group_changed(entity, group, added=True)

        # Add existing components to cache (though usually empty)
        for component in entity.components.values():
            self.on_component_added(entity, component)
        return entity

    def destroy_entity(self, entity: Entity):
        if entity not in self._entity_set:
            return
        # Also destroy children recursively
        for child in list(entity.children):
            self.destroy_entity(child)
        
        # Remove from groups
        for group in list(entity.groups):
            self.on_entity_group_changed(entity, group, added=False)
        
        # Remove from cache
        for component in list(entity.components.values()):
            self._notify_component_destroy(entity, component)
            self.on_component_removed(entity, component)
            
        if entity.parent:
            entity.parent.remove_child(entity)
        self._remove_entity_from_list(entity)
        self._entity_set.discard(entity)
        self._entity_id_index.pop(entity.id, None)
        # Remove from name index
        name_list = self._entity_name_index.get(entity.name)
        if name_list is not None:
            try:
                name_list.remove(entity)
            except ValueError:
                pass
            if not name_list:
                del self._entity_name_index[entity.name]
        self._transform_prev_states.pop(entity.id, None)
        self._transform_curr_states.pop(entity.id, None)

    def _notify_component_destroy(self, entity: Entity, component: Component):
        try:
            destroy_handler = getattr(component, "on_destroy", None)
            if callable(destroy_handler):
                destroy_handler()
        except Exception as e:
            _world_logger.warning(
                "Error in component on_destroy",
                entity=entity.name,
                component=type(component).__name__,
                error=str(e)
            )
        script_instance = getattr(component, "instance", None)
        if script_instance is None:
            return
        try:
            script_destroy = getattr(script_instance, "on_destroy", None)
            if callable(script_destroy):
                script_destroy()
        except Exception as e:
            _world_logger.warning(
                "Error in script on_destroy",
                entity=entity.name,
                error=str(e)
            )

    def on_component_added(self, entity: Entity, component: Component):
        for comp_type in self._get_component_cache_types(component):
            if comp_type not in self._component_cache:
                self._component_cache[comp_type] = set()
            self._component_cache[comp_type].add(entity)
        if self._is_transform_component(component):
            state = (
                float(component.x),
                float(component.y),
                float(component.rotation),
                float(component.scale_x),
                float(component.scale_y)
            )
            self._transform_prev_states[entity.id] = state
            self._transform_curr_states[entity.id] = state
            entity._previous_transform_state = state
            entity._current_transform_state = state

    def on_component_removed(self, entity: Entity, component: Component):
        for comp_type in self._get_component_cache_types(component):
            if comp_type in self._component_cache and entity in self._component_cache[comp_type]:
                self._component_cache[comp_type].remove(entity)
        if self._is_transform_component(component):
            self._transform_prev_states.pop(entity.id, None)
            self._transform_curr_states.pop(entity.id, None)
            entity._previous_transform_state = None
            entity._current_transform_state = None

    def get_entities_with(self, *component_types: Type[Component]) -> List[Entity]:
        """
        Returns a list of entities that have all the specified components.
        Uses cached sets for O(1) lookups per component type.
        """
        if not component_types:
            return self.entities
        
        first_type = component_types[0]
        first_set = self._component_cache.get(first_type)
        if not first_set:
            return []

        # Fast path: single component type — no copy needed
        if len(component_types) == 1:
            return list(first_set)
        
        # Multi-component: start with smallest set to minimize work
        smallest = first_set
        for comp_type in component_types[1:]:
            s = self._component_cache.get(comp_type)
            if not s:
                return []
            if len(s) < len(smallest):
                smallest = s

        # Intersect against smallest set
        if smallest is first_set:
            result_set = first_set.copy()
            for comp_type in component_types[1:]:
                result_set &= self._component_cache.get(comp_type, set())
        else:
            result_set = smallest.copy()
            for comp_type in component_types:
                s = self._component_cache.get(comp_type, set())
                if s is not smallest:
                    result_set &= s

        return list(result_set)

    def query(self) -> 'EntityQuery':
        """Return a fluent query builder for filtering entities."""
        return EntityQuery(self)

    def add_system(self, system: System):
        if system in self.systems:
            return
        system.world = self
        self.systems.append(system)
        self._sort_systems()
        system.on_added_to_world()

    def remove_system(self, system: System) -> bool:
        """Remove a system from the world. Returns True if removed."""
        if system not in self.systems:
            return False
        system.on_removed_from_world()
        self.systems.remove(system)
        system.world = None
        return True

    def get_system(self, system_type: Type['System']):
        """Return the first system matching the given type, or None."""
        for system in self.systems:
            if isinstance(system, system_type):
                return system
        return None

    def _sort_systems(self):
        """Sort systems by (update_phase, priority) for deterministic ordering."""
        phase_order = {"simulation": 0, "render": 1}
        self.systems.sort(
            key=lambda s: (phase_order.get(getattr(s, "update_phase", "simulation"), 0),
                           getattr(s, "priority", 0))
        )

    def get_entity_by_id(self, entity_id: str) -> Entity:
        entity = self._entity_id_index.get(entity_id)
        if entity is not None and entity in self._entity_set and entity.id == entity_id:
            return entity
        self._rebuild_entity_id_index()
        return self._entity_id_index.get(entity_id)

    def get_entity_by_name(self, name: str) -> Entity:
        """Returns the first entity found with the given name."""
        name_list = self._entity_name_index.get(name)
        if name_list:
            return name_list[0]
        return None

    def get_entities_by_name(self, name: str) -> List[Entity]:
        """Returns all entities with the given name."""
        return list(self._entity_name_index.get(name, []))

    def update(self, dt: float):
        self.simulate(dt)
        self.render(dt, 1.0)

    def _system_has_work(self, system: System) -> bool:
        """Return False if the system declares required_components and none exist."""
        reqs = system.required_components
        if not reqs:
            return True
        cache = self._component_cache
        for comp_type in reqs:
            if cache.get(comp_type):
                return True
        return False

    def simulate(self, dt: float):
        if dt <= 0.0:
            return
        self._prepare_simulation_step()
        profiling = self._profiling_enabled
        for system in self.systems:
            if getattr(system, "update_phase", "simulation") == "render":
                continue
            if not self._system_has_work(system):
                continue
            try:
                if profiling:
                    t0 = time.perf_counter()
                system.update(dt, self.entities)
                if profiling:
                    elapsed = time.perf_counter() - t0
                    self._system_timings[type(system).__name__] = elapsed
            except Exception as e:
                _world_logger.error(
                    "System update failed",
                    system=type(system).__name__,
                    phase="simulation",
                    error=str(e)
                )
        self._finalize_simulation_step()

    def render(self, dt: float, interpolation_alpha: float = 1.0):
        alpha = max(0.0, min(1.0, float(interpolation_alpha)))
        profiling = self._profiling_enabled
        for system in self.systems:
            if getattr(system, "update_phase", "simulation") != "render":
                continue
            if hasattr(system, "interpolation_alpha"):
                system.interpolation_alpha = alpha
            if not self._system_has_work(system):
                continue
            try:
                if profiling:
                    t0 = time.perf_counter()
                system.update(dt, self.entities)
                if profiling:
                    elapsed = time.perf_counter() - t0
                    self._system_timings[type(system).__name__] = elapsed
            except Exception as e:
                _world_logger.error(
                    "System update failed",
                    system=type(system).__name__,
                    phase="render",
                    error=str(e)
                )

    def enable_profiling(self):
        """Start recording per-system execution times each tick."""
        self._profiling_enabled = True
        self._system_timings.clear()

    def disable_profiling(self):
        """Stop recording per-system execution times."""
        self._profiling_enabled = False

    def get_system_timings(self) -> Dict[str, float]:
        """Return the latest per-system timing dict (system name → seconds)."""
        return dict(self._system_timings)

    def sync_interpolation_state(self):
        snapshot = self._capture_transform_snapshot()
        self._transform_prev_states = snapshot.copy()
        self._transform_curr_states = snapshot.copy()
        for entity in self.entities:
            state = snapshot.get(entity.id)
            entity._previous_transform_state = state
            entity._current_transform_state = state

    def get_interpolated_transform(self, entity: Entity, alpha: float):
        transform = self._get_entity_transform(entity)
        if not transform:
            return None
        curr = self._transform_curr_states.get(entity.id)
        if curr is None:
            curr = (
                float(transform.x),
                float(transform.y),
                float(transform.rotation),
                float(transform.scale_x),
                float(transform.scale_y)
            )
        prev = self._transform_prev_states.get(entity.id, curr)
        t = max(0.0, min(1.0, float(alpha)))
        return (
            prev[0] + ((curr[0] - prev[0]) * t),
            prev[1] + ((curr[1] - prev[1]) * t),
            self._lerp_angle(prev[2], curr[2], t),
            prev[3] + ((curr[3] - prev[3]) * t),
            prev[4] + ((curr[4] - prev[4]) * t)
        )

    def _prepare_simulation_step(self):
        if not self._transform_curr_states:
            self.sync_interpolation_state()
            return
        self._transform_prev_states = self._transform_curr_states.copy()
        transform_type = self._get_transform_component_type()
        for entity in self._component_cache.get(transform_type, set()):
            entity._previous_transform_state = self._transform_prev_states.get(entity.id)

    def _finalize_simulation_step(self):
        snapshot = self._capture_transform_snapshot()
        self._transform_curr_states = snapshot.copy()
        transform_type = self._get_transform_component_type()
        for entity in self._component_cache.get(transform_type, set()):
            entity._current_transform_state = snapshot.get(entity.id)

    def _capture_transform_snapshot(self):
        snapshot: Dict[str, tuple[float, float, float, float, float]] = {}
        transform_type = self._get_transform_component_type()
        transform_entities = self._component_cache.get(transform_type, set())
        for entity in transform_entities:
            transform = entity.components.get(transform_type)
            if transform is None:
                continue
            snapshot[entity.id] = (
                float(transform.x),
                float(transform.y),
                float(transform.rotation),
                float(transform.scale_x),
                float(transform.scale_y)
            )
        return snapshot

    def _lerp_angle(self, start: float, end: float, t: float):
        delta = ((end - start + 180.0) % 360.0) - 180.0
        return start + (delta * t)

    def _get_transform_component_type(self):
        if self._transform_component_type is None:
            from core.components import Transform
            self._transform_component_type = Transform
        return self._transform_component_type

    def _is_transform_component(self, component: Component):
        return isinstance(component, self._get_transform_component_type())

    def _get_entity_transform(self, entity: Entity):
        return entity.get_component(self._get_transform_component_type())

    def _get_component_cache_types(self, component: Component):
        cache_types = []
        for base_type in type(component).mro():
            if not isinstance(base_type, type) or base_type is object:
                continue
            if not issubclass(base_type, Component):
                continue
            cache_types.append(base_type)
            if base_type is Component:
                break
        return cache_types

    def _rebuild_entity_id_index(self):
        index: Dict[str, Entity] = {}
        for entity in self.entities:
            index[entity.id] = entity
        self._entity_id_index = index
