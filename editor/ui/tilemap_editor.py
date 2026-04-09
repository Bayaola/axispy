from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QImage, QPainter, QColor, QPen, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
    QCheckBox,
    QGroupBox
)

from core.components import TilemapComponent, TileLayer, Tileset
from core.resources import ResourceManager
import qtawesome as qta
from editor.ui.engine_settings import theme_icon_color


class _NoScrollSpinBox(QSpinBox):
    """QSpinBox that ignores wheel events when not focused"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class TilemapComponentUI(QWidget):
    """Tilemap component UI that can be embedded in the inspector"""
    
    def __init__(self, components, parent=None):
        super().__init__(parent)
        self.components = components
        self.main_window = parent.parent() if parent else None
        
        # Get the first component for single-entity editing
        self.component = components[0] if components else None
        self._syncing = False
        
        self.setup_ui()
        self.sync_from_component()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Edit mode toggle
        header = QHBoxLayout()
        self.btn_enable = QPushButton("Edit: Off")
        self.btn_enable.setCheckable(True)
        self.btn_enable.clicked.connect(self._toggle_edit_mode)
        header.addWidget(self.btn_enable)
        header.addStretch()
        layout.addLayout(header)
        
        # Tool buttons
        tools_layout = QHBoxLayout()
        tools_layout.addWidget(QLabel("Tools:"))
        
        self.tool_buttons = {}
        tools = [
            ("paint", qta.icon("fa5s.paint-brush"), "Paint", "P"),
            ("erase", qta.icon("fa5s.eraser"), "Erase", "E"),
            ("picker", qta.icon("fa5s.eye-dropper"), "Picker", "I"),
            ("rect", qta.icon("fa5s.square"), "Rectangle", "R"),
            ("fill", qta.icon("fa5s.fill"), "Fill", "F")
        ]
        
        for tool_name, icon, tooltip, shortcut in tools:
            btn = QPushButton()
            btn.setIcon(icon)
            btn.setCheckable(True)
            btn.setToolTip(f"{tooltip} ({shortcut})")
            btn.setMaximumSize(40, 30)
            btn.setMinimumSize(35, 25)
            btn.setShortcut(QKeySequence(shortcut))
            # Style for better visual feedback
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 2px;
                    background-color: #444;
                }
                QPushButton:hover {
                    background-color: #555;
                    border-color: #666;
                }
                QPushButton:checked {
                    background-color: #0078d4;
                    border-color: #0078d4;
                }
                QPushButton:disabled {
                    background-color: #333;
                    border-color: #444;
                    color: #666;
                }
            """)
            btn.clicked.connect(lambda checked, t=tool_name: self._set_tool(t))
            self.tool_buttons[tool_name] = btn
            tools_layout.addWidget(btn)
        
        # Set paint as default active tool
        self.tool_buttons["paint"].setChecked(True)
        self.current_tool = "paint"
        
        tools_layout.addStretch()
        layout.addLayout(tools_layout)
        
        # Tileset settings
        tileset_group = QGroupBox("Tileset")
        tileset_layout = QVBoxLayout(tileset_group)
        
        tileset_row = QHBoxLayout()
        self.tileset_path = QLineEdit()
        self.tileset_path.setPlaceholderText("Tileset image path")
        tileset_row.addWidget(self.tileset_path, 1)
        self.btn_browse_tileset = QPushButton("Browse")
        self.btn_browse_tileset.clicked.connect(self._browse_tileset)
        tileset_row.addWidget(self.btn_browse_tileset)
        tileset_layout.addLayout(tileset_row)
        
        settings = QHBoxLayout()
        self.spin_tw = _NoScrollSpinBox()
        self.spin_tw.setRange(1, 2048)
        self.spin_tw.setValue(32)
        self.spin_th = _NoScrollSpinBox()
        self.spin_th.setRange(1, 2048)
        self.spin_th.setValue(32)
        self.spin_spacing = _NoScrollSpinBox()
        self.spin_spacing.setRange(0, 128)
        self.spin_spacing.setValue(0)
        self.spin_margin = _NoScrollSpinBox()
        self.spin_margin.setRange(0, 128)
        self.spin_margin.setValue(0)
        
        for spin in (self.spin_tw, self.spin_th, self.spin_spacing, self.spin_margin):
            spin.valueChanged.connect(self._apply_tileset_settings_to_component)
        
        settings.addWidget(QLabel("W"))
        settings.addWidget(self.spin_tw)
        settings.addWidget(QLabel("H"))
        settings.addWidget(self.spin_th)
        settings.addWidget(QLabel("Sp"))
        settings.addWidget(self.spin_spacing)
        settings.addWidget(QLabel("Mg"))
        settings.addWidget(self.spin_margin)
        tileset_layout.addLayout(settings)
        
        # Tileset preview
        self.preview = TilesetPreview()
        self.preview.tile_selected.connect(self._on_tile_selected)
        tileset_layout.addWidget(self.preview, 1)
        
        layout.addWidget(tileset_group)
        
        # Layers
        layers_group = QGroupBox("Layers")
        layers_layout = QVBoxLayout(layers_group)
        
        layers_header = QHBoxLayout()
        self.btn_add_layer = QPushButton()
        self.btn_add_layer.setIcon(qta.icon("fa5s.plus", color=theme_icon_color()))
        self.btn_add_layer.clicked.connect(self._add_layer)
        self.btn_remove_layer = QPushButton()
        self.btn_remove_layer.setIcon(qta.icon("fa5s.minus", color=theme_icon_color()))
        self.btn_remove_layer.clicked.connect(self._remove_layer)
        layers_header.addWidget(QLabel("Layers"))
        layers_header.addWidget(self.btn_add_layer)
        layers_header.addWidget(self.btn_remove_layer)
        layers_header.addStretch(1)
        layers_layout.addLayout(layers_header)
        
        self.layers_list = QListWidget()
        self.layers_list.setMaximumHeight(150)
        layers_layout.addWidget(self.layers_list)
        self._layer_items = []
        
        layout.addWidget(layers_group)
        
        # Connect signals if we have a main window
        if self.main_window:
            self.edit_mode_changed.connect(self.main_window.viewport.set_tilemap_edit_mode)
            self.tool_changed.connect(self.main_window.viewport.set_tilemap_tool)
            self.active_layer_index_changed.connect(self.main_window.viewport.set_tilemap_active_layer)
            self.selected_tile_changed.connect(self.main_window.viewport.set_tilemap_selected_tile)
            # Set the tilemap entity for direct editing
            if self.component and hasattr(self.component, 'entity'):
                self.main_window.viewport.set_tilemap_entity(self.component.entity)
    
    # Signals
    edit_mode_changed = pyqtSignal(bool)
    active_layer_index_changed = pyqtSignal(int)
    tool_changed = pyqtSignal(str)
    selected_tile_changed = pyqtSignal(int)
    
    def sync_from_component(self):
        """Sync UI from the tilemap component"""
        if not self.component:
            return
        
        tilemap = self.component
        ts = tilemap.tileset or Tileset()
        
        # Set syncing flag to prevent apply during value changes
        self._syncing = True
        
        self.tileset_path.setText(str(ts.image_path or ""))
        self.spin_tw.setValue(int(getattr(tilemap, 'cell_width', ts.tile_width)))
        self.spin_th.setValue(int(getattr(tilemap, 'cell_height', ts.tile_height)))
        self.spin_spacing.setValue(int(ts.spacing))
        self.spin_margin.setValue(int(ts.margin))
        self._load_preview_image(ts)
        
        # Update layers
        self.layers_list.clear()
        self._layer_items.clear()
        
        for i, layer in enumerate(tilemap.layers or []):
            is_first = (i == 0)
            is_last = (i == len(tilemap.layers) - 1)
            item_widget = LayerListItem(layer.name, i, getattr(layer, 'visible', True), is_first, is_last)
            item_widget.visibility_changed.connect(self._on_layer_visibility_changed)
            item_widget.move_layer.connect(self._on_layer_move)
            item_widget.rename_layer.connect(self._on_layer_rename)
            
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.layers_list.addItem(list_item)
            self.layers_list.setItemWidget(list_item, item_widget)
            self._layer_items.append(item_widget)
        
        if self.layers_list.count() > 0:
            self.layers_list.setCurrentRow(0)
        
        # Clear syncing flag
        self._syncing = False
    
    def active_layer_index(self) -> int:
        idx = self.layers_list.currentRow()
        return int(idx) if idx >= 0 else 0
    
    def selected_tile_id(self) -> int:
        return self.preview.selected_tile_id()
    
    def current_tool(self) -> str:
        return self.current_tool
    
    def is_edit_mode(self) -> bool:
        return bool(self.btn_enable.isChecked())
    
    def _set_tool(self, tool_name: str):
        """Set the active tool, ensuring only one button is checked at a time"""
        for btn in self.tool_buttons.values():
            btn.setChecked(False)
        
        if tool_name in self.tool_buttons:
            self.tool_buttons[tool_name].setChecked(True)
            self.current_tool = tool_name
            self.tool_changed.emit(tool_name)
    
    def _toggle_edit_mode(self, checked: bool):
        self.btn_enable.setText("Edit: On" if checked else "Edit: Off")
        self.edit_mode_changed.emit(bool(checked))
        
        # When enabling edit mode, ensure a tool is selected
        if checked and not any(btn.isChecked() for btn in self.tool_buttons.values()):
            self._set_tool("paint")
    
    def _apply_tileset_settings_to_component(self):
        if self._syncing:
            return
            
        if not self.component:
            return
        
        tilemap = self.component
        tilemap.tileset.image_path = str(self.tileset_path.text()).strip()
        tilemap.tileset.tile_width = int(self.spin_tw.value())
        tilemap.tileset.tile_height = int(self.spin_th.value())
        tilemap.tileset.spacing = int(self.spin_spacing.value())
        tilemap.tileset.margin = int(self.spin_margin.value())
        tilemap.cell_width = int(self.spin_tw.value())
        tilemap.cell_height = int(self.spin_th.value())
        
        self._load_preview_image(tilemap.tileset)
    
    def _browse_tileset(self):
        if not self.main_window:
            return
        start_dir = self.main_window.project_path or os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Tileset Image", start_dir, "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not file_path:
            return
        if self.main_window.project_path:
            try:
                rel = os.path.relpath(file_path, self.main_window.project_path)
                if not rel.startswith(".."):
                    file_path = ResourceManager.portable_path(rel)
            except Exception:
                pass
        self.tileset_path.setText(file_path)
        self._apply_tileset_settings_to_component()
    
    def _load_preview_image(self, tileset: Tileset):
        if not tileset or not tileset.image_path:
            self.preview.set_tileset(None, None)
            return
        abs_path = ResourceManager.to_os_path(tileset.image_path)
        if self.main_window and self.main_window.project_path and not os.path.isabs(abs_path):
            abs_path = os.path.normpath(os.path.join(self.main_window.project_path, abs_path))
        if not os.path.exists(abs_path):
            self.preview.set_tileset(None, None)
            return
        image = QImage(abs_path)
        if image.isNull():
            self.preview.set_tileset(None, None)
            return
        self.preview.set_tileset(image, tileset)
    
    def _on_tile_selected(self, tile_id: int):
        self.selected_tile_changed.emit(int(tile_id))
    
    def _on_layer_visibility_changed(self, layer_index: int, visible: bool):
        if not self.component:
            return
        tilemap = self.component
        if not tilemap or layer_index >= len(tilemap.layers):
            return
        
        tilemap.layers[layer_index].visible = visible
        
        # Trigger viewport update
        if self.main_window and hasattr(self.main_window, 'viewport'):
            self.main_window.viewport.update()
    
    def _on_layer_move(self, from_index: int, to_index: int):
        if not self.component:
            return
        tilemap = self.component
        if not tilemap or not tilemap.layers:
            return
        
        # Validate indices
        if from_index < 0 or from_index >= len(tilemap.layers):
            return
        if to_index < 0 or to_index >= len(tilemap.layers):
            return
        
        # Move the layer
        layer = tilemap.layers.pop(from_index)
        tilemap.layers.insert(to_index, layer)
        
        # Resync to update the UI
        self.sync_from_component()
        
        # Select the moved layer at its new position
        self.layers_list.setCurrentRow(to_index)
        self.active_layer_index_changed.emit(to_index)
        
        # Trigger viewport update
        if self.main_window and hasattr(self.main_window, 'viewport'):
            self.main_window.viewport.update()

    def _on_layer_rename(self, layer_index: int, new_name: str):
        """Handle layer renaming"""
        if not self.component:
            return
        tilemap = self.component
        if not tilemap or layer_index >= len(tilemap.layers):
            return
        
        # Update layer name
        tilemap.layers[layer_index].name = new_name
        
        # No need to resync the entire UI, just update the label
        if layer_index < len(self._layer_items):
            self._layer_items[layer_index].set_name(new_name)

    def _add_layer(self):
        if not self.component:
            return
        tilemap = self.component
        if not tilemap:
            return
        name = f"Layer{len(tilemap.layers) + 1}"
        layer = TileLayer(
            name=name, 
            width=tilemap.map_width, 
            height=tilemap.map_height, 
            tiles=[0] * (tilemap.map_width * tilemap.map_height),
            offset_x=0,
            offset_y=0
        )
        tilemap.layers.append(layer)
        self.sync_from_component()
        self.layers_list.setCurrentRow(len(tilemap.layers) - 1)
        self.active_layer_index_changed.emit(len(tilemap.layers) - 1)
    
    def _remove_layer(self):
        if not self.component:
            return
        tilemap = self.component
        if not tilemap or not tilemap.layers:
            return
        if len(tilemap.layers) <= 1:
            QMessageBox.information(self, "Tilemap", "A tilemap must have at least one layer.")
            return
        idx = self.layers_list.currentRow()
        if idx < 0:
            idx = len(tilemap.layers) - 1
        idx = max(0, min(idx, len(tilemap.layers) - 1))
        tilemap.layers.pop(idx)
        self.sync_from_component()
        if idx >= len(tilemap.layers):
            idx = len(tilemap.layers) - 1
        self.layers_list.setCurrentRow(idx)
        self.active_layer_index_changed.emit(idx)


