import json
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
                             QGroupBox, QLabel, QPushButton, QColorDialog, QHBoxLayout,
                             QComboBox, QFileDialog, QScrollArea)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt

_manager = None
_ui_hooked = False

def register_plugin(manager):
    global _manager
    _manager = manager

def on_load(context):
    _inject_project_settings()

def on_unload():
    pass

def on_project_open(project_path: str):
    pass


def _inject_project_settings():
    try:
        from editor.ui.project_settings import ProjectSettingsDialog

        original_setup_ui = ProjectSettingsDialog.setup_ui
        original_save_config = ProjectSettingsDialog.save_config

        def new_setup_ui(self):
            original_setup_ui(self)

            # Find or create "Plugins" tab
            plugins_tab_index = -1
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "Plugins":
                    plugins_tab_index = i
                    break

            if plugins_tab_index == -1:
                self.plugins_tab = QWidget()
                self.plugins_layout = QVBoxLayout(self.plugins_tab)
                self.plugins_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(self.plugins_tab)
                self.tabs.addTab(scroll, "Plugins")
            else:
                scroll_widget = self.tabs.widget(plugins_tab_index)
                if isinstance(scroll_widget, QScrollArea):
                    self.plugins_tab = scroll_widget.widget()
                else:
                    self.plugins_tab = scroll_widget
                self.plugins_layout = self.plugins_tab.layout()

            designer_config = self.config_data.get("pygbag_designer", {})

            # ── Pygbag Designer group ────────────────────────────────
            group = QGroupBox("Pygbag Loading Screen Designer")
            layout = QFormLayout(group)

            # Background color
            self.pgd_bg_color = designer_config.get("background_color", "#222222")
            self.pgd_bg_btn = QPushButton()
            _set_color_btn(self.pgd_bg_btn, self.pgd_bg_color)
            self.pgd_bg_btn.clicked.connect(lambda: _pick_color(self, "pgd_bg_color", self.pgd_bg_btn))
            layout.addRow("Background Color:", self.pgd_bg_btn)

            # Text color
            self.pgd_text_color = designer_config.get("text_color", "#cccccc")
            self.pgd_text_btn = QPushButton()
            _set_color_btn(self.pgd_text_btn, self.pgd_text_color)
            self.pgd_text_btn.clicked.connect(lambda: _pick_color(self, "pgd_text_color", self.pgd_text_btn))
            layout.addRow("Text Color:", self.pgd_text_btn)

            # Accent / progress bar color
            self.pgd_accent_color = designer_config.get("accent_color", "#4fc3f7")
            self.pgd_accent_btn = QPushButton()
            _set_color_btn(self.pgd_accent_btn, self.pgd_accent_color)
            self.pgd_accent_btn.clicked.connect(lambda: _pick_color(self, "pgd_accent_color", self.pgd_accent_btn))
            layout.addRow("Accent Color:", self.pgd_accent_btn)

            # Loading text
            self.pgd_loading_text_edit = QLineEdit(designer_config.get("loading_text", "Loading, please wait ..."))
            layout.addRow("Loading Text:", self.pgd_loading_text_edit)

            # Font family
            self.pgd_font_combo = QComboBox()
            self.pgd_font_combo.setEditable(True)
            fonts = [
                "Arial, Helvetica, sans-serif",
                "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
                "'Courier New', Courier, monospace",
                "Georgia, 'Times New Roman', Times, serif",
                "'Trebuchet MS', sans-serif",
                "Verdana, Geneva, sans-serif",
            ]
            self.pgd_font_combo.addItems(fonts)
            current_font = designer_config.get("font_family", fonts[0])
            idx = self.pgd_font_combo.findText(current_font)
            if idx >= 0:
                self.pgd_font_combo.setCurrentIndex(idx)
            else:
                self.pgd_font_combo.setCurrentText(current_font)
            layout.addRow("Font Family:", self.pgd_font_combo)

            # Show progress bar
            self.pgd_progress_chk = QCheckBox("Show loading progress bar")
            self.pgd_progress_chk.setChecked(designer_config.get("show_progress_bar", True))
            layout.addRow(self.pgd_progress_chk)

            # Logo image URL / path
            logo_row = QHBoxLayout()
            self.pgd_logo_edit = QLineEdit(designer_config.get("logo_url", ""))
            self.pgd_logo_edit.setPlaceholderText("URL or filename (copied into build)")
            self.pgd_logo_browse_btn = QPushButton("Browse...")
            self.pgd_logo_browse_btn.clicked.connect(lambda: _browse_logo(self))
            logo_row.addWidget(self.pgd_logo_edit, 1)
            logo_row.addWidget(self.pgd_logo_browse_btn)
            layout.addRow("Logo Image:", logo_row)

            # Background image URL / path
            bgimg_row = QHBoxLayout()
            self.pgd_bgimg_edit = QLineEdit(designer_config.get("background_image_url", ""))
            self.pgd_bgimg_edit.setPlaceholderText("URL or filename (optional)")
            self.pgd_bgimg_browse_btn = QPushButton("Browse...")
            self.pgd_bgimg_browse_btn.clicked.connect(lambda: _browse_bgimg(self))
            bgimg_row.addWidget(self.pgd_bgimg_edit, 1)
            bgimg_row.addWidget(self.pgd_bgimg_browse_btn)
            layout.addRow("Background Image:", bgimg_row)

            # Layout preset
            self.pgd_layout_combo = QComboBox()
            self.pgd_layout_combo.addItems(["centered", "top-left", "bottom-center"])
            self.pgd_layout_combo.setCurrentText(designer_config.get("layout", "centered"))
            layout.addRow("Layout:", self.pgd_layout_combo)

            # Preview hint
            hint = QLabel("These settings customize the pygbag web loading screen template.\n"
                          "All web plugins (Game Distribution, etc.) can also add their own\n"
                          "scripts and styles — they are merged automatically.")
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #888; font-size: 11px;")
            layout.addRow(hint)

            self.plugins_layout.addWidget(group)

        def new_save_config(self):
            if hasattr(self, "pgd_bg_color"):
                self.config_data["pygbag_designer"] = {
                    "background_color": self.pgd_bg_color,
                    "text_color": self.pgd_text_color,
                    "accent_color": self.pgd_accent_color,
                    "loading_text": self.pgd_loading_text_edit.text().strip() or "Loading, please wait ...",
                    "font_family": self.pgd_font_combo.currentText().strip() or "Arial, Helvetica, sans-serif",
                    "show_progress_bar": self.pgd_progress_chk.isChecked(),
                    "logo_url": self.pgd_logo_edit.text().strip(),
                    "background_image_url": self.pgd_bgimg_edit.text().strip(),
                    "layout": self.pgd_layout_combo.currentText(),
                }
            original_save_config(self)

        ProjectSettingsDialog.setup_ui = new_setup_ui
        ProjectSettingsDialog.save_config = new_save_config

        global _ui_hooked
        _ui_hooked = True
    except Exception as e:
        if _manager:
            _manager._logger.error("Pygbag Designer: Failed to inject UI", error=str(e))


