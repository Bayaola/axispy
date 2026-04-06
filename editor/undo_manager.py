from core.components import Transform, SpriteRenderer
from core.components import TilemapComponent

class Command:
    def execute(self):
        raise NotImplementedError
    
    def undo(self):
        raise NotImplementedError
    
    def redo(self):
        self.execute()

class UndoManager:
    def __init__(self, main_window=None):
        self.undo_stack = []
        self.redo_stack = []
        self.max_stack = 50
        self.main_window = main_window

    def push(self, command):
        self.undo_stack.append(command)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_stack:
            self.undo_stack.pop(0)
        # print(f"Pushed command: {type(command).__name__}")

    def undo(self):
        if not self.undo_stack:
            return
        
        command = self.undo_stack.pop()
        try:
            command.undo()
            self.redo_stack.append(command)
            # print(f"Undid {type(command).__name__}")
            if self.main_window:
                self.main_window.hierarchy_dock.refresh()
                # Update inspector if selection matches
                if self.main_window.inspector_dock.current_entities:
                    # Re-set entities to refresh UI values
                    self.main_window.inspector_dock.set_entities(self.main_window.inspector_dock.current_entities)
        except Exception as e:
            print(f"Undo failed: {e}")

    def redo(self):
        if not self.redo_stack:
            return
            
        command = self.redo_stack.pop()
        try:
            command.redo()
            self.undo_stack.append(command)
            # print(f"Redid {type(command).__name__}")
            if self.main_window:
                self.main_window.hierarchy_dock.refresh()
                if self.main_window.inspector_dock.current_entities:
                    self.main_window.inspector_dock.set_entities(self.main_window.inspector_dock.current_entities)
        except Exception as e:
            print(f"Redo failed: {e}")

class DeleteEntitiesCommand(Command):
    def __init__(self, world, entities):
        self.world = world
        self.entities = list(entities) # Copy list
        self.indices = [] # List of (entity, parent, index_in_parent, index_in_world)
        
        # Capture state
        for entity in self.entities:
            parent = entity.parent
            idx_in_parent = -1
            if parent:
                if entity in parent.children:
                    idx_in_parent = parent.children.index(entity)
            
            idx_in_world = -1
            if entity in getattr(self.world, '_entity_set', self.world.entities):
                idx_map = getattr(self.world, '_entity_index', None)
                if idx_map is not None and entity in idx_map:
                    idx_in_world = idx_map[entity]
                else:
                    idx_in_world = self.world.entities.index(entity)
                
            self.indices.append({
                'entity': entity,
                'parent': parent,
                'idx_parent': idx_in_parent,
                'idx_world': idx_in_world
            })

    def execute(self):
        # The actual deletion logic.
        # Note: If called from outside (e.g. key press), the deletion might happen there.
        # But for Redo, we need this.
        # And usually we construct command, execute it, then push.
        for item in self.indices:
            entity = item['entity']
            if entity in getattr(self.world, '_entity_set', self.world.entities):
                self.world.destroy_entity(entity)

    def undo(self):
        # Restore in reverse order of deletion to maintain indices if possible
        # But indices were captured at start.
        # We should restore based on captured indices.
        
        # Sort indices by world index to restore order?
        sorted_items = sorted(self.indices, key=lambda x: x['idx_world'])
        
        for item in sorted_items:
            entity = item['entity']
            parent = item['parent']
            idx_parent = item['idx_parent']
            idx_world = item['idx_world']
            
            # Add back to world
            if idx_world >= 0 and idx_world <= len(self.world.entities):
                self.world.entities.insert(idx_world, entity)
            else:
                self.world.entities.append(entity)
            self.world._register_entity(entity)
            self.world._sync_entity_indices()
            
            # Add back to parent
            if parent:
                entity.parent = parent
                if idx_parent >= 0 and idx_parent <= len(parent.children):
                    parent.children.insert(idx_parent, entity)
                else:
                    parent.children.append(entity)
            else:
                entity.parent = None

    def redo(self):
        self.execute()