class LayerListItem(QWidget):
    """Custom list widget item for layers with visibility checkbox and reordering buttons"""
    visibility_changed = pyqtSignal(int, bool)  # layer_index, visible
    move_layer = pyqtSignal(int, int)  # from_index, to_index
    rename_layer = pyqtSignal(int, str)  # layer_index, new_name
    
    def __init__(self, layer_name: str, layer_index: int, is_visible: bool = True, is_first: bool = False, is_last: bool = False, parent=None):
        super().__init__(parent)
        self.layer_index = layer_index
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 2, 4, 2)
        
        # Visibility checkbox
        self.visibility_checkbox = QCheckBox()
        self.visibility_checkbox.setChecked(is_visible)
        self.visibility_checkbox.stateChanged.connect(self._on_visibility_changed)
        self.layout.addWidget(self.visibility_checkbox)
        
        # Layer name (make it editable)
        self.name_label = QLabel(layer_name)
        self.name_label.setMinimumWidth(60)
        self.name_label.setStyleSheet("QLabel { border: 1px solid transparent; padding: 2px; }")
        self.name_label.mouseDoubleClickEvent = self._on_name_double_click
        self.layout.addWidget(self.name_label)
        
        # Reordering buttons
        self.btn_move_up = QPushButton("↑")
        self.btn_move_up.setMaximumSize(20, 20)
        self.btn_move_up.setEnabled(not is_first)
        self.btn_move_up.clicked.connect(self._move_up)
        self.layout.addWidget(self.btn_move_up)
        
        self.btn_move_down = QPushButton("↓")
        self.btn_move_down.setMaximumSize(20, 20)
        self.btn_move_down.setEnabled(not is_last)
        self.btn_move_down.clicked.connect(self._move_down)
        self.layout.addWidget(self.btn_move_down)
        
        # Set minimum height for better usability
        self.setMinimumHeight(24)
    
    def _on_name_double_click(self, event):
        """Start editing the layer name on double click"""
        from PyQt6.QtWidgets import QLineEdit
        
        # Create line edit for renaming
        self.name_edit = QLineEdit(self.name_label.text())
        self.name_edit.setFrame(False)
        self.name_edit.selectAll()
        
        # Replace label with line edit
        index = self.layout.indexOf(self.name_label)
        self.layout.insertWidget(index, self.name_edit)
        self.layout.removeWidget(self.name_label)
        self.name_label.hide()
        
        # Focus and select all text
        self.name_edit.setFocus()
        
        # Handle finishing edit
        def finish_edit():
            new_name = self.name_edit.text().strip()
            if new_name and new_name != self.name_label.text():
                self.rename_layer.emit(self.layer_index, new_name)
                self.name_label.setText(new_name)
            
            # Replace line edit with label
            self.layout.insertWidget(index, self.name_label)
            self.layout.removeWidget(self.name_edit)
            self.name_edit.deleteLater()
            self.name_label.show()
        
        # Connect signals
        self.name_edit.editingFinished.connect(finish_edit)
        self.name_edit.returnPressed.connect(finish_edit)
    
    def _on_visibility_changed(self, state):
        is_visible = state == Qt.CheckState.Checked.value
        self.visibility_changed.emit(self.layer_index, is_visible)
    
    def _move_up(self):
        self.move_layer.emit(self.layer_index, self.layer_index - 1)
    
    def _move_down(self):
        self.move_layer.emit(self.layer_index, self.layer_index + 1)
    
    def set_visible(self, visible: bool):
        self.visibility_checkbox.setChecked(visible)
    
    def is_visible(self) -> bool:
        return self.visibility_checkbox.isChecked()
    
    def set_name(self, name: str):
        self.name_label.setText(name)
    
    def update_position(self, is_first: bool, is_last: bool):
        """Update button states based on position"""
        self.btn_move_up.setEnabled(not is_first)
        self.btn_move_down.setEnabled(not is_last)


