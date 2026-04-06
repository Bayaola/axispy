from PyQt6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QInputDialog, QMessageBox, QLabel, QLineEdit
from PyQt6.QtCore import Qt
from core.ecs import Entity

class GroupsDock(QDockWidget):
    def __init__(self, main_window):
        super().__init__("Groups", main_window)
        self.main_window = main_window
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        
        # Filter
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter groups...")
        self.filter_edit.textChanged.connect(self.refresh_list)
        layout.addWidget(self.filter_edit)
        
        # List
        self.groups_list = QListWidget()
        self.groups_list.itemClicked.connect(self.on_group_selected)
        layout.addWidget(self.groups_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Create Group")
        add_btn.clicked.connect(self.create_group)
        del_btn = QPushButton("Delete Group")
        del_btn.clicked.connect(self.delete_group)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_list)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addWidget(refresh_btn)
        layout.addLayout(btn_layout)
        
        self.setWidget(container)
        
    def refresh_list(self):
        self.groups_list.clear()
        if not self.main_window.scene:
            return
            
        world = self.main_window.scene.world
        filter_text = self.filter_edit.text().lower()
        
        # Get all unique groups from world registry
        all_groups = sorted(list(world.groups.keys()))
        
        for group in all_groups:
            if filter_text and filter_text not in group.lower():
                continue
                
            count = len(world.groups[group])
            self.groups_list.addItem(f"{group} ({count})")
            
    def create_group(self):
        if not self.main_window.scene:
            return
            
        name, ok = QInputDialog.getText(self, "Create Group", "Group Name:")
        if ok and name:
            world = self.main_window.scene.world
            if name in world.groups:
                QMessageBox.warning(self, "Error", "Group already exists")
                return
            # Create empty group entry
            world.groups[name] = set()
            self.refresh_list()
            
    def delete_group(self):
        if not self.main_window.scene:
            return
            
        items = self.groups_list.selectedItems()
        if not items:
            return
            
        # Parse name from "Name (Count)"
        text = items[0].text()
        name = text.rpartition(" (")[0]
        
        if QMessageBox.question(self, "Confirm", f"Delete group '{name}'? Entities will be removed from this group.") == QMessageBox.StandardButton.Yes:
            world = self.main_window.scene.world
            # Remove group from all entities
            if name in world.groups:
                entities = list(world.groups[name])
                for entity in entities:
                    entity.remove_group(name)
                # Ensure it's gone from registry
                if name in world.groups:
                    del world.groups[name]
            self.refresh_list()

    def on_group_selected(self, item):
        # Maybe select all entities in this group?
        # Or just show info
        pass
