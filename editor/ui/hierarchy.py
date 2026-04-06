from PyQt6.QtWidgets import QDockWidget, QTreeWidget, QTreeWidgetItem, QMenu, QFileDialog, QMessageBox, QAbstractItemView
from PyQt6.QtCore import Qt, QMimeData, QSize
from PyQt6.QtGui import QDrag, QKeySequence, QShortcut, QIcon, QPixmap
from core.components import Transform, CameraComponent
from core.serializer import SceneSerializer
from editor.undo_manager import DeleteEntitiesCommand, DuplicateEntitiesCommand
import qtawesome as qta
import tempfile, os
from editor.ui.engine_settings import theme_icon_color, theme_arrow_color

class HierarchyDock(QDockWidget):
    def __init__(self, scene, parent=None):
        super().__init__("Hierarchy", parent)
        self.scene = scene
        self.main_window = parent # Assuming parent is MainWindow
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        self.tree.itemChanged.connect(self.on_item_changed)

        self._rebuild_icons()
        self._apply_arrow_stylesheet()
        
        # Drag and drop settings
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Override drag and drop events
        self.tree.dragEnterEvent = self.dragEnterEvent
        self.tree.dragMoveEvent = self.dragMoveEvent
        self.tree.dropEvent = self.dropEvent
        
        self.setWidget(self.tree)
        
        # Shortcuts
        self.delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.tree, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.delete_selected_entities)
        
        self.duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), self.tree, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.duplicate_shortcut.activated.connect(self.duplicate_selected_entities)

        self.refresh()

    def get_unique_name(self, name, parent_entity, exclude_entity=None):
        siblings = []
        if parent_entity:
            siblings = parent_entity.children
        else:
            # Root level siblings
            siblings = [e for e in self.scene.world.entities if e.parent is None]
            
        existing_names = set()
        for e in siblings:
            if exclude_entity and e == exclude_entity:
                continue
            existing_names.add(e.name)
        
        if name not in existing_names:
            return name
            
        # Try to find a suffix
        base_name = name
        counter = 1
        
        # Check if name already ends with a number
        import re
        match = re.search(r'\((\d+)\)$', name)
        if match:
            try:
                counter = int(match.group(1)) + 1
                base_name = name[:match.start()].strip()
            except ValueError:
                pass # Fallback to appending
            
        new_name = f"{base_name} ({counter})"
        while new_name in existing_names:
            counter += 1
            new_name = f"{base_name} ({counter})"
            
        return new_name

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.accept()
        else:
            event.ignore()

    def refresh(self):
        # Store current selection
        selected_items = self.tree.selectedItems()
        selected_entity_ids = [item.data(0, Qt.ItemDataRole.UserRole) for item in selected_items]
        
        expansion_state = {}
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while stack:
            current_item = stack.pop()
            if not current_item:
                continue
            entity_id = current_item.data(0, Qt.ItemDataRole.UserRole)
            if entity_id:
                expansion_state[entity_id] = current_item.isExpanded()
            for i in range(current_item.childCount()):
                stack.append(current_item.child(i))
        
        self.tree.blockSignals(True)
        self.tree.clear()
        
        # Keep a map of entities to tree items for quick selection
        self._item_map = {}
        
        if not self.scene:
            self.tree.blockSignals(False)
            return
            
        # Recursive function to add items
        def add_item(entity, parent_item=None):
            item = QTreeWidgetItem([entity.name])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            item.setData(0, Qt.ItemDataRole.UserRole, entity.id)
            if entity.get_component(CameraComponent):
                item.setIcon(0, self._camera_icon)
            else:
                item.setIcon(0, self._entity_icon)
            self._item_map[entity.id] = item
            
            if entity.id in selected_entity_ids:
                item.setSelected(True)
            
            if parent_item:
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)
                
            for child in entity.children:
                add_item(child, item)
            
            item.setExpanded(expansion_state.get(entity.id, False))

        for entity in self.scene.world.entities:
            # Only add root entities (those without parent)
            if entity.parent is None:
                add_item(entity)
                
        self.tree.blockSignals(False)

    def _get_entity_from_item(self, item):
        if not item:
            return None
        entity_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not entity_id:
            return None
        return self.scene.world.get_entity_by_id(entity_id)

    def dropEvent(self, event):
        # Get the dragged item before Qt can interfere
        dragged_item = self.tree.currentItem()
        if not dragged_item:
            event.ignore()
            return
            
        # Get the target item (where it was dropped)
        target_item = self.tree.itemAt(event.position().toPoint())
        
        dragged_entity = self._get_entity_from_item(dragged_item)
        target_entity = self._get_entity_from_item(target_item)
        
        if not dragged_entity:
            event.ignore()
            return
        
        # Prevent dragging onto itself
        if target_entity and target_entity == dragged_entity:
            event.ignore()
            return
        
        # Prevent dragging onto its children (circular dependency)
        if target_entity:
            current = target_entity
            while current:
                if current == dragged_entity:
                    event.ignore()
                    return
                current = current.parent
        
        # Prevent dropping onto current parent (no-op)
        if target_entity == dragged_entity.parent:
            event.ignore()
            return
        
        # --- Perform the reparenting on the ECS side ---
        
        # Detach from old parent
        if dragged_entity.parent:
            dragged_entity.parent.remove_child(dragged_entity)
            
        if target_entity:
            target_entity.add_child(dragged_entity)
            
            # Inherit layer and groups from new parent
            dragged_entity.set_layer(target_entity.layer)
            dragged_entity.groups = set(target_entity.groups)
        else:
            # Dropped at root level
            dragged_entity.parent = None
            
        # Ensure name uniqueness in new location (exclude self from sibling check)
        new_name = self.get_unique_name(dragged_entity.name, target_entity, exclude_entity=dragged_entity)
        if new_name != dragged_entity.name:
            dragged_entity.name = new_name
        
        # Prevent Qt from doing its own internal move on the tree items
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        
        # Rebuild the tree entirely from the ECS data
        self.tree.blockSignals(True)
        self.refresh()
        # refresh() unblocks signals internally, re-block
        self.tree.blockSignals(True)
        
        # Expand the new parent so the moved entity is visible
        if target_entity and target_entity.id in self._item_map:
            self._item_map[target_entity.id].setExpanded(True)
        
        # Restore selection without triggering signals
        if dragged_entity.id in self._item_map:
            self.tree.clearSelection()
            self._item_map[dragged_entity.id].setSelected(True)
            self.tree.scrollToItem(self._item_map[dragged_entity.id])
        
        self.tree.blockSignals(False)

    def select_entities(self, entities):
        if not entities:
            self.tree.clearSelection()
            return

        if not isinstance(entities, list):
            entities = [entities]
            
        # Ensure item map exists
        if not hasattr(self, '_item_map'):
            return

        self.tree.blockSignals(True)
        self.tree.clearSelection()
        
        for entity in entities:
            if not entity:
                continue
            item = self._item_map.get(entity.id)
            if item:
                try:
                    item.setSelected(True)
                    # Scroll to the last selected item
                    self.tree.scrollToItem(item)
                except RuntimeError:
                    # Stale reference handling similar to before
                    pass
        
        self.tree.blockSignals(False)

    def select_entity(self, entity):
        # Wrapper for backward compatibility
        self.select_entities([entity] if entity else [])

    def on_item_changed(self, item, column):
        entity = self._get_entity_from_item(item)
        if entity:
            new_name = item.text(0)
            if entity.name != new_name:
                # Check for uniqueness in the same scope
                parent = entity.parent
                final_name = self.get_unique_name(new_name, parent, exclude_entity=entity)
                
                # If name was adjusted to be unique, update the item text
                if final_name != new_name:
                    self.tree.blockSignals(True)
                    item.setText(0, final_name)
                    self.tree.blockSignals(False)
                
                entity.name = final_name
                
                # Update inspector if it's the selected entity
                if self.main_window and hasattr(self.main_window, 'inspector_dock'):
                    inspector = self.main_window.inspector_dock
                    if hasattr(inspector, 'current_entities') and entity in inspector.current_entities:
                        inspector.refresh_name()
            
    def open_context_menu(self, position):
        menu = QMenu()
        
        create_action = menu.addAction(qta.icon("fa5s.plus", color="#78c878"), "Create Entity")
        create_child_action = None
        duplicate_action = None
        
        # Check if an item is selected
        selected_items = self.tree.selectedItems()
        if selected_items:
             if len(selected_items) == 1:
                 create_child_action = menu.addAction(qta.icon("fa5s.plus-circle", color="#64b4ff"), "Create Child Entity")
             duplicate_action = menu.addAction(qta.icon("fa5s.clone", color="#c8c8c8"), "Duplicate")
        
        delete_action = menu.addAction(qta.icon("fa5s.trash-alt", color="#ff6b6b"), "Delete Selected Entities" if len(selected_items) > 1 else "Delete Entity")
        menu.addSeparator()
        save_prefab_action = menu.addAction(qta.icon("fa5s.cube", color="#64dc64"), "Save as Prefab")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == create_action:
            self.create_entity()
        elif create_child_action and action == create_child_action:
            self.create_child_entity(selected_items[0])
        elif duplicate_action and action == duplicate_action:
            self.duplicate_selected_entities()
        elif action == delete_action:
            self.delete_selected_entities()
        elif action == save_prefab_action:
            self.save_as_prefab()

    def create_child_entity(self, parent_item):
        parent_entity = self._get_entity_from_item(parent_item)
        if not parent_entity:
            return
            
        new_name = self.get_unique_name("New Child", parent_entity)
        child = self.scene.world.create_entity(new_name)
        child.add_component(Transform())
        parent_entity.add_child(child)
        self.refresh()

    def save_as_prefab(self):
        items = self.tree.selectedItems()
        if not items:
            return
            
        entity = self._get_entity_from_item(items[0])
        if not entity:
            return
            
        # Ask for location
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Prefab", "", "Prefab Files (*.pfb)")
        if file_path:
            try:
                data = SceneSerializer.entity_to_json(entity)
                with open(file_path, "w") as f:
                    f.write(data)
                print(f"Prefab saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save prefab: {e}")

    def create_entity(self):
        new_name = self.get_unique_name("New Entity", None)
        entity = self.scene.world.create_entity(new_name)
        entity.add_component(Transform())
        self.refresh()

    def duplicate_selected_entities(self):
        items = self.tree.selectedItems()
        if not items:
            return
            
        new_selection = []
        for item in items:
            entity = self._get_entity_from_item(item)
            if not entity:
                continue
            
            # Serialize to JSON then deserialize to create a deep copy
            data = SceneSerializer.entity_to_json(entity)
            
            # Parse the JSON and strip IDs
            import json
            entity_data = json.loads(data)
            
            def remove_ids(data):
                if "id" in data:
                    del data["id"]
                if "children" in data:
                    for child in data["children"]:
                        remove_ids(child)
            
            remove_ids(entity_data)
            
            # Ensure unique name
            original_name = entity_data.get("name", "Entity")
            parent = entity.parent
            new_name = self.get_unique_name(original_name, parent)
            entity_data["name"] = new_name
            
            # Deserialize
            # entity_from_json will automatically create a new entity in the world
            # and set up its components and children
            new_entity = SceneSerializer.entity_from_json(json.dumps(entity_data), self.scene.world)
            
            # Add to parent
            if parent:
                parent.add_child(new_entity)
            
            new_selection.append(new_entity)
            
        # Use UndoManager
        if hasattr(self.main_window, 'undo_manager'):
            cmd = DuplicateEntitiesCommand(self.scene.world, new_selection)
            # Entities are already created/added by entity_from_json, so execute logic is satisfied
            # But wait, DuplicateEntitiesCommand.execute() might add them again or we should just push
            self.main_window.undo_manager.push(cmd)

        self.refresh()
        self.select_entities(new_selection)
        
        # Notify main window
        if self.main_window and hasattr(self.main_window, 'on_entity_selected'):
            self.main_window.on_entity_selected()

    def delete_selected_entities(self):
        items = self.tree.selectedItems()
        if not items:
            return
            
        # Confirmation dialog
        count = len(items)
        reply = QMessageBox.question(self, "Delete Entities", 
                                   f"Are you sure you want to delete {count} entities?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                   QMessageBox.StandardButton.No)
                                   
        if reply == QMessageBox.StandardButton.No:
            return
            
        entities_to_delete = []
        for item in items:
            entity = self._get_entity_from_item(item)
            if entity:
                entities_to_delete.append(entity)
        protected_entities = [entity for entity in entities_to_delete if self._is_protected_entity(entity)]
        entities_to_delete = [entity for entity in entities_to_delete if not self._is_protected_entity(entity)]
        if protected_entities:
            QMessageBox.information(self, "Protected Entity", "Main Camera cannot be deleted.")
        if not entities_to_delete:
            return
                
        # Filter out entities whose parents are also selected
        final_list = []
        for entity in entities_to_delete:
            parent_selected = False
            current = entity.parent
            while current:
                if current in entities_to_delete:
                    parent_selected = True
                    break
                current = current.parent
            
            if not parent_selected:
                final_list.append(entity)
        
        # Use UndoManager
        if hasattr(self.main_window, 'undo_manager'):
            cmd = DeleteEntitiesCommand(self.scene.world, final_list)
            cmd.execute()
            self.main_window.undo_manager.push(cmd)
        else:
            for entity in final_list:
                self.scene.world.destroy_entity(entity)
            
        self.refresh()
        
        # Notify main window to clear selection and hide gizmo
        if self.main_window and hasattr(self.main_window, 'on_entity_selected'):
            self.main_window.on_entity_selected()

    def update_theme_icons(self):
        """Refresh all icons when the theme changes."""
        self._rebuild_icons()
        self._apply_arrow_stylesheet()
        self.refresh()

    def _rebuild_icons(self):
        c = theme_icon_color()
        self._entity_icon = qta.icon("fa5s.cube", color=c)
        self._camera_icon = qta.icon("fa5s.camera", color="#78c878")

    def _apply_arrow_stylesheet(self):
        ac = theme_arrow_color()
        arrow_right = qta.icon("fa5s.chevron-right", color=ac)
        arrow_down = qta.icon("fa5s.chevron-down", color=ac)
        tmp_dir = os.path.join(tempfile.gettempdir(), "techcrea_icons")
        os.makedirs(tmp_dir, exist_ok=True)
        closed_path = os.path.join(tmp_dir, "arrow_right.png")
        open_path = os.path.join(tmp_dir, "arrow_down.png")
        arrow_right.pixmap(12, 12).save(closed_path)
        arrow_down.pixmap(12, 12).save(open_path)
        closed_path_css = closed_path.replace("\\", "/")
        open_path_css = open_path.replace("\\", "/")
        self.tree.setStyleSheet(f"""
            QTreeWidget::branch::has-children::!has-siblings::closed,
            QTreeWidget::branch::closed::has-children::has-siblings {{
                image: url({closed_path_css});
            }}
            QTreeWidget::branch::open::has-children::!has-siblings,
            QTreeWidget::branch::open::has-children::has-siblings {{
                image: url({open_path_css});
            }}
        """)

    def _is_protected_entity(self, entity):
        if not entity:
            return False
        if entity.name != "Main Camera":
            return False
        return entity.get_component(CameraComponent) is not None