class DuplicateEntitiesCommand(Command):
    def __init__(self, world, new_entities):
        self.world = world
        self.new_entities = list(new_entities)
        # Capture parents to restore hierarchy on redo
        self.parents = {e: e.parent for e in new_entities}
    
    def execute(self):
        for entity in self.new_entities:
            # Add to world if not already there
            if entity not in getattr(self.world, '_entity_set', self.world.entities):
                # To properly register it, we use create_entity logic or append
                # But since it's already instantiated, we append and add to index
                self.world.entities.append(entity)
                self.world._register_entity(entity)
                self.world._sync_entity_indices()
                
                # Register components
                for component in entity.components.values():
                    self.world.on_component_added(entity, component)
                    
                # Register groups
                for group in entity.groups:
                    self.world.on_entity_group_changed(entity, group, added=True)
            
            # Restore parent connection
            parent = self.parents.get(entity)
            if parent:
                # add_child sets entity.parent = parent and adds to children list
                if entity not in parent.children:
                    parent.add_child(entity)
            else:
                entity.parent = None

    def undo(self):
        for entity in self.new_entities:
            if entity in getattr(self.world, '_entity_set', self.world.entities):
                self.world.destroy_entity(entity)

    def redo(self):
        self.execute()

class TransformCommand(Command):
    def __init__(self, entities, initial_states, final_states):
        self.entities = entities
        self.initial_states = initial_states # List of dicts {'x':..., 'y':..., ...}
        self.final_states = final_states

    def undo(self):
        for i, entity in enumerate(self.entities):
            state = self.initial_states[i]
            t = entity.get_component(Transform)
            if t:
                t.x = state['x']
                t.y = state['y']
                t.rotation = state['rotation']
                t.scale_x = state['scale_x']
                t.scale_y = state['scale_y']

    def redo(self):
        for i, entity in enumerate(self.entities):
            state = self.final_states[i]
            t = entity.get_component(Transform)
            if t:
                t.x = state['x']
                t.y = state['y']
                t.rotation = state['rotation']
                t.scale_x = state['scale_x']
                t.scale_y = state['scale_y']

class PropertyChangeCommand(Command):
    def __init__(self, entities, component_type, attr_name, old_values, new_value):
        self.entities = entities
        self.component_type = component_type
        self.attr_name = attr_name
        self.old_values = old_values # List of values corresponding to entities
        self.new_value = new_value   # Single value applied to all

    def undo(self):
        for i, entity in enumerate(self.entities):
            comp = entity.get_component(self.component_type)
            if comp:
                setattr(comp, self.attr_name, self.old_values[i])

    def redo(self):
        for entity in self.entities:
            comp = entity.get_component(self.component_type)
            if comp:
                setattr(comp, self.attr_name, self.new_value)

class MultiPropertyChangeCommand(Command):
    def __init__(self, entities, component_type, attr_names, old_values_list, new_values):
        self.entities = entities
        self.component_type = component_type
        self.attr_names = attr_names
        self.old_values_list = old_values_list
        self.new_values = new_values

    def undo(self):
        for i, entity in enumerate(self.entities):
            comp = entity.get_component(self.component_type)
            if not comp:
                continue
            for attr_name, old_values in zip(self.attr_names, self.old_values_list):
                setattr(comp, attr_name, old_values[i])

    def redo(self):
        for entity in self.entities:
            comp = entity.get_component(self.component_type)
            if not comp:
                continue
            for attr_name, new_value in zip(self.attr_names, self.new_values):
                setattr(comp, attr_name, new_value)

class EntityPropertyChangeCommand(Command):
    def __init__(self, entities, getter, setter, old_values, new_value):
        self.entities = entities
        self.getter = getter
        self.setter = setter
        self.old_values = old_values
        self.new_value = new_value

    def undo(self):
        for i, entity in enumerate(self.entities):
            self.setter(entity, self.old_values[i])

    def redo(self):
        for entity in self.entities:
            self.setter(entity, self.new_value)


class TilemapEditCommand(Command):
    """
    Undoable set of tile edits for one tilemap layer.

    changes: list of (x, y, old_value, new_value)
    """

    def __init__(self, entity, layer_index: int, changes: list[tuple[int, int, int, int]]):
        self.entity = entity
        self.layer_index = int(layer_index)
        self.changes = [(int(x), int(y), int(old), int(new)) for (x, y, old, new) in (changes or [])]

    def _apply(self, use_new: bool):
        if not self.entity:
            return
        tilemap = self.entity.get_component(TilemapComponent)
        if not tilemap or not tilemap.layers:
            return
        idx = max(0, min(self.layer_index, len(tilemap.layers) - 1))
        layer = tilemap.layers[idx]
        for x, y, old_value, new_value in self.changes:
            # Use world coordinates for infinite expansion
            layer.set_world(x, y, new_value if use_new else old_value)

    def execute(self):
        self._apply(True)

    def undo(self):
        self._apply(False)

    def redo(self):
        self._apply(True)