# ── Helper functions ─────────────────────────────────────────────────

def _set_color_btn(btn, hex_color):
    btn.setStyleSheet(
        f"background-color: {hex_color}; border: 1px solid #555; "
        f"min-width: 60px; min-height: 22px;"
    )
    btn.setText(hex_color)

def _pick_color(dialog, attr_name, btn):
    current = getattr(dialog, attr_name, "#222222")
    color = QColorDialog.getColor(QColor(current), dialog, "Pick Color")
    if color.isValid():
        hex_val = color.name()
        setattr(dialog, attr_name, hex_val)
        _set_color_btn(btn, hex_val)

def _browse_logo(dialog):
    start_dir = os.path.dirname(dialog.pgd_logo_edit.text().strip()) or dialog.project_path or os.path.expanduser("~")
    path, _ = QFileDialog.getOpenFileName(
        dialog, "Select Logo Image", start_dir,
        "Image Files (*.png *.jpg *.jpeg *.svg *.gif *.webp);;All Files (*)"
    )
    if path:
        dialog.pgd_logo_edit.setText(os.path.normpath(path))

def _browse_bgimg(dialog):
    start_dir = os.path.dirname(dialog.pgd_bgimg_edit.text().strip()) or dialog.project_path or os.path.expanduser("~")
    path, _ = QFileDialog.getOpenFileName(
        dialog, "Select Background Image", start_dir,
        "Image Files (*.png *.jpg *.jpeg *.svg *.gif *.webp);;All Files (*)"
    )
    if path:
        dialog.pgd_bgimg_edit.setText(os.path.normpath(path))
