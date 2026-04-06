from PyQt6.QtWidgets import QDockWidget, QTreeView, QListView, QWidget, QVBoxLayout, QHBoxLayout, QMenu, QMessageBox, QSplitter, QAbstractItemView, QInputDialog, QComboBox, QSlider, QLabel, QStackedWidget, QPushButton, QFileIconProvider
from PyQt6.QtGui import QFileSystemModel, QKeySequence, QShortcut, QIcon
from PyQt6.QtCore import Qt, QDir, QSortFilterProxyModel, QSize, QFileInfo
import qtawesome as qta
from core.components import AnimatorComponent
from core.serializer import SceneSerializer
from core.animation import AnimationController, AnimationClip
from editor.ui.preview_panel import PreviewPanel
from editor.ui.engine_settings import load_engine_config, save_engine_config, theme_icon_color
import os
import shutil


class AssetIconProvider(QFileIconProvider):
    """Custom icon provider using FontAwesome icons via qtawesome."""

    _EXT_ICONS = {
        # Images
        ".png": ("fa5s.file-image", "#64b4ff"),
        ".jpg": ("fa5s.file-image", "#64b4ff"),
        ".jpeg": ("fa5s.file-image", "#64b4ff"),
        ".bmp": ("fa5s.file-image", "#64b4ff"),
        ".gif": ("fa5s.file-image", "#64b4ff"),
        ".svg": ("fa5s.file-image", "#64b4ff"),
        ".webp": ("fa5s.file-image", "#64b4ff"),
        ".ico": ("fa5s.file-image", "#64b4ff"),
        # Audio
        ".wav": ("fa5s.file-audio", "#b482dc"),
        ".mp3": ("fa5s.file-audio", "#b482dc"),
        ".ogg": ("fa5s.file-audio", "#b482dc"),
        ".flac": ("fa5s.file-audio", "#b482dc"),
        # Video
        ".mp4": ("fa5s.file-video", "#50b4dc"),
        ".avi": ("fa5s.file-video", "#50b4dc"),
        ".mov": ("fa5s.file-video", "#50b4dc"),
        ".webm": ("fa5s.file-video", "#50b4dc"),
        # Scripts
        ".py": ("fa5s.file-code", "#dcb450"),
        ".js": ("fa5s.file-code", "#dcb450"),
        ".ts": ("fa5s.file-code", "#dcb450"),
        ".lua": ("fa5s.file-code", "#dcb450"),
        # Data / Config
        ".json": ("fa5s.file-alt", "#78c8a0"),
        ".xml": ("fa5s.file-alt", "#78c8a0"),
        ".yaml": ("fa5s.file-alt", "#78c8a0"),
        ".yml": ("fa5s.file-alt", "#78c8a0"),
        ".toml": ("fa5s.file-alt", "#78c8a0"),
        ".csv": ("fa5s.file-alt", "#78c8a0"),
        ".ini": ("fa5s.file-alt", "#78c8a0"),
        ".cfg": ("fa5s.file-alt", "#78c8a0"),
        ".txt": ("fa5s.file-alt", "#c8c8c8"),
        ".md": ("fa5s.file-alt", "#c8c8c8"),
        ".log": ("fa5s.file-alt", "#888888"),
        # Engine-specific
        ".scn": ("fa5s.film", "#ff8c64"),
        ".pfb": ("fa5s.cube", "#64dc64"),
        ".anim": ("fa5s.video", "#ffdc50"),
        ".actrl": ("fa5s.project-diagram", "#ff8c64"),
        # Fonts
        ".ttf": ("fa5s.font", "#c896ff"),
        ".otf": ("fa5s.font", "#c896ff"),
        ".woff": ("fa5s.font", "#c896ff"),
        ".woff2": ("fa5s.font", "#c896ff"),
        # Archives
        ".zip": ("fa5s.file-archive", "#b4dc78"),
        ".tar": ("fa5s.file-archive", "#b4dc78"),
        ".gz": ("fa5s.file-archive", "#b4dc78"),
        ".7z": ("fa5s.file-archive", "#b4dc78"),
        ".rar": ("fa5s.file-archive", "#b4dc78"),
        # Docs
        ".pdf": ("fa5s.file-pdf", "#ff6b6b"),
    }

    _FOLDER_ICON = ("fa5s.folder", "#ffb43c")
    _FOLDER_OPEN_ICON = ("fa5s.folder-open", "#ffdc50")
    _DEFAULT_FILE_ICON = ("fa5s.file", "#c8c8c8")

    def __init__(self):
        super().__init__()
        self._cache = {}

    def _qta_icon(self, icon_name, color):
        key = (icon_name, color)
        if key not in self._cache:
            try:
                self._cache[key] = qta.icon(icon_name, color=color)
            except Exception:
                self._cache[key] = super().icon(QFileIconProvider.IconType.File)
        return self._cache[key]

    def icon(self, info_or_type):
        if isinstance(info_or_type, QFileInfo):
            if info_or_type.isDir():
                return self._qta_icon(*self._FOLDER_ICON)
            ext = os.path.splitext(info_or_type.fileName())[1].lower()
            entry = self._EXT_ICONS.get(ext)
            if entry:
                return self._qta_icon(*entry)
            return self._qta_icon(*self._DEFAULT_FILE_ICON)
        # IconType enum
        if info_or_type == QFileIconProvider.IconType.Folder:
            return self._qta_icon(*self._FOLDER_ICON)
        return self._qta_icon(*self._DEFAULT_FILE_ICON)


class AssetFilterProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        file_name = model.fileName(index)
        
        # Hide __pycache__, build folder, .atlas, and specific config files
        if file_name == "__pycache__":
            return False
        if file_name == "build":
            return False
        if file_name == ".axispy":
            return False
        if file_name == ".atlas":
            return False
        if file_name.endswith(".config") or file_name in ("hub_config.json", "editor_settings.json"):
            return False
        if file_name in ("temp_scene.scn", "temp_scene_runcheck.scn"):
            return False
            
        return super().filterAcceptsRow(source_row, source_parent)

class AssetManagerDock(QDockWidget):
    def __init__(self, main_window, parent=None):
        super().__init__("Assets", parent)
        self.main_window = main_window
        self.project_path = QDir.currentPath()
        self.current_root_path = self.project_path
        self.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        
        self.widget = QWidget()
        self.layout = QVBoxLayout(self.widget)
        self.setWidget(self.widget)

        controls_row = QHBoxLayout()
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Details", "List", "Large Icons"])
        self.view_mode_combo.currentIndexChanged.connect(self.set_view_mode)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(16, 128)
        self.zoom_slider.setValue(32)
        self.zoom_slider.setFixedWidth(140)
        self.zoom_slider.valueChanged.connect(self.apply_zoom)
        self.up_btn = QPushButton()
        self.up_btn.setIcon(qta.icon("fa5s.level-up-alt", color=theme_icon_color()))
        self.up_btn.setToolTip("Navigate Up")
        self.up_btn.clicked.connect(self.navigate_up)
        controls_row.addWidget(QLabel("View"))
        controls_row.addWidget(self.view_mode_combo)
        controls_row.addWidget(self.up_btn)
        controls_row.addWidget(QLabel("Zoom"))
        controls_row.addWidget(self.zoom_slider)
        controls_row.addStretch(1)
        self.layout.addLayout(controls_row)
        
        # Breadcrumbs
        self.breadcrumb_widget = QWidget()
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_widget)
        self.breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        self.breadcrumb_layout.setSpacing(2)
        self.layout.addWidget(self.breadcrumb_widget)
        
        # Create Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter, stretch=1)
        
        self.model = QFileSystemModel()
        self.model.setIconProvider(AssetIconProvider())
        self.model.setRootPath(QDir.currentPath())
        self.model.setReadOnly(False)
        
        self.proxy_model = AssetFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        
        root_index = self.proxy_model.mapFromSource(self.model.index(self.current_root_path))

        self.tree = QTreeView()
        self.tree.setModel(self.proxy_model)
        self.tree.setRootIndex(root_index)
        self.tree.setAnimated(False)
        self.tree.setIndentation(20)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setSortingEnabled(True)
        self.tree.setColumnWidth(0, 300)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(lambda pos, view=self.tree: self.open_context_menu(view, pos))
        self.tree.doubleClicked.connect(self.on_double_click)
        self.tree.selectionModel().currentChanged.connect(self.on_selection_changed)

        self.list_view = QListView()
        self.list_view.setModel(self.proxy_model)
        self.list_view.setRootIndex(root_index)
        self.list_view.setViewMode(QListView.ViewMode.ListMode)
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(lambda pos, view=self.list_view: self.open_context_menu(view, pos))
        self.list_view.doubleClicked.connect(self.on_double_click)
        self.list_view.selectionModel().currentChanged.connect(self.on_selection_changed)

        self.icon_view = QListView()
        self.icon_view.setModel(self.proxy_model)
        self.icon_view.setRootIndex(root_index)
        self.icon_view.setViewMode(QListView.ViewMode.IconMode)
        self.icon_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.icon_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.icon_view.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        self.icon_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.icon_view.customContextMenuRequested.connect(lambda pos, view=self.icon_view: self.open_context_menu(view, pos))
        self.icon_view.doubleClicked.connect(self.on_double_click)
        self.icon_view.selectionModel().currentChanged.connect(self.on_selection_changed)

        self.views_stack = QStackedWidget()
        self.views_stack.addWidget(self.tree)
        self.views_stack.addWidget(self.list_view)
        self.views_stack.addWidget(self.icon_view)
        
        # Delete shortcut
        self.delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.widget, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.delete_selected_files)

        # Select All shortcut (Ctrl+A)
        self.select_all_shortcut = QShortcut(QKeySequence.StandardKey.SelectAll, self.widget, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.select_all_shortcut.activated.connect(lambda: self.active_view().selectAll())
        
        self.splitter.addWidget(self.views_stack)
        
        # Preview Panel
        self.preview_panel = PreviewPanel()
        self.splitter.addWidget(self.preview_panel)
        
        # Set initial sizes
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self._load_ui_preferences()
        self.apply_zoom(self.zoom_slider.value())
        self.update_breadcrumbs()

    def update_breadcrumbs(self):
        while self.breadcrumb_layout.count():
            item = self.breadcrumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        if not self.project_path or not self.current_root_path:
            return
            
        try:
            rel_path = os.path.relpath(self.current_root_path, self.project_path)
        except ValueError:
            rel_path = "."
            
        parts = [] if rel_path == "." else rel_path.split(os.sep)
        current_build_path = self.project_path
        
        root_name = os.path.basename(self.project_path)
        if not root_name:
            root_name = self.project_path
            
        root_btn = QPushButton(root_name)
        root_btn.setFlat(True)
        root_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        root_btn.setStyleSheet("font-weight: bold; color: palette(link); text-decoration: underline;")
        root_btn.clicked.connect(lambda checked=False, p=self.project_path: self.set_current_root_path(p))
        self.breadcrumb_layout.addWidget(root_btn)
        
        for part in parts:
            if not part or part == ".":
                continue
            current_build_path = os.path.join(current_build_path, part)
            
            lbl = QLabel(" > ")
            self.breadcrumb_layout.addWidget(lbl)
            
            btn = QPushButton(part)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("font-weight: bold; color: palette(link); text-decoration: underline;")
            btn.clicked.connect(lambda checked=False, p=current_build_path: self.set_current_root_path(p))
            self.breadcrumb_layout.addWidget(btn)
            
        self.breadcrumb_layout.addStretch(1)

    def active_view(self):
        return self.views_stack.currentWidget()

    def set_view_mode(self, index: int):
        self.views_stack.setCurrentIndex(index)
        self._save_ui_preferences()

    def apply_zoom(self, size: int):
        icon_size = QSize(size, size)
        self.tree.setIconSize(icon_size)
        self.list_view.setIconSize(icon_size)
        self.icon_view.setIconSize(icon_size)
        self.icon_view.setGridSize(QSize(size + 40, size + 40))
        self._save_ui_preferences()

    def set_current_root_path(self, path: str):
        normalized = os.path.normpath(path)
        source_index = self.model.index(normalized)
        if not source_index.isValid():
            return
        proxy_index = self.proxy_model.mapFromSource(source_index)
        if not proxy_index.isValid():
            return
        self.current_root_path = normalized
        self.tree.setRootIndex(proxy_index)
        self.list_view.setRootIndex(proxy_index)
        self.icon_view.setRootIndex(proxy_index)
        self._save_ui_preferences()
        self.update_breadcrumbs()

    def update_theme_icons(self):
        """Refresh icons when the theme changes."""
        self.up_btn.setIcon(qta.icon("fa5s.level-up-alt", color=theme_icon_color()))

    def navigate_up(self):
        if not self.current_root_path:
            return
        parent = os.path.dirname(self.current_root_path)
        if not parent or parent == self.current_root_path:
            return
        if self.project_path and not os.path.normpath(parent).startswith(os.path.normpath(self.project_path)):
            return
        self.set_current_root_path(parent)

    def _load_ui_preferences(self):
        data = load_engine_config()
        view_mode = int(data.get("assets_view_mode", 0))
        zoom = int(data.get("assets_zoom", 32))
        view_mode = max(0, min(2, view_mode))
        zoom = max(16, min(128, zoom))
        self.view_mode_combo.blockSignals(True)
        self.zoom_slider.blockSignals(True)
        self.view_mode_combo.setCurrentIndex(view_mode)
        self.zoom_slider.setValue(zoom)
        self.view_mode_combo.blockSignals(False)
        self.zoom_slider.blockSignals(False)
        self.views_stack.setCurrentIndex(view_mode)

    def _save_ui_preferences(self):
        data = load_engine_config()
        data["assets_view_mode"] = int(self.view_mode_combo.currentIndex())
        data["assets_zoom"] = int(self.zoom_slider.value())
        save_engine_config(data)

    def on_selection_changed(self, current, previous):
        if current.isValid():
            source_index = self.proxy_model.mapToSource(current)
            file_path = self.model.filePath(source_index)
            self.preview_panel.set_file(file_path)
        else:
            self.preview_panel.clear()

    def set_project_path(self, path: str):
        self.project_path = os.path.normpath(path)
        self.model.setRootPath(path)
        self.set_current_root_path(path)

    def open_context_menu(self, view, position):
        indexes = self._get_selected_indexes()
        
        menu = QMenu()
        
        # Multi-selection logic
        if len(indexes) > 1:
            delete_action = menu.addAction(qta.icon("fa5s.trash-alt", color="#ff6b6b"), f"Delete {len(indexes)} Items")
            
            action = menu.exec(view.viewport().mapToGlobal(position))
            
            if action == delete_action:
                self.delete_selected_files()
            return
            
        # Single selection or no selection logic
        index = view.indexAt(position)
        
        # Determine the target path for creating new files/folders
        if index.isValid():
            source_index = self.proxy_model.mapToSource(index)
            file_path = self.model.filePath(source_index)
        else:
            root_proxy = view.rootIndex()
            root_source = self.proxy_model.mapToSource(root_proxy)
            file_path = self.model.filePath(root_source) if root_source.isValid() else self.current_root_path

        import os
        target_dir = file_path if os.path.isdir(file_path) else os.path.dirname(file_path)
        
        new_folder_action = menu.addAction(qta.icon("fa5s.folder-plus", color="#ffb43c"), "New Folder")
        new_animation_action = menu.addAction(qta.icon("fa5s.video", color="#ffdc50"), "New Animation Clip")
        new_controller_action = menu.addAction(qta.icon("fa5s.project-diagram", color="#ff8c64"), "New Animation Controller")
        menu.addSeparator()
        
        # Specific actions
        instantiate_action = None
        load_scene_action = None
        edit_script_action = None
        open_animation_action = None
        open_controller_action = None
        
        if index.isValid():
            if file_path.endswith(".pfb"):
                instantiate_action = menu.addAction(qta.icon("fa5s.cube", color="#64dc64"), "Instantiate Prefab")
                
            elif file_path.endswith(".scn"):
                load_scene_action = menu.addAction(qta.icon("fa5s.film", color="#ff8c64"), "Load Scene")
                
            elif file_path.endswith(".py"):
                edit_script_action = menu.addAction(qta.icon("fa5s.file-code", color="#dcb450"), "Edit Script")
            elif file_path.endswith(".anim"):
                open_animation_action = menu.addAction(qta.icon("fa5s.magic", color="#ffdc50"), "Open Animation Clip")
            elif file_path.endswith(".actrl"):
                open_controller_action = menu.addAction(qta.icon("fa5s.project-diagram", color="#ff8c64"), "Open Animation Controller")
                
            # Common actions
            menu.addSeparator()
            rename_action = menu.addAction(qta.icon("fa5s.pen", color="#c8c8c8"), "Rename")
            delete_action = menu.addAction(qta.icon("fa5s.trash-alt", color="#ff6b6b"), "Delete")
        else:
            rename_action = None
            delete_action = None
        
        action = menu.exec(view.viewport().mapToGlobal(position))
        
        if action == new_folder_action:
            self.create_new_folder(target_dir)

        elif action == new_animation_action:
            self.create_new_animation_clip(target_dir)

        elif action == new_controller_action:
            self.create_new_animation_controller(target_dir)
            
        elif instantiate_action and action == instantiate_action:
            self.instantiate_prefab(file_path)
            
        elif load_scene_action and action == load_scene_action:
            self.load_scene(file_path)
            
        elif edit_script_action and action == edit_script_action:
            if self.main_window:
                self.main_window.open_script(file_path)

        elif open_animation_action and action == open_animation_action:
            if self.main_window:
                self.main_window.open_animation_clip(file_path)

        elif open_controller_action and action == open_controller_action:
            if self.main_window:
                self.main_window.open_animation_controller_editor(file_path)
                
        elif rename_action and action == rename_action:
            view.edit(index)
            
        elif delete_action and action == delete_action:
            self.delete_selected_files()

    def create_new_folder(self, parent_dir):
        import os
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and folder_name:
            new_path = os.path.join(parent_dir, folder_name)
            try:
                os.makedirs(new_path, exist_ok=False)
                print(f"Created new folder: {new_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create folder:\n{e}")

    def create_new_animation_clip(self, parent_dir):
        clip_name, ok = QInputDialog.getText(self, "New Animation Clip", "Enter clip file name:")
        if not ok:
            return
        clip_name = clip_name.strip()
        if not clip_name:
            return
        if not clip_name.endswith(".anim"):
            clip_name += ".anim"
        file_path = os.path.join(parent_dir, clip_name)
        if os.path.exists(file_path):
            QMessageBox.warning(self, "Warning", f"File already exists:\n{file_path}")
            return
        try:
            SceneSerializer.save_animation_clip(file_path, AnimationClip(clip_name.replace(".anim", "")))
            print(f"Created animation clip: {file_path}")
        except Exception as error:
            QMessageBox.critical(self, "Error", f"Failed to create animation clip:\n{error}")

    def create_new_animation_controller(self, parent_dir):
        ctrl_name, ok = QInputDialog.getText(self, "New Animation Controller", "Enter controller name:")
        if not ok:
            return
        ctrl_name = ctrl_name.strip()
        if not ctrl_name:
            return
        if not ctrl_name.endswith(".actrl"):
            ctrl_name += ".actrl"
        file_path = os.path.join(parent_dir, ctrl_name)
        if os.path.exists(file_path):
            QMessageBox.warning(self, "Warning", f"File already exists:\n{file_path}")
            return
        try:
            ctrl = AnimationController()
            SceneSerializer.save_animation_controller(file_path, ctrl)
            print(f"Created animation controller: {file_path}")
        except Exception as error:
            QMessageBox.critical(self, "Error", f"Failed to create animation controller:\n{error}")

    def _get_selected_indexes(self):
        """Return selected proxy indexes for the active view."""
        view = self.active_view()
        sel = view.selectionModel()
        # selectedRows works for QTreeView; QListView needs selectedIndexes
        indexes = sel.selectedRows(0)
        if not indexes:
            indexes = sel.selectedIndexes()
        # Deduplicate by row+parent (tree views return one index per column)
        seen = set()
        unique = []
        for ix in indexes:
            key = (ix.row(), ix.parent())
            if key not in seen:
                seen.add(key)
                unique.append(ix)
        return unique

    def delete_selected_files(self):
        indexes = self._get_selected_indexes()
        
        if not indexes:
            return

        paths = []
        for ix in indexes:
            source_index = self.proxy_model.mapToSource(ix)
            paths.append(self.model.filePath(source_index))
            
        # Confirmation dialog
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Delete Confirmation")
        
        count = len(paths)
        if count == 1:
            path = paths[0]
            name = os.path.basename(path)
            if os.path.isdir(path):
                 msg_box.setText(f"Are you sure you want to permanently delete the folder '{name}' and all its contents?")
            else:
                 msg_box.setText(f"Are you sure you want to permanently delete the file '{name}'?")
        else:
            msg_box.setText(f"Are you sure you want to permanently delete these {count} items?")
            msg_box.setInformativeText("This action cannot be undone.")
            
            detailed_text = "\n".join([os.path.basename(p) for p in paths])
            if len(detailed_text) > 500:
                detailed_text = detailed_text[:500] + "\n..."
            msg_box.setDetailedText(detailed_text)
            
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            errors = []
            for path in paths:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    print(f"Deleted: {path}")
                except Exception as e:
                    errors.append(f"{os.path.basename(path)}: {str(e)}")
            
            if errors:
                QMessageBox.critical(self, "Delete Errors", "Some items could not be deleted:\n\n" + "\n".join(errors))

    def on_double_click(self, index):
        source_index = self.proxy_model.mapToSource(index)
        file_path = self.model.filePath(source_index)
        if os.path.isdir(file_path):
            self.set_current_root_path(file_path)
            return
        if file_path.endswith(".scn"):
            self.load_scene(file_path)
        elif file_path.endswith(".pfb"):
            self.instantiate_prefab(file_path)
        elif file_path.endswith(".py"):
            if self.main_window:
                self.main_window.open_script(file_path)
        elif file_path.endswith(".anim"):
            if self.main_window:
                self.main_window.open_animation_clip(file_path)
        elif file_path.endswith(".actrl"):
            if self.main_window:
                self.main_window.open_animation_controller_editor(file_path)

    def instantiate_prefab(self, path):
        try:
            with open(path, "r") as f:
                json_str = f.read()
                # We need access to the world instance.
                # Passed MainWindow reference in constructor
                if self.main_window and self.main_window.scene:
                    entity = SceneSerializer.entity_from_json(json_str, self.main_window.scene.world)
                    self.main_window.hierarchy_dock.refresh()
                    print(f"Instantiated prefab from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to instantiate prefab: {e}")

    def load_scene(self, path):
        if self.main_window:
            try:
                with open(path, "r") as f:
                    # Basic check if it looks like a scene
                    content = f.read()
                    if '"entities":' in content: 
                        new_scene = SceneSerializer.from_json(content)
                        self.main_window.scene = new_scene
                        self.main_window.current_scene_path = path
                        self.main_window.viewport.bind_scene(new_scene)
                        
                        self.main_window.hierarchy_dock.scene = new_scene
                        self.main_window.hierarchy_dock.refresh()
                        self.main_window.inspector_dock.set_entity(None)
                        
                        # Ensure project settings (bg color) are applied
                        self.main_window.load_project_settings()
                        
                        print(f"Loaded scene from {path}")
                    else:
                        # Try to instantiate as prefab if it's not a scene?
                        # Or just warn
                        print("File does not look like a scene (might be a prefab)")
                        self.instantiate_prefab(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load scene: {e}")
