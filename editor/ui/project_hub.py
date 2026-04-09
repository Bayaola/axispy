import os
import json
import hashlib
from core.resources import ResourceManager
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QListWidget, QFileDialog, QMessageBox, QListWidgetItem, QInputDialog, QLineEdit, QAbstractItemView)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QColor, QFont, QDesktopServices, QShortcut, QKeySequence
from editor.ui.engine_settings import load_saved_theme_mode, get_user_config_dir

class ProjectHub(QWidget):
    project_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AxisPy Engine - Project Hub")
        self.resize(500, 560)
        
        self.recent_projects = []
        self.config_path = os.path.join(get_user_config_dir(), "hub_config.json")
        self.filter_text = ""
        
        self.load_config()
        self.setup_ui()
        
    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    items = data.get("recent_projects", [])
                    normalized = []
                    for item in items:
                        if isinstance(item, dict):
                            path = item.get("path", "")
                        else:
                            path = item
                        if not path:
                            continue
                        norm = os.path.normpath(path)
                        if os.path.exists(norm):
                            normalized.append(norm)
                    self.recent_projects = normalized
            except Exception as e:
                print(f"Failed to load hub config: {e}")
                
    def save_config(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump({"recent_projects": self.recent_projects}, f, indent=4)
        except Exception as e:
            print(f"Failed to save hub config: {e}")

    def add_recent_project(self, path):
        normalized = os.path.normpath(path)
        if normalized in self.recent_projects:
            self.recent_projects.remove(normalized)
        self.recent_projects.insert(0, normalized)
        self.recent_projects = self.recent_projects[:10]
        self.save_config()
        self.refresh_list()

    def setup_ui(self):
        self.apply_theme_style(load_saved_theme_mode())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header_layout = QVBoxLayout()
        title = QLabel("Project Hub")
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QLabel("Open a recent project or create a new one.")
        subtitle.setStyleSheet("color: #aeb8c8;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name or path")
        self.search_edit.textChanged.connect(self.on_search_changed)
        layout.addWidget(self.search_edit)

        actions_layout = QHBoxLayout()
        self.new_btn = QPushButton("New Project")
        self.new_btn.clicked.connect(self.new_project)
        actions_layout.addWidget(self.new_btn)

        self.open_btn = QPushButton("Open Existing")
        self.open_btn.clicked.connect(self.open_project_dialog)
        actions_layout.addWidget(self.open_btn)

        self.open_selected_btn = QPushButton("Open Selected")
        self.open_selected_btn.clicked.connect(self.open_selected_project)
        self.open_selected_btn.setEnabled(False)
        self.open_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b6bff;
                border: 1px solid #3874ff;
                border-radius: 8px;
                padding: 8px 14px;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3a78ff;
            }
            QPushButton:disabled {
                background-color: #1f2735;
                color: #7f8898;
                border: 1px solid #2a3342;
            }
        """)
        actions_layout.addWidget(self.open_selected_btn)

        self.reveal_btn = QPushButton("Reveal Folder")
        self.reveal_btn.clicked.connect(self.reveal_selected_project)
        self.reveal_btn.setEnabled(False)
        actions_layout.addWidget(self.reveal_btn)

        self.delete_btn = QPushButton("Remove from List")
        self.delete_btn.clicked.connect(self.delete_selected_project)
        self.delete_btn.setEnabled(False)
        actions_layout.addWidget(self.delete_btn)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        self.project_list = QListWidget()
        self.project_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.project_list.setIconSize(QSize(40, 40))
        self.project_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.project_list.setWordWrap(True)
        self.project_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.project_list.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.project_list)

        self.empty_label = QLabel("No projects match your search.")
        self.empty_label.setStyleSheet("color: #aeb8c8;")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_edit.setFocus)
        QShortcut(QKeySequence("Return"), self, activated=self.open_selected_project)
        QShortcut(QKeySequence("Enter"), self, activated=self.open_selected_project)
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_selected_project)

        self.refresh_list()

    def apply_theme_style(self, mode: str):
        if str(mode).strip().lower() == "light":
            self.setStyleSheet("""
                QWidget {
                    background-color: #f4f6f9;
                    color: #1c2330;
                    font-size: 13px;
                }
                QLineEdit {
                    background-color: #ffffff;
                    border: 1px solid #c8d1df;
                    border-radius: 8px;
                    padding: 8px 10px;
                }
                QListWidget {
                    background-color: #ffffff;
                    border: 1px solid #c8d1df;
                    border-radius: 10px;
                    padding: 6px;
                }
                QListWidget::item {
                    border-radius: 8px;
                    padding: 8px;
                    margin: 2px 0px;
                }
                QListWidget::item:selected {
                    background-color: #2b6bff;
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #e8edf5;
                    border: 1px solid #c3cedf;
                    border-radius: 8px;
                    padding: 8px 14px;
                }
                QPushButton:hover {
                    background-color: #dbe4f1;
                }
                QPushButton:disabled {
                    color: #7f8898;
                    background-color: #e5e9f0;
                    border: 1px solid #d2d9e6;
                }
            """)
            return
        self.setStyleSheet("""
            QWidget {
                background-color: #171b22;
                color: #e7edf6;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #10151c;
                border: 1px solid #2a3342;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QListWidget {
                background-color: #10151c;
                border: 1px solid #2a3342;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                border-radius: 8px;
                padding: 8px;
                margin: 2px 0px;
            }
            QListWidget::item:selected {
                background-color: #2b6bff;
                color: #ffffff;
            }
            QPushButton {
                background-color: #263145;
                border: 1px solid #31425d;
                border-radius: 8px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #2f3c55;
            }
            QPushButton:disabled {
                color: #7f8898;
                background-color: #1f2735;
                border: 1px solid #2a3342;
            }
        """)
        
    def on_selection_changed(self):
        has_selection = bool(self.project_list.selectedItems())
        self.open_selected_btn.setEnabled(has_selection)
        self.reveal_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def delete_selected_project(self):
        items = self.project_list.selectedItems()
        if items:
            path = items[0].data(Qt.ItemDataRole.UserRole)
            if path in self.recent_projects:
                reply = QMessageBox.question(self, "Remove Project", 
                                           f"Are you sure you want to remove '{os.path.basename(path)}' from the recent list?\n(This will NOT delete the project files)",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.recent_projects.remove(path)
                    self.save_config()
                    self.refresh_list()

    def open_selected_project(self):
        items = self.project_list.selectedItems()
        if items:
            path = items[0].data(Qt.ItemDataRole.UserRole)
            self.open_project(path)

    def reveal_selected_project(self):
        items = self.project_list.selectedItems()
        if not items:
            return
        path = items[0].data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def on_search_changed(self, text):
        self.filter_text = text.strip().lower()
        self.refresh_list()

    def _read_project_config(self, project_path):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _resolve_game_icon_path(self, project_path, game_icon_value):
        if not game_icon_value:
            return ""
        value = ResourceManager.to_os_path(str(game_icon_value))
        if os.path.isabs(value):
            return value if os.path.exists(value) else ""
        resolved = os.path.normpath(os.path.join(project_path, value))
        return resolved if os.path.exists(resolved) else ""

    def _project_color(self, key):
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        hue = int(digest[:2], 16) % 360
        return QColor.fromHsv(hue, 110, 190)

    def _create_fallback_icon(self, project_name, project_path):
        pixmap = QPixmap(40, 40)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = self._project_color(project_path)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 40, 40, 6, 6)
        letter = (project_name or "?").strip()[:1].upper() or "?"
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#f3f6fb"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)
        painter.end()
        return QIcon(pixmap)

    def _create_project_icon(self, project_name, project_path, game_icon_value):
        icon_path = self._resolve_game_icon_path(project_path, game_icon_value)
        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                return QIcon(scaled)
        return self._create_fallback_icon(project_name, project_path)
            
    def refresh_list(self):
        selected_items = self.project_list.selectedItems()
        selected_path = selected_items[0].data(Qt.ItemDataRole.UserRole) if selected_items else None
        self.project_list.clear()
        for path in self.recent_projects:
            if not os.path.exists(path):
                continue
            config_data = self._read_project_config(path)
            name = os.path.basename(path)
            if "game_name" in config_data and str(config_data.get("game_name")).strip():
                name = str(config_data.get("game_name")).strip()
            if self.filter_text:
                searchable = f"{name} {path}".lower()
                if self.filter_text not in searchable:
                    continue
            subtitle = os.path.normpath(path)
            item = QListWidgetItem(f"{name}\n{subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(subtitle)
            item.setSizeHint(QSize(0, 52))
            item.setIcon(self._create_project_icon(name, path, config_data.get("game_icon", "")))
            self.project_list.addItem(item)
            if selected_path and selected_path == path:
                item.setSelected(True)
        has_rows = self.project_list.count() > 0
        if has_rows and not self.project_list.selectedItems():
            self.project_list.setCurrentRow(0)
        self.empty_label.setVisible(not has_rows)
        self.on_selection_changed()
            
    def on_item_double_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.open_project(path)
        
    def new_project(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select New Project Parent Directory")
        if dir_path:
            name, ok = QInputDialog.getText(self, "New Project", "Project Name:")
            if ok and name:
                project_path = os.path.join(dir_path, name)
                try:
                    os.makedirs(project_path)
                    
                    # Create standard project directories
                    os.makedirs(os.path.join(project_path, "assets", "images"), exist_ok=True)
                    os.makedirs(os.path.join(project_path, "assets", "sounds"), exist_ok=True)
                    os.makedirs(os.path.join(project_path, "assets", "musics"), exist_ok=True)
                    os.makedirs(os.path.join(project_path, "assets", "fonts"), exist_ok=True)
                    os.makedirs(os.path.join(project_path, "scenes"), exist_ok=True)
                    os.makedirs(os.path.join(project_path, "scripts"), exist_ok=True)
                    os.makedirs(os.path.join(project_path, "prefabs"), exist_ok=True)
                    os.makedirs(os.path.join(project_path, "animations"), exist_ok=True)
                    
                    # Create default config immediately
                    config_path = os.path.join(project_path, "project.config")
                    default_config = {
                        "game_name": name,
                        "game_icon": "",
                        "resolution": {"width": 800, "height": 600},
                        "display": {
                            "window": {"width": 800, "height": 600, "resizable": True, "fullscreen": False},
                            "virtual_resolution": {"width": 800, "height": 600},
                            "stretch": {"mode": "fit", "aspect": "keep", "scale": "fractional"}
                        },
                        "version": "1.0.0"
                    }
                    with open(config_path, "w") as f:
                        json.dump(default_config, f, indent=4)
                        
                    self.open_project(project_path)
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to create project: {e}")

    def open_project_dialog(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Open Project Directory")
        if dir_path:
            self.open_project(dir_path)

    def open_project(self, path):
        self.add_recent_project(path)
        self.project_selected.emit(path)
        self.close()