class TilesetPreview(QLabel):
    tile_selected = pyqtSignal(int)  # tile_id (1..N), 0 = none

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("No tileset selected")
        self._image = None  # QImage
        self._tileset: Tileset | None = None
        self._selected_tile_id = 0

    def set_tileset(self, image: QImage | None, tileset: Tileset | None):
        self._image = image
        self._tileset = tileset
        self._selected_tile_id = 0
        self.update()

    def selected_tile_id(self) -> int:
        return int(self._selected_tile_id)

    def mousePressEvent(self, event):
        if not self._image or not self._tileset:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Map click to image coordinates in current draw rect.
        draw_rect = self._compute_draw_rect()
        if draw_rect is None:
            return
        x = int(event.position().x() - draw_rect.x())
        y = int(event.position().y() - draw_rect.y())
        if x < 0 or y < 0 or x >= draw_rect.width() or y >= draw_rect.height():
            return

        img_x = int((x / max(1, draw_rect.width())) * self._image.width())
        img_y = int((y / max(1, draw_rect.height())) * self._image.height())

        tw = max(1, int(self._tileset.tile_width))
        th = max(1, int(self._tileset.tile_height))
        spacing = max(0, int(self._tileset.spacing))
        margin = max(0, int(self._tileset.margin))

        if img_x < margin or img_y < margin:
            return
        rel_x = img_x - margin
        rel_y = img_y - margin
        step_x = tw + spacing
        step_y = th + spacing
        tx = rel_x // step_x
        ty = rel_y // step_y
        in_tile_x = rel_x % step_x
        in_tile_y = rel_y % step_y
        if in_tile_x >= tw or in_tile_y >= th:
            return

        tiles_per_row = max(1, (self._image.width() - margin) // step_x)
        tile_id = int(ty * tiles_per_row + tx + 1)
        self._selected_tile_id = tile_id
        self.tile_selected.emit(tile_id)
        self.update()

    def _compute_draw_rect(self):
        if not self._image:
            return None
        widget_w = max(1, self.width())
        widget_h = max(1, self.height())
        img_w = max(1, self._image.width())
        img_h = max(1, self._image.height())
        scale = min(widget_w / img_w, widget_h / img_h)
        draw_w = max(1, int(img_w * scale))
        draw_h = max(1, int(img_h * scale))
        x = (widget_w - draw_w) // 2
        y = (widget_h - draw_h) // 2
        return self.rect().adjusted(x, y, x - widget_w + draw_w, y - widget_h + draw_h)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._image or not self._tileset:
            return
        painter = QPainter(self)
        draw_rect = self._compute_draw_rect()
        if draw_rect is None:
            return
        painter.drawImage(draw_rect, self._image)

        # Overlay grid + selection
        tw = max(1, int(self._tileset.tile_width))
        th = max(1, int(self._tileset.tile_height))
        spacing = max(0, int(self._tileset.spacing))
        margin = max(0, int(self._tileset.margin))

        sx = draw_rect.width() / max(1, self._image.width())
        sy = draw_rect.height() / max(1, self._image.height())

        pen = QPen(QColor(255, 255, 255, 90))
        pen.setWidth(1)
        painter.setPen(pen)

        x0 = draw_rect.x() + int(margin * sx)
        y0 = draw_rect.y() + int(margin * sy)
        step_x = (tw + spacing) * sx
        step_y = (th + spacing) * sy

        cols = int((self._image.width() - margin) // (tw + spacing))
        rows = int((self._image.height() - margin) // (th + spacing))
        for cx in range(cols + 1):
            x = int(x0 + (cx * step_x))
            painter.drawLine(x, y0, x, int(y0 + rows * step_y))
        for cy in range(rows + 1):
            y = int(y0 + (cy * step_y))
            painter.drawLine(x0, y, int(x0 + cols * step_x), y)

        if self._selected_tile_id > 0:
            tiles_per_row = max(1, cols)
            idx = self._selected_tile_id - 1
            tx = idx % tiles_per_row
            ty = idx // tiles_per_row
            sel_x = int(x0 + tx * step_x)
            sel_y = int(y0 + ty * step_y)
            sel_w = int(tw * sx)
            sel_h = int(th * sy)
            painter.setPen(QPen(QColor(255, 210, 80, 220), 2))
            painter.drawRect(sel_x, sel_y, sel_w, sel_h)


class TilemapEditorDock(QDockWidget):
    edit_mode_changed = pyqtSignal(bool)
    active_layer_index_changed = pyqtSignal(int)
    tool_changed = pyqtSignal(str)
    selected_tile_changed = pyqtSignal(int)
    tilemap_selected = pyqtSignal(object)  # entity or None

    def __init__(self, main_window, parent=None):
        super().__init__("Tilemap", parent)
        self.main_window = main_window
        self._active_entity = None
        self._syncing = False  # Flag to prevent apply during sync

        self.widget = QWidget()
        self.setWidget(self.widget)
        layout = QVBoxLayout(self.widget)

        header = QHBoxLayout()
        self.btn_enable = QPushButton("Edit: Off")
        self.btn_enable.setCheckable(True)
        self.btn_enable.clicked.connect(self._toggle_edit_mode)
        header.addWidget(self.btn_enable)

        # Tool buttons group
        header.addWidget(QLabel("Tool:"))
        
        # Create tool buttons
        self.tool_buttons = {}
        tools = [
            ("paint", qta.icon("fa5s.paint-brush"), "Paint", "P"),
            ("erase", qta.icon("fa5s.eraser"), "Erase", "E"),
            ("picker", qta.icon("fa5s.eye-dropper"), "Picker", "I"),
            ("rect", qta.icon("fa5s.square"), "Rectangle", "R"),
            ("fill", qta.icon("fa5s.fill"), "Fill", "F")
        ]
        
        for tool_name, icon, tooltip, shortcut in tools:
            btn = QPushButton()
            btn.setIcon(icon)
            btn.setCheckable(True)
            btn.setToolTip(f"{tooltip} ({shortcut})")
            btn.setMaximumSize(40, 30)
            btn.setMinimumSize(35, 25)
            btn.setShortcut(QKeySequence(shortcut))
            # Style for better visual feedback
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 2px;
                    background-color: #444;
                }
                QPushButton:hover {
                    background-color: #555;
                    border-color: #666;
                }
                QPushButton:checked {
                    background-color: #0078d4;
                    border-color: #0078d4;
                }
                QPushButton:disabled {
                    background-color: #333;
                    border-color: #444;
                    color: #666;
                }
            """)
            btn.clicked.connect(lambda checked, t=tool_name: self._set_tool(t))
            self.tool_buttons[tool_name] = btn
            header.addWidget(btn)
        
        # Set paint as default active tool
        self.tool_buttons["paint"].setChecked(True)
        self.current_tool = "paint"
        
        header.addStretch()
        layout.addLayout(header)

        tileset_row = QHBoxLayout()
        self.tileset_path = QLineEdit()
        self.tileset_path.setPlaceholderText("Tileset image path (spritesheet)")
        tileset_row.addWidget(self.tileset_path, 1)
        self.btn_browse_tileset = QPushButton("Browse")
        self.btn_browse_tileset.clicked.connect(self._browse_tileset)
        tileset_row.addWidget(self.btn_browse_tileset)
        layout.addLayout(tileset_row)

        settings = QHBoxLayout()
        self.spin_tw = _NoScrollSpinBox()
        self.spin_tw.setRange(1, 2048)
        self.spin_tw.setValue(32)
        self.spin_th = _NoScrollSpinBox()
        self.spin_th.setRange(1, 2048)
        self.spin_th.setValue(32)
        self.spin_spacing = _NoScrollSpinBox()
        self.spin_spacing.setRange(0, 128)
        self.spin_spacing.setValue(0)
        self.spin_margin = _NoScrollSpinBox()
        self.spin_margin.setRange(0, 128)
        self.spin_margin.setValue(0)
        for spin in (self.spin_tw, self.spin_th, self.spin_spacing, self.spin_margin):
            spin.valueChanged.connect(self._apply_tileset_settings_to_entity)

        settings.addWidget(QLabel("W"))
        settings.addWidget(self.spin_tw)
        settings.addWidget(QLabel("H"))
        settings.addWidget(self.spin_th)
        settings.addWidget(QLabel("Sp"))
        settings.addWidget(self.spin_spacing)
        settings.addWidget(QLabel("Mg"))
        settings.addWidget(self.spin_margin)
        layout.addLayout(settings)

        self.preview = TilesetPreview()
        self.preview.tile_selected.connect(self._on_tile_selected)
        layout.addWidget(self.preview, 1)

        layers_header = QHBoxLayout()
        layers_header.addWidget(QLabel("Layers"))
        self.btn_add_layer = QPushButton()
        self.btn_add_layer.setIcon(qta.icon("fa5s.plus", color=theme_icon_color()))
        self.btn_add_layer.clicked.connect(self._add_layer)
        self.btn_remove_layer = QPushButton()
        self.btn_remove_layer.setIcon(qta.icon("fa5s.minus", color=theme_icon_color()))
        self.btn_remove_layer.clicked.connect(self._remove_layer)
        layers_header.addWidget(self.btn_add_layer)
        layers_header.addWidget(self.btn_remove_layer)
        layers_header.addStretch(1)
        layout.addLayout(layers_header)

        self.layers_list = QListWidget()
        self.layers_list.currentRowChanged.connect(self.active_layer_index_changed.emit)
        layout.addWidget(self.layers_list)
        
        # Store layer items for visibility management
        self._layer_items = []

        self._refresh_enabled_state()

    def set_active_tilemap_entity(self, entity):
        self._active_entity = entity
        self.tilemap_selected.emit(entity)
        self._sync_from_entity()
        self._refresh_enabled_state()

    def active_layer_index(self) -> int:
        idx = self.layers_list.currentRow()
        return int(idx) if idx >= 0 else 0

    def selected_tile_id(self) -> int:
        return self.preview.selected_tile_id()

    def current_tool(self) -> str:
        return self.current_tool
    
    def _set_tool(self, tool_name: str):
        """Set the active tool, ensuring only one button is checked at a time"""
        # Uncheck all buttons
        for btn in self.tool_buttons.values():
            btn.setChecked(False)
        
        # Check the selected button
        if tool_name in self.tool_buttons:
            self.tool_buttons[tool_name].setChecked(True)
            self.current_tool = tool_name
            self.tool_changed.emit(tool_name)
    
    def _toggle_edit_mode(self, checked: bool):
        self.btn_enable.setText("Edit: On" if checked else "Edit: Off")
        self.edit_mode_changed.emit(bool(checked))
        self._refresh_enabled_state()
        
        # When enabling edit mode, ensure a tool is selected
        if checked and not any(btn.isChecked() for btn in self.tool_buttons.values()):
            self._set_tool("paint")

    def is_edit_mode(self) -> bool:
        return bool(self.btn_enable.isChecked())

    def _refresh_enabled_state(self):
        has_entity = self._active_entity is not None
        # Enable/disable tool buttons
        for btn in self.tool_buttons.values():
            btn.setEnabled(has_entity)
        self.tileset_path.setEnabled(has_entity)
        self.btn_browse_tileset.setEnabled(has_entity)
        for spin in (self.spin_tw, self.spin_th, self.spin_spacing, self.spin_margin):
            spin.setEnabled(has_entity)
        self.preview.setEnabled(has_entity)
        self.layers_list.setEnabled(has_entity)
        self.btn_add_layer.setEnabled(has_entity)
        self.btn_remove_layer.setEnabled(has_entity)

    def _browse_tileset(self):
        if not self.main_window:
            return
        start_dir = self.main_window.project_path or os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Tileset Image", start_dir, "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not file_path:
            return
        if self.main_window.project_path:
            try:
                rel = os.path.relpath(file_path, self.main_window.project_path)
                if not rel.startswith(".."):
                    file_path = ResourceManager.portable_path(rel)
            except Exception:
                pass
        self.tileset_path.setText(file_path)
        self._apply_tileset_settings_to_entity()

    def _apply_tileset_settings_to_entity(self):
        # Don't apply if we're syncing from entity
        if self._syncing:
            return
            
        entity = self._active_entity
        if not entity:
            return
        tilemap = entity.get_component(TilemapComponent)
        if not tilemap:
            return
        tilemap.tileset.image_path = str(self.tileset_path.text()).strip()
        tilemap.tileset.tile_width = int(self.spin_tw.value())
        tilemap.tileset.tile_height = int(self.spin_th.value())
        tilemap.tileset.spacing = int(self.spin_spacing.value())
        tilemap.tileset.margin = int(self.spin_margin.value())
        # Use the spinbox values for cell dimensions, not the tileset values
        tilemap.cell_width = int(self.spin_tw.value())
        tilemap.cell_height = int(self.spin_th.value())

        self._load_preview_image(tilemap.tileset)

    def _load_preview_image(self, tileset: Tileset):
        if not tileset or not tileset.image_path:
            self.preview.set_tileset(None, None)
            return
        abs_path = tileset.image_path
        if self.main_window and self.main_window.project_path and not os.path.isabs(abs_path):
            abs_path = os.path.normpath(os.path.join(self.main_window.project_path, abs_path))
        if not os.path.exists(abs_path):
            self.preview.set_tileset(None, None)
            return
        image = QImage(abs_path)
        if image.isNull():
            self.preview.set_tileset(None, None)
            return
        self.preview.set_tileset(image, tileset)

    def _on_tile_selected(self, tile_id: int):
        self.selected_tile_changed.emit(int(tile_id))

    def _sync_from_entity(self):
        entity = self._active_entity
        if not entity:
            self.layers_list.clear()
            self.preview.set_tileset(None, None)
            return
        tilemap = entity.get_component(TilemapComponent)
        if not tilemap:
            self.layers_list.clear()
            self.preview.set_tileset(None, None)
            return
        ts = tilemap.tileset or Tileset()
        
        # Set syncing flag to prevent apply during value changes
        self._syncing = True
        
        self.tileset_path.setText(str(ts.image_path or ""))
        self.spin_tw.setValue(int(getattr(tilemap, 'cell_width', ts.tile_width)))
        self.spin_th.setValue(int(getattr(tilemap, 'cell_height', ts.tile_height)))
        self.spin_spacing.setValue(int(ts.spacing))
        self.spin_margin.setValue(int(ts.margin))
        self._load_preview_image(ts)

        self.layers_list.clear()
        self._layer_items.clear()
        
        for i, layer in enumerate(tilemap.layers or []):
            # Create custom list item widget with position info
            is_first = (i == 0)
            is_last = (i == len(tilemap.layers) - 1)
            item_widget = LayerListItem(layer.name, i, getattr(layer, 'visible', True), is_first, is_last)
            item_widget.visibility_changed.connect(self._on_layer_visibility_changed)
            item_widget.move_layer.connect(self._on_layer_move)
            item_widget.rename_layer.connect(self._on_layer_rename)
            
            # Create list item and set widget
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.layers_list.addItem(list_item)
            self.layers_list.setItemWidget(list_item, item_widget)
            self._layer_items.append(item_widget)
            
        if self.layers_list.count() > 0:
            self.layers_list.setCurrentRow(0)
        
        # Clear syncing flag
        self._syncing = False

    def _on_layer_visibility_changed(self, layer_index: int, visible: bool):
        """Handle visibility change for a layer"""
        entity = self._active_entity
        if not entity:
            return
        tilemap = entity.get_component(TilemapComponent)
        if not tilemap or layer_index >= len(tilemap.layers):
            return
        
        # Update layer visibility
        tilemap.layers[layer_index].visible = visible
        
        # Trigger viewport update through main window
        if self.main_window and hasattr(self.main_window, 'viewport'):
            self.main_window.viewport.update()

    def _on_layer_move(self, from_index: int, to_index: int):
        """Handle layer reordering"""
        entity = self._active_entity
        if not entity:
            return
        tilemap = entity.get_component(TilemapComponent)
        if not tilemap or not tilemap.layers:
            return
        
        # Validate indices
        if from_index < 0 or from_index >= len(tilemap.layers):
            return
        if to_index < 0 or to_index >= len(tilemap.layers):
            return
        
        # Move the layer
        layer = tilemap.layers.pop(from_index)
        tilemap.layers.insert(to_index, layer)
        
        # Resync to update the UI
        self._sync_from_entity()
        
        # Select the moved layer at its new position
        self.layers_list.setCurrentRow(to_index)
        self.active_layer_index_changed.emit(to_index)
        
        # Trigger viewport update
        if self.main_window and hasattr(self.main_window, 'viewport'):
            self.main_window.viewport.update()

    def _on_layer_rename(self, layer_index: int, new_name: str):
        """Handle layer renaming"""
        if not self.component:
            return
        tilemap = self.component
        if not tilemap or layer_index >= len(tilemap.layers):
            return
        
        # Update layer name
        tilemap.layers[layer_index].name = new_name
        
        # No need to resync the entire UI, just update the label
        if layer_index < len(self._layer_items):
            self._layer_items[layer_index].set_name(new_name)

    def _add_layer(self):
        entity = self._active_entity
        if not entity:
            return
        tilemap = entity.get_component(TilemapComponent)
        if not tilemap:
            return
        name = f"Layer{len(tilemap.layers) + 1}"
        # Initialize with offset fields for infinite expansion
        layer = TileLayer(
            name=name, 
            width=tilemap.map_width, 
            height=tilemap.map_height, 
            tiles=[0] * (tilemap.map_width * tilemap.map_height),
            offset_x=0,
            offset_y=0
        )
        tilemap.layers.append(layer)
        self._sync_from_entity()
        self.layers_list.setCurrentRow(len(tilemap.layers) - 1)
        
        # Select the new layer
        self.active_layer_index_changed.emit(len(tilemap.layers) - 1)

    def _remove_layer(self):
        entity = self._active_entity
        if not entity:
            return
        tilemap = entity.get_component(TilemapComponent)
        if not tilemap or not tilemap.layers:
            return
        if len(tilemap.layers) <= 1:
            QMessageBox.information(self, "Tilemap", "A tilemap must have at least one layer.")
            return
        idx = self.layers_list.currentRow()
        if idx < 0:
            idx = len(tilemap.layers) - 1
        idx = max(0, min(idx, len(tilemap.layers) - 1))
        tilemap.layers.pop(idx)
        self._sync_from_entity()

