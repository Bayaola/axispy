from PyQt6.QtWidgets import QMainWindow, QToolBar, QFileDialog, QMessageBox, QTabWidget, QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDockWidget, QScrollArea, QFrame, QWidget, QSizePolicy
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QRect, QTimer
import qtawesome as qta
from editor.ui.engine_settings import theme_icon_color
import os
import sys
import json

from core.scene import Scene
from core.serializer import SceneSerializer
from editor.ui.viewport import PygameViewport
from editor.ui.hierarchy import HierarchyDock
from editor.ui.inspector import InspectorDock
from editor.ui.asset_manager import AssetManagerDock
from editor.ui.code_editor import ScriptEditorWidget
from editor.ui.animation_editor import AnimationEditor
from editor.ui.project_settings import ProjectSettingsDialog
from editor.ui.export_dialog import ExportDialog
from editor.ui.engine_settings import EngineSettings
from editor.ui.project_hub import ProjectHub
from editor.ui.console_dock import ConsoleDock
from editor.ui.chat_dock import ChatDock
from core.ai.chat_manager import ChatManager
from core.ai.providers.openai_provider import OpenAIProvider
from core.ai.providers.local_provider import LocalLLMProvider
from core.ai.providers.openrouter_provider import OpenRouterProvider
from core.ai.providers.google_provider import GoogleProvider
from core.ai.providers.anthropic_provider import AnthropicProvider
from core.ai.providers.nvidia_provider import NvidiaProvider
from core.resources import ResourceManager
from core.logger import get_logger
from core.runtime_launch import LaunchProfile, RuntimeCommandBuilder
from plugins.plugin_manager import PluginManager
from editor.undo_manager import UndoManager
from editor.ui.tilemap_editor import TilemapEditorDock
from core.components import Transform, TilemapComponent



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AxisPy Engine - Editor")
        self.resize(1280, 720)
        
        self.project_path = None
        self.current_scene_path = None
        self._last_launch_handle = None
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_all_plugins()
        self._logger = get_logger("editor")

        # Initialize core scene
        self.scene = Scene()
        # self.scene.setup_default()

        # Initialize UndoManager
        self.undo_manager = UndoManager(self)

        # Central Widget - Tab Widget
        self.central_tabs = QTabWidget()
        self.setCentralWidget(self.central_tabs)

        # Main viewport (Scene Tab)
        self.project_config = {}
        self.viewport = PygameViewport(self.scene, self, self.project_config)
        self.central_tabs.addTab(self.viewport, "Scene")
        
        # Code Editor (Script Tab)
        self.script_editor = ScriptEditorWidget(self)
        self.central_tabs.addTab(self.script_editor, "Scripts Editor")

        # Animation Editor
        self.animation_editor = AnimationEditor(self)
        self.central_tabs.addTab(self.animation_editor, "Animation Editor")

        # Docks
        self.hierarchy_dock = HierarchyDock(self.scene, self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.hierarchy_dock)
        
        self.inspector_dock = InspectorDock(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)

        # Set default size for Inspector
        self.resizeDocks([self.inspector_dock], [360], Qt.Orientation.Horizontal)
        
        self.asset_manager_dock = AssetManagerDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.asset_manager_dock)

        # Tilemap editor dock
        self.tilemap_editor_dock = TilemapEditorDock(self, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.tilemap_editor_dock)
        self.tilemap_editor_dock.hide()

        self.console_dock = ConsoleDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)
        self.splitDockWidget(self.asset_manager_dock, self.console_dock, Qt.Orientation.Vertical)

        # AI Chat dock - tabified with inspector
        self.chat_manager = ChatManager()
        self.chat_dock = ChatDock(self.chat_manager, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.chat_dock)
        self.tabifyDockWidget(self.inspector_dock, self.chat_dock)
        self.inspector_dock.raise_()  # Make inspector the active tab

        # Connect hierarchy selection to inspector
        self.hierarchy_dock.tree.itemSelectionChanged.connect(self.on_entity_selected)
        
        # Connect viewport modification to inspector
        self.viewport.entity_selected.connect(self.on_viewport_entity_selected)
        self.viewport.entity_modified.connect(self.inspector_dock.refresh_values)
        self.viewport.entity_deleted.connect(self.on_entity_deleted)

        # Tilemap editor <-> viewport integration (selection/edit mode handled in viewport todo)
        self.tilemap_editor_dock.edit_mode_changed.connect(self.viewport.set_tilemap_edit_mode)
        self.tilemap_editor_dock.tool_changed.connect(self.viewport.set_tilemap_tool)
        self.tilemap_editor_dock.active_layer_index_changed.connect(self.viewport.set_tilemap_active_layer)
        self.tilemap_editor_dock.selected_tile_changed.connect(self.viewport.set_tilemap_selected_tile)
        
        # Create Menus
        self.create_menus()

        # Toolbar for Run button
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)
        
        c = theme_icon_color()
        self.save_action = self.toolbar.addAction(qta.icon("fa5s.save", color=c), "Save")
        self.save_action.triggered.connect(self.save_current_context)

        # Add spacer to center the run buttons
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.run_current_scene_action = self.toolbar.addAction(qta.icon("fa5s.play", color="#5adc78"), "Run Current Scene")
        self.run_current_scene_action.triggered.connect(self.run_current_scene)
        self.run_game_action = self.toolbar.addAction(qta.icon("fa5s.gamepad", color="#5adc78"), "Run Game")
        self.run_game_action.triggered.connect(self.run_game)

        # Add spacer on the right to keep run buttons centered
        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer_right)


    def closeEvent(self, event):
        self.console_dock.cleanup()
        super().closeEvent(event)


    def open_engine_settings(self):
        dialog = EngineSettings(self)
        dialog.exec()
        
    def show_about_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("About AxisPy Engine")
        dialog.setFixedSize(560, 620)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        layout = QVBoxLayout(dialog)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "images", "logo.png")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            logo_pixmap = QPixmap(logo_path)
            logo_pixmap = logo_pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_label)
        
        # Title
        title_label = QLabel("AxisPy Engine")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Description (scrollable)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        description = QLabel(
            "<p>AxisPy Game Engine is a Python-based 2D game engine designed for developers "
            "who are passionate about both Python and game development in AI era.</p>"
            "<p>Built on top of Pygame, AxisPy aims to provide a structured and intuitive "
            "development experience inspired by modern engines, while staying "
            "fully within the Python ecosystem.</p>"
            "<p>Instead of competing with high-performance engines, AxisPy focuses on:</p>"
            "<ul>"
            "<li><b>Developer experience first</b>: clean architecture, readable code, and fast iteration</li>"
            "<li><b>Python-native workflows</b>: no need to switch languages or toolchains</li>"
            "<li><b>Rapid prototyping</b>: ideal for experimenting, learning, and building indie projects</li>"
            "<li><b>Extensibility</b>: leverage Python's vast ecosystem (AI, data, tools, etc.) directly in your games</li>"
            "</ul>"
            "<p>AxisPy is especially suited for:</p>"
            "<ul>"
            "<li>Indie developers who prefer Python</li>"
            "<li>Educators and students learning game development</li>"
            "<li>Developers exploring game ideas without heavy engine overhead</li>"
            "</ul>"
            "<p><i>AxisPy is not about replacing existing AAA engines, it's about empowering "
            "Python developers to create games in an environment they already love.</i></p>"
        )
        description.setTextFormat(Qt.TextFormat.RichText)
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignLeft)
        description.setContentsMargins(10, 10, 10, 10)
        
        scroll_area.setWidget(description)
        scroll_area.setMinimumHeight(400)
        layout.addWidget(scroll_area)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
        
    def update_theme_icons(self):
        c = theme_icon_color()
        # Toolbar
        self.save_action.setIcon(qta.icon("fa5s.save", color=c))
        self.run_current_scene_action.setIcon(qta.icon("fa5s.play", color="#5adc78"))
        self.run_game_action.setIcon(qta.icon("fa5s.gamepad", color="#5adc78"))
        # Menu actions
        for icon_name, action in self._menu_actions:
            action.setIcon(qta.icon(icon_name, color=c))
        # Propagate to panels
        if hasattr(self, 'hierarchy_dock'):
            self.hierarchy_dock.update_theme_icons()
        if hasattr(self, 'inspector_dock'):
            self.inspector_dock.update_theme_icons()
        if hasattr(self, 'asset_manager_dock'):
            self.asset_manager_dock.update_theme_icons()
        self.script_editor.apply_theme()

    def _create_symbol_icon(self, symbol, color, pixel_size):
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(color)
        font = QFont()
        font.setPixelSize(pixel_size)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 24, 24), Qt.AlignmentFlag.AlignCenter, symbol)
        painter.end()
        return QIcon(pixmap)

    def create_menus(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")
        
        file_menu.addSeparator()
        
        c = theme_icon_color()
        self._menu_actions = []  # (icon_name, QAction) for theme updates

        def _ma(icon_name, text, parent=self):
            act = QAction(qta.icon(icon_name, color=c), text, parent)
            self._menu_actions.append((icon_name, act))
            return act

        new_scene_action = _ma("fa5s.file", "New Scene")
        new_scene_action.setShortcut("Ctrl+N")
        new_scene_action.triggered.connect(self.new_scene)
        file_menu.addAction(new_scene_action)
        
        save_scene_action = _ma("fa5s.save", "Save")
        save_scene_action.setShortcut("Ctrl+S")
        save_scene_action.triggered.connect(self.save_current_context)
        file_menu.addAction(save_scene_action)
        
        open_scene_action = _ma("fa5s.folder-open", "Open Scene")
        open_scene_action.setShortcut("Ctrl+O")
        open_scene_action.triggered.connect(self.open_scene)
        file_menu.addAction(open_scene_action)
        
        file_menu.addSeparator()

        project_hub_action = _ma("fa5s.home", "Go To Projects Hub")
        project_hub_action.triggered.connect(self.open_project_hub)
        file_menu.addAction(project_hub_action)
        
        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        
        self.undo_action = _ma("fa5s.undo", "Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo_manager.undo)
        edit_menu.addAction(self.undo_action)
        
        self.redo_action = _ma("fa5s.redo", "Redo")
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.undo_manager.redo)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        settings_action = _ma("fa5s.cog", "Engine Settings")
        settings_action.triggered.connect(self.open_engine_settings)
        edit_menu.addAction(settings_action)

        project_menu = menubar.addMenu("&Project")
        project_settings_action = _ma("fa5s.sliders-h", "Project Settings")
        project_settings_action.triggered.connect(self.open_project_settings)
        project_menu.addAction(project_settings_action)

        export_action = _ma("fa5s.file-export", "Export...")
        export_action.triggered.connect(self.open_export_dialog)
        project_menu.addAction(export_action)
        
        # View Menu
        view_menu = menubar.addMenu("&View")
        
        # Hierarchy dock
        hierarchy_action = _ma("fa5s.sitemap", "Hierarchy")
        hierarchy_action.setCheckable(True)
        hierarchy_action.setChecked(True)
        hierarchy_action.triggered.connect(lambda checked: self.hierarchy_dock.setVisible(checked))
        view_menu.addAction(hierarchy_action)
        self.hierarchy_dock.visibilityChanged.connect(hierarchy_action.setChecked)
        
        # Inspector dock
        inspector_action = _ma("fa5s.info-circle", "Inspector")
        inspector_action.setCheckable(True)
        inspector_action.setChecked(True)
        inspector_action.triggered.connect(lambda checked: self.inspector_dock.setVisible(checked))
        view_menu.addAction(inspector_action)
        self.inspector_dock.visibilityChanged.connect(inspector_action.setChecked)
        
        # Asset Manager dock
        asset_manager_action = _ma("fa5s.folder", "Asset Manager")
        asset_manager_action.setCheckable(True)
        asset_manager_action.setChecked(True)
        asset_manager_action.triggered.connect(lambda checked: self.asset_manager_dock.setVisible(checked))
        view_menu.addAction(asset_manager_action)
        self.asset_manager_dock.visibilityChanged.connect(asset_manager_action.setChecked)
        
        # Console dock
        console_action = _ma("fa5s.terminal", "Console")
        console_action.setCheckable(True)
        console_action.setChecked(True)
        console_action.triggered.connect(lambda checked: self.console_dock.setVisible(checked))
        view_menu.addAction(console_action)
        self.console_dock.visibilityChanged.connect(console_action.setChecked)

        # AI Chat dock
        chat_action = _ma("fa5s.robot", "AI Assistant")
        chat_action.setCheckable(True)
        chat_action.setChecked(False)
        chat_action.triggered.connect(lambda checked: self.chat_dock.setVisible(checked))
        view_menu.addAction(chat_action)
        self.chat_dock.visibilityChanged.connect(chat_action.setChecked)
        
        # Animation Editor dock (if it exists as a dock)
        if hasattr(self, 'animation_dock'):
            animation_action = _ma("fa5s.film", "Animation Editor")
            animation_action.setCheckable(True)
            animation_action.setChecked(True)
            animation_action.triggered.connect(lambda checked: self.animation_dock.setVisible(checked))
            view_menu.addAction(animation_action)
            self.animation_dock.visibilityChanged.connect(animation_action.setChecked)
        
        # GameObject Menu
        go_menu = menubar.addMenu("&GameObject")
        create_empty_action = _ma("fa5s.cube", "Create Empty")
        create_empty_action.triggered.connect(self.create_empty_entity)
        go_menu.addAction(create_empty_action)
        
        # Help Menu
        help_menu = menubar.addMenu("&Help")
        about_action = _ma("fa5s.question-circle", "About")
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

        
    
    def open_script(self, path):
        self.script_editor.open_file(path)
        self.central_tabs.setCurrentWidget(self.script_editor)

    def open_animation_controller_editor(self, path):
        self.animation_editor.project_dir = self.project_path or "."
        self.animation_editor.open_file(path)
        self.central_tabs.setCurrentWidget(self.animation_editor)

    def open_animation_clip(self, path):
        self.animation_editor.project_dir = self.project_path or "."
        self.animation_editor.open_file(path)
        self.central_tabs.setCurrentWidget(self.animation_editor)

    def new_project(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select New Project Directory")
        if dir_path:
            dir_path = os.path.normpath(dir_path)
            self.project_path = dir_path
            os.environ["AXISPY_PROJECT_PATH"] = dir_path
            ResourceManager.set_base_path(dir_path)
            self.plugin_manager.notify_project_open(dir_path)
            self.asset_manager_dock.set_project_path(dir_path)
            self.setWindowTitle(f"AxisPy Engine - {dir_path}")
            self.load_project_settings()
            
            # Create project.config
            config_path = os.path.join(dir_path, "project.config")
            if not os.path.exists(config_path):
                default_config = {
                    "game_name": os.path.basename(dir_path),
                    "game_icon": "",
                    "entry_scene": "",
                    "resolution": {
                        "width": 800,
                        "height": 600
                    },
                    "display": {
                        "window": {
                            "width": 800,
                            "height": 600,
                            "resizable": True,
                            "fullscreen": False
                        },
                        "virtual_resolution": {
                            "width": 800,
                            "height": 600
                        },
                        "stretch": {
                            "mode": "fit",
                            "aspect": "keep",
                            "scale": "fractional"
                        }
                    },
                    "groups": [],
                    "physics_collision_matrix": {},
                    "version": "1.0.0"
                }
                default_config["layers"] = ["Default"]
                try:
                    with open(config_path, "w") as f:
                        json.dump(default_config, f, indent=4)
                except Exception as e:
                    print(f"Failed to create project.config: {e}")

            # Reset scene
            self.scene = Scene()
            self.scene.ensure_main_camera()
            self.viewport.bind_scene(self.scene)
            self.hierarchy_dock.scene = self.scene
            self.hierarchy_dock.refresh()
            self.inspector_dock.set_entity(None)
            
            # Hide tilemap editor when creating new project (now using component UI)
            # self._update_tilemap_editor_visibility([])
            
            self.load_last_opened_scene()

    def open_project(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Open Project Directory")
        if dir_path:
            dir_path = os.path.normpath(dir_path)
            self.project_path = dir_path
            os.environ["AXISPY_PROJECT_PATH"] = dir_path
            ResourceManager.set_base_path(dir_path)
            self.plugin_manager.notify_project_open(dir_path)
            self.asset_manager_dock.set_project_path(dir_path)
            self.setWindowTitle(f"AxisPy Engine - {dir_path}")
            self.load_project_settings()
            
            # Hide tilemap editor when opening project (now using component UI)
            # self._update_tilemap_editor_visibility([])
            
            self.load_last_opened_scene()

    def new_scene(self):
        if not self.project_path:
            QMessageBox.warning(self, "Warning", "Please create or open a project first.")
            return
            
        # Confirm save current scene?
        # For now, just reset
        self.scene = Scene("New Scene")
        self.scene.ensure_main_camera()
        self.current_scene_path = None
        
        # Re-link viewport
        self.viewport.bind_scene(self.scene)
        
        # Refresh UI
        self.hierarchy_dock.scene = self.scene
        self.hierarchy_dock.refresh()
        self.inspector_dock.set_entity(None)
        
        # Hide tilemap editor when creating new project (now using component UI)
        # self._update_tilemap_editor_visibility([])

    def save_current_context(self):
        # Check which tab is active
        current_index = self.central_tabs.currentIndex()
        if current_index == 0: # Scene tab
            self.save_scene()
        elif current_index == 1: # Script tab
            self.script_editor.save_file()

    def save_scene(self):
        if not self.project_path:
            QMessageBox.warning(self, "Warning", "Please create or open a project first.")
            return False

        if not self.current_scene_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Scene", self.project_path, "Scene Files (*.scn)")
            if file_path:
                self.current_scene_path = file_path
            else:
                return False
        
        try:
            self.scene.editor_view_state = self.viewport.get_scene_view_state()
            data = SceneSerializer.to_json(self.scene)
            with open(self.current_scene_path, "w") as f:
                f.write(data)
            self.scene._file_path = self.current_scene_path  # Track file path for AI tools
            self._persist_last_opened_scene(self.current_scene_path)
            print(f"Scene saved to {self.current_scene_path}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save scene: {e}")
            return False

    def open_scene(self):
        if not self.project_path:
             QMessageBox.warning(self, "Warning", "Please create or open a project first.")
             return
             
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Scene", self.project_path, "Scene Files (*.scn)")
        if file_path:
            self._load_scene_from_path(file_path, show_error=True)

    def create_empty_entity(self):
        entity = self.scene.world.create_entity("New Entity")
        # Add Transform by default
        from core.components import Transform
        entity.add_component(Transform())
        self.hierarchy_dock.refresh()

    def load_project_settings(self):
        if not self.project_path:
            return
            
        config_path = os.path.join(self.project_path, "project.config")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    # Store config and update viewport
                    self.project_config = config
                    self.viewport.update_project_config(config)
                    
                    bg_color = config.get("background_color", [33, 33, 33])
                    # Ensure integer values
                    bg_color = [int(c) for c in bg_color]
                    self.viewport.bg_color = tuple(bg_color)

                    display = config.get("display", {})
                    virtual = display.get("virtual_resolution", {})
                    res = config.get("resolution", {"width": 800, "height": 600})
                    game_width = int(virtual.get("width", res.get("width", 800)))
                    game_height = int(virtual.get("height", res.get("height", 600)))
                    self.viewport.game_resolution = (game_width, game_height)

                    layers = config.get("layers", ["Default"])
                    normalized_layers = []
                    seen = set()
                    if isinstance(layers, list):
                        for layer in layers:
                            name = str(layer).strip()
                            if not name:
                                continue
                            lowered = name.lower()
                            if lowered in seen:
                                continue
                            seen.add(lowered)
                            normalized_layers.append(name)
                    if "default" in seen:
                        normalized_layers = [layer for layer in normalized_layers if layer.lower() != "default"]
                    normalized_layers.insert(0, "Default")
                    self.scene.world.layers = normalized_layers
                    valid_layers = set(normalized_layers)
                    for entity in self.scene.world.entities:
                        if entity.layer not in valid_layers:
                            entity.set_layer("Default")

                    groups = config.get("groups", [])
                    normalized_groups = []
                    group_seen = set()
                    if isinstance(groups, list):
                        for group_name in groups:
                            group_text = str(group_name).strip()
                            if not group_text:
                                continue
                            lowered_group = group_text.lower()
                            if lowered_group in group_seen:
                                continue
                            group_seen.add(lowered_group)
                            normalized_groups.append(group_text)

                    world = self.scene.world
                    for group_name in list(world.groups.keys()):
                        if group_name not in normalized_groups:
                            members = list(world.groups.get(group_name, set()))
                            for entity in members:
                                entity.remove_group(group_name)
                    for group_name in normalized_groups:
                        world.groups.setdefault(group_name, set())

                    raw_matrix = config.get("physics_collision_matrix", {})
                    if not isinstance(raw_matrix, dict):
                        raw_matrix = {}
                    normalized_matrix = {}
                    for row_group in normalized_groups:
                        targets = raw_matrix.get(row_group, normalized_groups)
                        if not isinstance(targets, list):
                            targets = normalized_groups
                        allowed_targets = []
                        target_seen = set()
                        for target in targets:
                            target_name = str(target).strip()
                            if target_name not in normalized_groups:
                                continue
                            lowered_target = target_name.lower()
                            if lowered_target in target_seen:
                                continue
                            target_seen.add(lowered_target)
                            allowed_targets.append(target_name)
                        normalized_matrix[row_group] = allowed_targets
                    for row_group in normalized_groups:
                        for target in list(normalized_matrix.get(row_group, [])):
                            peer = normalized_matrix.setdefault(target, [])
                            if row_group not in peer:
                                peer.append(row_group)

                    world.physics_group_order = list(normalized_groups)
                    world.physics_collision_matrix = normalized_matrix
                    
                    print(f"Loaded bg_color: {bg_color}, res: {self.viewport.game_resolution}")

                    # Configure AI provider
                    self._configure_ai_provider(config)
            except Exception as e:
                print(f"Failed to load project settings: {e}")

    def _configure_ai_provider(self, config: dict):
        """Create and set the AI provider from project config."""
        # First: ensure sessions are loaded (before any callbacks are set)
        if self.project_path:
            self.chat_manager.set_project_path(self.project_path)
            # Wire context and tool executor
            self.chat_manager.context_builder.set_project_path(self.project_path)
            self.chat_manager.tool_executor.set_project_path(self.project_path)
            # Refresh UI
            self.chat_dock.refresh_sessions()
            self.chat_dock._reload_messages()

        ai_cfg = config.get("ai", {})
        provider_name = ai_cfg.get("provider", "openai")

        if provider_name == "openrouter":
            provider = OpenRouterProvider(
                api_key=ai_cfg.get("openrouter_api_key", ""),
                model=ai_cfg.get("openrouter_model", "deepseek/deepseek-chat:free"),
                base_url=ai_cfg.get("openrouter_url", ""),
            )
        elif provider_name == "local":
            provider = LocalLLMProvider(
                model=ai_cfg.get("local_model", "llama3"),
                base_url=ai_cfg.get("local_url", "http://localhost:11434/v1"),
            )
        elif provider_name == "google":
            provider = GoogleProvider(
                api_key=ai_cfg.get("google_api_key", ""),
                model=ai_cfg.get("google_model", "gemini-2.5-flash"),
            )
        elif provider_name == "anthropic":
            provider = AnthropicProvider(
                api_key=ai_cfg.get("anthropic_api_key", ""),
                model=ai_cfg.get("anthropic_model", "claude-3-5-sonnet-latest"),
            )
        elif provider_name == "nvidia":
            provider = NvidiaProvider(
                api_key=ai_cfg.get("nvidia_api_key", ""),
                model=ai_cfg.get("nvidia_model", "google/gemma-4-31b-it"),
                base_url=ai_cfg.get("nvidia_url", "https://integrate.api.nvidia.com/v1"),
            )
        else:
            provider = OpenAIProvider(
                api_key=ai_cfg.get("api_key", ""),
                model=ai_cfg.get("model", "gpt-4o-mini"),
                base_url=ai_cfg.get("base_url", "https://api.openai.com/v1"),
            )

        self.chat_manager.set_provider(provider)

        # Wire scene getters
        self.chat_manager.context_builder.set_scene_getter(lambda: self.scene)
        self.chat_manager.context_builder.set_selected_entities_getter(
            lambda: self.inspector_dock.current_entities if hasattr(self.inspector_dock, 'current_entities') else []
        )
        self.chat_manager.tool_executor.set_scene_getter(lambda: self.scene)
        self.chat_manager.tool_executor.set_selected_entities_getter(
            lambda: self.inspector_dock.current_entities if hasattr(self.inspector_dock, 'current_entities') else []
        )
        self.chat_manager.tool_executor.set_scene_reload_callback(self._reload_scene_from_ai)

        self.chat_dock.update_model_label()

    def load_last_opened_scene(self):
        if not self.project_path:
            return False
        config = self._read_project_config()
        if not config:
            return False
        scene_path = self._resolve_scene_path(config.get("last_opened_scene", ""))
        if not scene_path:
            return False
        if not os.path.exists(scene_path):
            return False
        return self._load_scene_from_path(scene_path, show_error=False)

    def _load_scene_from_path(self, file_path, show_error=True):
        try:
            with open(file_path, "r") as f:
                self.scene = SceneSerializer.from_json(f.read())
                self.scene._file_path = file_path  # Track file path for AI tools
                self.current_scene_path = file_path
                self.viewport.bind_scene(self.scene)
                self.hierarchy_dock.scene = self.scene
                self.hierarchy_dock.refresh()
                self.inspector_dock.set_entity(None)
                
                # Hide tilemap editor when loading scene (now using component UI)
                # self._update_tilemap_editor_visibility([])
                
                self.load_project_settings()
                self._persist_last_opened_scene(file_path)
                print(f"Scene loaded from {file_path}")
            return True
        except Exception as e:
            if show_error:
                QMessageBox.critical(self, "Error", f"Failed to load scene: {e}")
            else:
                print(f"Failed to auto-load scene: {e}")
            return False

    def _reload_scene_from_ai(self, file_path: str):
        """Reload scene after AI tool has edited the scene file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                scene_data = json.load(f)
            # Reload entities from the modified file
            from core.serializer import SceneSerializer
            restored = SceneSerializer.from_json(json.dumps(scene_data))
            restored._file_path = file_path
            self.scene = restored
            self.current_scene_path = file_path
            self.viewport.bind_scene(self.scene)
            self.hierarchy_dock.scene = self.scene
            self.hierarchy_dock.refresh()
            self.inspector_dock.set_entity(None)
            print(f"Scene reloaded after AI edit: {file_path}")
        except Exception as e:
            print(f"Failed to reload scene after AI edit: {e}")

    def _read_project_config(self):
        if not self.project_path:
            return {}
        config_path = os.path.join(self.project_path, "project.config")
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_project_config(self, config):
        if not self.project_path:
            return
        config_path = os.path.join(self.project_path, "project.config")
        try:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Failed to save project settings: {e}")

    def _persist_last_opened_scene(self, scene_path):
        if not self.project_path or not scene_path:
            return
        config = self._read_project_config()
        abs_project = os.path.abspath(self.project_path)
        abs_scene = os.path.abspath(scene_path)
        try:
            rel_scene = os.path.relpath(abs_scene, abs_project)
            if rel_scene.startswith(".."):
                scene_value = abs_scene
            else:
                scene_value = rel_scene
        except ValueError:
            scene_value = abs_scene
        config["last_opened_scene"] = ResourceManager.portable_path(scene_value)
        self._write_project_config(config)

    def _resolve_scene_path(self, scene_value):
        if not scene_value:
            return ""
        native_value = ResourceManager.to_os_path(scene_value)
        if os.path.isabs(native_value):
            return native_value
        if not self.project_path:
            return ""
        return os.path.normpath(os.path.join(self.project_path, native_value))

    def open_project_settings(self):
        if not self.project_path:
            QMessageBox.warning(self, "Warning", "Please create or open a project first.")
            return
            
        dialog = ProjectSettingsDialog(self.project_path, self)
        if dialog.exec():
            # Reload settings if saved
            self.load_project_settings()

    def open_project_hub(self):
        if not self.save_scene():
            return
        hub = ProjectHub()
        hub.project_selected.connect(self._launch_editor_from_hub)
        app = QApplication.instance()
        if app and not hasattr(app, "_axispy_windows"):
            app._axispy_windows = []
        if app:
            app._axispy_windows.append(hub)
        hub.show()
        self.close()

    def _launch_editor_from_hub(self, project_path):
        project_path = os.path.normpath(project_path)
        os.environ["AXISPY_PROJECT_PATH"] = project_path
        ResourceManager.set_base_path(project_path)
        main_window = MainWindow()
        main_window.project_path = project_path
        main_window.asset_manager_dock.set_project_path(project_path)
        main_window.setWindowTitle(f"AxisPy Engine - {project_path}")
        main_window.load_project_settings()
        main_window.load_last_opened_scene()
        app = QApplication.instance()
        if app and not hasattr(app, "_axispy_windows"):
            app._axispy_windows = []
        if app:
            app._axispy_windows.append(main_window)
        main_window.show()

    def on_viewport_entity_selected(self, entities):
        # Update hierarchy selection to match viewport without triggering recursion
        self.hierarchy_dock.tree.blockSignals(True)
        # Ensure it's a list
        if not isinstance(entities, list):
            entities = [entities] if entities else []
            
        self.hierarchy_dock.select_entities(entities)
        self.hierarchy_dock.tree.blockSignals(False)
        self.inspector_dock.set_entities(entities)
        
        # Update tilemap editor visibility (now using component UI)
        # self._update_tilemap_editor_visibility(entities)

    def on_entity_deleted(self, _):
        # Refresh hierarchy and clear inspector when an entity is deleted from viewport
        self.hierarchy_dock.refresh()
        self.inspector_dock.set_entities([])
        
        # Hide tilemap editor when entity is deleted (now using component UI)
        # self._update_tilemap_editor_visibility([])
    
    
    def on_entity_selected(self):
        items = self.hierarchy_dock.tree.selectedItems()
        entities = []
        for item in items:
            entity_id = item.data(0, Qt.ItemDataRole.UserRole)
            # Resolve entity from ID
            entity = self.scene.world.get_entity_by_id(entity_id)
            if entity:
                entities.append(entity)
        
        self.inspector_dock.set_entities(entities)
        
        # Update tilemap editor visibility (now using component UI)
        # self._update_tilemap_editor_visibility(entities)
        
        # Sync viewport selection
        self.viewport.selected_entities = entities
        if entities:
            # Pass all entities to gizmo
            self.viewport.gizmo.set_targets(entities)
        else:
            self.viewport.gizmo.set_targets([])

    def _launch_runtime(self, scene_data: str, scene_name: str):
        base_path = self.project_path if self.project_path else os.getcwd()
        engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        temp_scene_path = os.path.join(base_path, "temp_scene.scn")
        profile = LaunchProfile(
            module="core.player",
            scene_file_name=temp_scene_path,
            working_directory=engine_root,
            report_directory=os.path.join(base_path, ".axispy", "reports"),
            python_executable=sys.executable,
            python_path_entries=[engine_root],
            env_overrides={
                "AXISPY_PROJECT_PATH": base_path,
                "AXISPY_EDITOR_MODE": "1"  # Flag to indicate running in editor
            }
        )
        try:
            handle = RuntimeCommandBuilder.launch(profile, scene_data, use_pipe=True)
            self._last_launch_handle = handle
            self.console_dock.set_player_process(handle.process)
            self._logger.info(
                "Runtime launched",
                scene_name=scene_name,
                command=" ".join(handle.command),
                scene_path=handle.scene_path,
                stdout_report=handle.report_stdout_path,
                stderr_report=handle.report_stderr_path,
                pid=handle.process.pid
            )
            self.statusBar().showMessage(f"Runtime launched (PID {handle.process.pid})", 4000)
            QTimer.singleShot(500, self._check_runtime_process_health)
        except Exception as error:
            self._logger.error("Runtime launch failed", scene_name=scene_name, error=str(error))
            QMessageBox.critical(self, "Runtime Launch Failed", str(error))

    def run_current_scene(self):
        self.scene.editor_view_state = self.viewport.get_scene_view_state()
        scene_data = SceneSerializer.to_json(self.scene)
        self._launch_runtime(scene_data, self.scene.name)

    def run_game(self):
        if not self.project_path:
            QMessageBox.warning(self, "Warning", "Please create or open a project first.")
            return
        config = self._read_project_config()
        entry_scene_value = str(config.get("entry_scene", "")).strip()
        if not entry_scene_value:
            QMessageBox.warning(self, "Run Game", "No entry scene set in Project Settings.")
            return
        entry_scene_path = self._resolve_scene_path(entry_scene_value)
        if not entry_scene_path or not os.path.exists(entry_scene_path):
            QMessageBox.warning(self, "Run Game", f"Entry scene not found:\n{entry_scene_value}")
            return
        try:
            with open(entry_scene_path, "r", encoding="utf-8") as f:
                scene_data = f.read()
            scene_name = os.path.basename(entry_scene_path)
            self._launch_runtime(scene_data, scene_name)
        except Exception as error:
            QMessageBox.critical(self, "Run Game", f"Failed to read entry scene:\n{error}")

    def open_export_dialog(self):
        if not self.project_path:
            QMessageBox.warning(self, "Warning", "Please create or open a project first.")
            return
        dialog = ExportDialog(self.project_path, self)
        dialog.exec()

    def _check_runtime_process_health(self):
        handle = self._last_launch_handle
        if not handle:
            return
        process = handle.process
        if process.poll() is None:
            return
        
        # Check if process exited with an error
        if process.returncode == 0:
            # Normal exit - just log info and clean up
            self._logger.info(
                "Runtime exited normally",
                return_code=process.returncode
            )
            handle.close_logs()
            self._last_launch_handle = None
            return
            
        # Process exited with error
        handle.close_logs()
        error_details = ""
        try:
            if os.path.exists(handle.report_stderr_path):
                with open(handle.report_stderr_path, "r", encoding="utf-8") as file:
                    error_details = file.read(1000).strip()
        except Exception:
            error_details = ""
        self._logger.error(
            "Runtime exited with error",
            return_code=process.returncode,
            stderr_report=handle.report_stderr_path,
            stderr_preview=error_details
        )
        message = f"Runtime exited with error code {process.returncode}."
        if error_details:
            message = f"{message}\n\n{error_details}"
        QMessageBox.critical(self, "Runtime Error", message)
        self._last_launch_handle = None
