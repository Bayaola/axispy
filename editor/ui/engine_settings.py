import os
import sys
import json
import platform
import shutil
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QLabel, QApplication, QPushButton, QHBoxLayout
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

_APP_NAME = "AxisPyGameEngine"

def get_user_config_dir() -> str:
    """Return the OS-appropriate user config directory for the engine.
    
    Windows: ~/Documents/AxisPyGameEngine/
    macOS:   ~/Documents/AxisPyGameEngine/
    Linux:   ~/.config/AxisPyGameEngine/
    """
    system = platform.system()
    if system == "Windows":
        config_dir = os.path.join(os.path.expanduser("~"), "Documents", _APP_NAME)
    elif system == "Darwin":
        config_dir = os.path.join(os.path.expanduser("~"), "Documents", _APP_NAME)
    else:
        config_dir = os.path.join(os.path.expanduser("~"), ".config", _APP_NAME)
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

def _migrate_config_file(filename: str):
    """Migrate a config file from the old location (next to source) to the user config dir."""
    old_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    new_path = os.path.join(get_user_config_dir(), filename)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            shutil.copy2(old_path, new_path)
        except Exception:
            pass

_migrate_config_file("engine_config.json")
_migrate_config_file("hub_config.json")

SETTINGS_PATH = os.path.join(get_user_config_dir(), "engine_config.json")

def load_engine_config():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}

def save_engine_config(data: dict):
    payload = data if isinstance(data, dict) else {}
    try:
        with open(SETTINGS_PATH, "w") as file:
            json.dump(payload, file, indent=4)
    except Exception:
        pass


def load_saved_theme_mode():
    data = load_engine_config()
    mode = str(data.get("theme_mode", "Dark")).strip().lower()
    if mode in {"dark", "light"}:
        return mode.capitalize()
    return "Dark"


def is_dark_mode():
    """Return True if the current theme is dark."""
    return load_saved_theme_mode() == "Dark"


def theme_icon_color():
    """Return an icon color suitable for the current theme (light text on dark, dark text on light)."""
    return "#c8c8c8" if is_dark_mode() else "#333333"


def theme_arrow_color():
    """Return an arrow/indicator color suitable for the current theme."""
    return "#aaaaaa" if is_dark_mode() else "#555555"


def save_theme_mode(mode: str):
    normalized_mode = "Dark" if str(mode).strip().lower() == "dark" else "Light"
    data = load_engine_config()
    data["theme_mode"] = normalized_mode
    save_engine_config(data)


def apply_theme_mode(app, mode: str):
    if str(mode).strip().lower() == "dark":
        apply_dark_theme(app)
    else:
        apply_light_theme(app)


class EngineSettings(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Engine Settings")
        self.resize(320, 160)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Theme Selection
        theme_label = QLabel("Theme Mode:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(load_saved_theme_mode())
        
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)
        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.close_button = QPushButton("Close")
        self.save_button = QPushButton("Save")
        self.close_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.save_changes)
        actions.addWidget(self.close_button)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)

    def save_changes(self):
        text = self.theme_combo.currentText()
        save_theme_mode(text)
        app = QApplication.instance()
        apply_theme_mode(app, text)
        if self.parent() and hasattr(self.parent(), 'update_theme_icons'):
            self.parent().update_theme_icons()
        self.accept()

def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)

def apply_light_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 231, 227))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(palette)
