from PyQt6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel, QFormLayout, QLineEdit, QDoubleSpinBox, QPushButton, QMenu, QFileDialog, QMessageBox, QScrollArea, QCheckBox, QHBoxLayout, QComboBox, QDialog, QDialogButtonBox, QGroupBox, QSpinBox, QListWidget, QListWidgetItem, QColorDialog, QToolButton, QInputDialog
from PyQt6.QtGui import QCursor, QPixmap, QPainter, QPen, QColor, QIcon, QFont
from PyQt6.QtCore import Qt, QDir, QSize, QRect, pyqtSignal
from core.components import Transform, CameraComponent, SpriteRenderer, Rigidbody2D, BoxCollider2D, CircleCollider2D, PolygonCollider2D, AnimatorComponent, ParticleEmitterComponent, TilemapComponent
from core.components.ui import (
    TextRenderer, ButtonComponent, TextInputComponent, SliderComponent,
    ProgressBarComponent, CheckBoxComponent, ImageRenderer,
    HBoxContainerComponent, VBoxContainerComponent, GridBoxContainerComponent
)
from core.components.script import ScriptComponent
from core.components.sound import SoundComponent
from core.components.websocket import WebSocketComponent
from core.components.http_client import HTTPClientComponent
from core.components.http_request import HTTPRequestComponent
from core.components.webview import WebviewComponent
from core.components.webrtc import WebRTCComponent
from core.components.multiplayer import MultiplayerComponent
from core.components.network_identity import NetworkIdentityComponent
from core.components.timer import TimerComponent
from core.components.steering import (
    SteeringAgentComponent,
    SeekBehavior, FleeBehavior, ArriveBehavior, WanderBehavior,
    SeparationBehavior, CohesionBehavior, AlignmentBehavior,
)
from core.components.light import PointLight2D, SpotLight2D, LightOccluder2D
from core.serializer import SceneSerializer
from core.animation import AnimationController
from editor.undo_manager import PropertyChangeCommand, EntityPropertyChangeCommand
from core.vector import Vector2
from core.resources import ResourceManager
import os
import qtawesome as qta
from editor.ui.engine_settings import theme_icon_color

class UndoableDoubleSpinBox(QDoubleSpinBox):
    focused = pyqtSignal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def focusInEvent(self, event):
        self.focused.emit()
        super().focusInEvent(event)
    
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)
    
    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clearFocus()

class UndoableLineEdit(QLineEdit):
    focused = pyqtSignal()
    
    def focusInEvent(self, event):
        self.focused.emit()
        super().focusInEvent(event)

class NoScrollSpinBox(QSpinBox):
    """QSpinBox that ignores wheel events when not focused"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)

class NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events when not focused"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)

class AnimationClipEditorDialog(QDialog):
    def __init__(self, project_dir, default_mode="spritesheet", default_clip_name="", parent=None):
        super().__init__(parent)
        self.project_dir = os.path.abspath(project_dir)
        self.image_paths = []
        self.result_data = None
        self.setWindowTitle("Animation Clip Editor")
        self.resize(700, 780)

        layout = QVBoxLayout(self)

        clip_group = QGroupBox("Clip")
        clip_form = QFormLayout(clip_group)
        self.clip_name_edit = QLineEdit(default_clip_name)
        self.source_combo = NoScrollComboBox()
        self.source_combo.addItem("Spritesheet", "spritesheet")
        self.source_combo.addItem("Image Sequence", "images")
        self.fps_spin = UndoableDoubleSpinBox()
        self.fps_spin.setRange(0.1, 240.0)
        self.fps_spin.setSingleStep(0.5)
        self.fps_spin.setValue(12.0)
        self.loop_chk = QCheckBox()
        self.loop_chk.setChecked(True)
        clip_form.addRow("Name", self.clip_name_edit)
        clip_form.addRow("Source", self.source_combo)
        clip_form.addRow("FPS", self.fps_spin)
        clip_form.addRow("Loop", self.loop_chk)
        layout.addWidget(clip_group)

        self.spritesheet_group = QGroupBox("Spritesheet")
        ss_form = QFormLayout(self.spritesheet_group)
        sheet_row = QWidget()
        sheet_row_layout = QHBoxLayout(sheet_row)
        sheet_row_layout.setContentsMargins(0, 0, 0, 0)
        self.sheet_path_edit = QLineEdit()
        browse_sheet_btn = QPushButton("Browse...")
        sheet_row_layout.addWidget(self.sheet_path_edit)
        sheet_row_layout.addWidget(browse_sheet_btn)
        self.frame_width_spin = NoScrollSpinBox()
        self.frame_width_spin.setRange(1, 8192)
        self.frame_width_spin.setValue(32)
        self.frame_height_spin = NoScrollSpinBox()
        self.frame_height_spin.setRange(1, 8192)
        self.frame_height_spin.setValue(32)
        self.start_frame_spin = NoScrollSpinBox()
        self.start_frame_spin.setRange(0, 1000000)
        self.frame_count_spin = NoScrollSpinBox()
        self.frame_count_spin.setRange(0, 1000000)
        self.margin_spin = NoScrollSpinBox()
        self.margin_spin.setRange(0, 4096)
        self.spacing_spin = NoScrollSpinBox()
        self.spacing_spin.setRange(0, 4096)
        ss_form.addRow("Image", sheet_row)
        ss_form.addRow("Frame Width", self.frame_width_spin)
        ss_form.addRow("Frame Height", self.frame_height_spin)
        ss_form.addRow("Start Frame", self.start_frame_spin)
        ss_form.addRow("Frame Count", self.frame_count_spin)
        ss_form.addRow("Margin", self.margin_spin)
        ss_form.addRow("Spacing", self.spacing_spin)
        layout.addWidget(self.spritesheet_group)

        self.images_group = QGroupBox("Image Sequence")
        images_layout = QVBoxLayout(self.images_group)
        images_btn_row = QWidget()
        images_btn_layout = QHBoxLayout(images_btn_row)
        images_btn_layout.setContentsMargins(0, 0, 0, 0)
        add_images_btn = QPushButton("Select Images...")
        clear_images_btn = QPushButton("Clear")
        images_btn_layout.addWidget(add_images_btn)
        images_btn_layout.addWidget(clear_images_btn)
        self.images_list = QListWidget()
        images_layout.addWidget(images_btn_row)
        images_layout.addWidget(self.images_list)
        layout.addWidget(self.images_group)

        save_group = QGroupBox("Animation Clip File")
        save_form = QFormLayout(save_group)
        save_row = QWidget()
        save_row_layout = QHBoxLayout(save_row)
        save_row_layout.setContentsMargins(0, 0, 0, 0)
        self.save_path_edit = QLineEdit()
        browse_save_btn = QPushButton("Save As...")
        save_row_layout.addWidget(self.save_path_edit)
        save_row_layout.addWidget(browse_save_btn)
        save_form.addRow(".anim Path", save_row)
        layout.addWidget(save_group)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("No preview")
        self.preview_label.setMinimumSize(460, 300)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid #666;")
        self.preview_info = QLabel("")
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.preview_info)
        layout.addWidget(preview_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        browse_sheet_btn.clicked.connect(self._browse_spritesheet)
        add_images_btn.clicked.connect(self._add_images)
        clear_images_btn.clicked.connect(self._clear_images)
        browse_save_btn.clicked.connect(self._browse_save_path)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.images_list.currentRowChanged.connect(self._update_preview)
        self.sheet_path_edit.textChanged.connect(self._update_preview)
        self.frame_width_spin.valueChanged.connect(self._update_preview)
        self.frame_height_spin.valueChanged.connect(self._update_preview)
        self.start_frame_spin.valueChanged.connect(self._update_preview)
        self.frame_count_spin.valueChanged.connect(self._update_preview)
        self.margin_spin.valueChanged.connect(self._update_preview)
        self.spacing_spin.valueChanged.connect(self._update_preview)

        self.source_combo.setCurrentIndex(0 if default_mode == "spritesheet" else 1)
        if default_clip_name:
            self._default_save_path(default_clip_name)
        self._on_source_changed()
        self._update_preview()

    def _default_save_path(self, clip_name):
        safe_name = "".join(ch for ch in clip_name if ch.isalnum() or ch in ("_", "-")).strip() or "animation"
        self.save_path_edit.setText(os.path.join(self.project_dir, f"{safe_name}.anim"))

    def _browse_spritesheet(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Spritesheet",
            self.project_dir,
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.sheet_path_edit.setText(self._to_project_relative(path))

    def _add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Animation Images",
            self.project_dir,
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not paths:
            return
        for path in paths:
            rel_path = self._to_project_relative(path)
            if rel_path not in self.image_paths:
                self.image_paths.append(rel_path)
        self._refresh_images_list()

    def _clear_images(self):
        self.image_paths = []
        self._refresh_images_list()

    def _refresh_images_list(self):
        self.images_list.clear()
        for path in self.image_paths:
            self.images_list.addItem(QListWidgetItem(os.path.basename(path)))
        if self.image_paths:
            self.images_list.setCurrentRow(0)
        self._update_preview()

    def _browse_save_path(self):
        clip_name = self.clip_name_edit.text().strip() or "animation"
        default_path = os.path.join(self.project_dir, f"{clip_name}.anim")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Animation Clip",
            default_path,
            "Animation Clips (*.anim)"
        )
        if not file_path:
            return
        if not file_path.endswith(".anim"):
            file_path += ".anim"
        self.save_path_edit.setText(file_path)

    def _on_source_changed(self):
        source_type = self.source_combo.currentData()
        self.spritesheet_group.setVisible(source_type == "spritesheet")
        self.images_group.setVisible(source_type == "images")
        self._update_preview()

    def _resolve_to_absolute(self, path):
        """Resolve a potentially relative path against the project directory."""
        if not path:
            return ""
        path = ResourceManager.to_os_path(path)
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(self.project_dir, path))

    def _load_pixmap(self, path):
        if not path:
            return None
        abs_path = self._resolve_to_absolute(path)
        pixmap = QPixmap(abs_path)
        if pixmap.isNull():
            return None
        return pixmap

    def _frame_rects(self, width, height, frame_width, frame_height, margin, spacing):
        rects = []
        y = margin
        while y + frame_height <= height:
            x = margin
            while x + frame_width <= width:
                rects.append((x, y, frame_width, frame_height))
                x += frame_width + spacing
            y += frame_height + spacing
        return rects

    def _update_preview(self):
        source_type = self.source_combo.currentData()
        if source_type == "spritesheet":
            pixmap = self._load_pixmap(self.sheet_path_edit.text().strip())
            if pixmap is None:
                self.preview_label.setPixmap(QPixmap())
                self.preview_label.setText("Select a spritesheet")
                self.preview_info.setText("")
                return
            frame_width = self.frame_width_spin.value()
            frame_height = self.frame_height_spin.value()
            margin = self.margin_spin.value()
            spacing = self.spacing_spin.value()
            start_frame = self.start_frame_spin.value()
            frame_count = self.frame_count_spin.value()
            rects = self._frame_rects(pixmap.width(), pixmap.height(), frame_width, frame_height, margin, spacing)
            selected = []
            if start_frame < len(rects):
                if frame_count > 0:
                    selected = rects[start_frame:start_frame + frame_count]
                else:
                    selected = rects[start_frame:]
            preview = QPixmap(pixmap)
            painter = QPainter(preview)
            painter.setPen(QPen(QColor(255, 200, 0), 1))
            for rect in rects:
                painter.drawRect(rect[0], rect[1], rect[2], rect[3])
            painter.setPen(QPen(QColor(0, 255, 140), 2))
            for rect in selected:
                painter.drawRect(rect[0], rect[1], rect[2], rect[3])
            painter.end()
            rendered = preview.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(rendered)
            self.preview_label.setText("")
            self.preview_info.setText(f"Total frames: {len(rects)} | Selected: {len(selected)}")
            return
        if not self.image_paths:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Select sequence images")
            self.preview_info.setText("")
            return
        index = self.images_list.currentRow()
        if index < 0 or index >= len(self.image_paths):
            index = 0
        pixmap = self._load_pixmap(self.image_paths[index])
        if pixmap is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Unable to preview selected image")
            self.preview_info.setText("")
            return
        rendered = pixmap.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(rendered)
        self.preview_label.setText("")
        self.preview_info.setText(f"Frame {index + 1}/{len(self.image_paths)}: {os.path.basename(self.image_paths[index])}")

    def _to_project_relative(self, path):
        abs_project = os.path.abspath(self.project_dir)
        abs_path = os.path.abspath(path)
        try:
            rel = os.path.relpath(abs_path, abs_project)
            if not rel.startswith(".."):
                return ResourceManager.portable_path(rel)
        except Exception:
            pass
        return ResourceManager.portable_path(abs_path)

    def _validate_and_build_result(self):
        clip_name = self.clip_name_edit.text().strip()
        if not clip_name:
            QMessageBox.warning(self, "Validation", "Clip name is required.")
            return None
        save_path = self.save_path_edit.text().strip()
        if not save_path:
            QMessageBox.warning(self, "Validation", "Please choose a .anim save path.")
            return None
        if not save_path.endswith(".anim"):
            save_path += ".anim"
        abs_save_path = os.path.abspath(save_path)
        abs_project = os.path.abspath(self.project_dir)
        rel_to_project = os.path.relpath(abs_save_path, abs_project)
        if rel_to_project.startswith(".."):
            QMessageBox.warning(self, "Validation", "Animation clip file must be inside the project folder.")
            return None
        source_type = self.source_combo.currentData()
        result = {
            "name": clip_name,
            "fps": float(self.fps_spin.value()),
            "loop": bool(self.loop_chk.isChecked()),
            "source_type": source_type,
            "save_path": abs_save_path
        }
        if source_type == "spritesheet":
            sheet_path = self.sheet_path_edit.text().strip()
            if not sheet_path:
                QMessageBox.warning(self, "Validation", "Select a spritesheet image.")
                return None
            result["sheet_path"] = self._to_project_relative(sheet_path)
            result["frame_width"] = int(self.frame_width_spin.value())
            result["frame_height"] = int(self.frame_height_spin.value())
            result["start_frame"] = int(self.start_frame_spin.value())
            result["frame_count"] = int(self.frame_count_spin.value())
            result["margin"] = int(self.margin_spin.value())
            result["spacing"] = int(self.spacing_spin.value())
            return result
        if not self.image_paths:
            QMessageBox.warning(self, "Validation", "Select at least one image for the sequence.")
            return None
        result["image_paths"] = [self._to_project_relative(path) for path in self.image_paths]
        return result

    def accept(self):
        data = self._validate_and_build_result()
        if data is None:
            return
        self.result_data = data
        super().accept()

class InspectorDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Inspector", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMinimumWidth(360)
        
        # Main widget to hold the scroll area
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container for the actual inspector content
        self.container_widget = QWidget()
        self.layout = QVBoxLayout(self.container_widget)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.container_widget)
        self.main_layout.addWidget(self.scroll_area)
        
        self.setWidget(self.main_widget)
        self.current_entities = []
        # Persist collapse state across inspector rebuilds (add/remove component, refresh)
        self._component_section_expanded = {}

    def set_entities(self, entities):
        # Handle single entity input for backward compatibility
        if entities and not isinstance(entities, list):
            entities = [entities]
        
        self.current_entities = entities or []
        self.update_callbacks = []
        
        # Clear previous widgets
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if not self.current_entities:
            self.layout.addWidget(QLabel("No entity selected"))
            return

        # Common header
        if len(self.current_entities) == 1:
            entity = self.current_entities[0]
            self.name_edit = QLineEdit(entity.name)
            self.name_edit.textChanged.connect(self.on_name_changed)
            self.layout.addWidget(self.name_edit)
        else:
            self.layout.addWidget(QLabel(f"<b>{len(self.current_entities)} entities selected</b>"))
            self.name_edit = QLineEdit("Multiple values")
            self.name_edit.setEnabled(False)
            self.layout.addWidget(self.name_edit)

        # Find common components
        # Get component types of the first entity
        if not self.current_entities:
            return
            
        first_entity = self.current_entities[0]
        common_types = set(first_entity.components.keys())
        
        for entity in self.current_entities[1:]:
            entity_types = set(entity.components.keys())
            common_types &= entity_types

        ordered_common_types = []
        if Transform in common_types:
            ordered_common_types.append(Transform)
        for comp_type in first_entity.components.keys():
            if comp_type != Transform and comp_type in common_types:
                ordered_common_types.append(comp_type)
        remaining = [comp_type for comp_type in common_types if comp_type not in ordered_common_types]
        remaining.sort(key=lambda comp_type: comp_type.__name__)
        ordered_common_types.extend(remaining)

        for comp_type in ordered_common_types:
            components = [e.components[comp_type] for e in self.current_entities]
            if comp_type == Transform:
                self.add_transform_ui(components)
            elif comp_type == CameraComponent:
                self.add_camera_ui(components)
            elif comp_type == SpriteRenderer:
                self.add_sprite_ui(components)
            elif comp_type == ScriptComponent:
                self.add_script_ui(components)
            elif comp_type == SoundComponent:
                self.add_sound_ui(components)
            elif comp_type == WebSocketComponent:
                self.add_websocket_ui(components)
            elif comp_type == HTTPClientComponent:
                self.add_http_client_ui(components)
            elif comp_type == HTTPRequestComponent:
                self.add_http_request_ui(components)
            elif comp_type == WebviewComponent:
                self.add_webview_ui(components)
            elif comp_type == WebRTCComponent:
                self.add_webrtc_ui(components)
            elif comp_type == MultiplayerComponent:
                self.add_multiplayer_ui(components)
            elif comp_type == NetworkIdentityComponent:
                self.add_network_identity_ui(components)
            elif comp_type == Rigidbody2D:
                self.add_rigidbody_ui(components)
            elif comp_type == BoxCollider2D:
                self.add_box_collider_ui(components)
            elif comp_type == CircleCollider2D:
                self.add_circle_collider_ui(components)
            elif comp_type == PolygonCollider2D:
                self.add_polygon_collider_ui(components)
            elif comp_type == AnimatorComponent:
                self.add_animator_ui(components)
            elif comp_type == ParticleEmitterComponent:
                self.add_particle_emitter_ui(components)
            elif comp_type == TextRenderer:
                self.add_text_renderer_ui(components)
            elif comp_type == ButtonComponent:
                self.add_button_ui(components)
            elif comp_type == TextInputComponent:
                self.add_text_input_ui(components)
            elif comp_type == SliderComponent:
                self.add_slider_ui(components)
            elif comp_type == ProgressBarComponent:
                self.add_progress_bar_ui(components)
            elif comp_type == CheckBoxComponent:
                self.add_checkbox_ui(components)
            elif comp_type == ImageRenderer:
                self.add_ui_image_ui(components)
            elif comp_type == HBoxContainerComponent:
                self.add_hbox_ui(components)
            elif comp_type == VBoxContainerComponent:
                self.add_vbox_ui(components)
            elif comp_type == GridBoxContainerComponent:
                self.add_gridbox_ui(components)
            elif comp_type == TilemapComponent:
                self.add_tilemap_ui(components)
            elif comp_type == TimerComponent:
                self.add_timer_ui(components)
            elif comp_type == SteeringAgentComponent:
                self.add_steering_agent_ui(components)
            elif comp_type == SeekBehavior:
                self.add_seek_ui(components)
            elif comp_type == FleeBehavior:
                self.add_flee_ui(components)
            elif comp_type == ArriveBehavior:
                self.add_arrive_ui(components)
            elif comp_type == WanderBehavior:
                self.add_wander_ui(components)
            elif comp_type == SeparationBehavior:
                self.add_separation_ui(components)
            elif comp_type == CohesionBehavior:
                self.add_cohesion_ui(components)
            elif comp_type == AlignmentBehavior:
                self.add_alignment_ui(components)
            elif comp_type == PointLight2D:
                self.add_point_light_ui(components)
            elif comp_type == SpotLight2D:
                self.add_spot_light_ui(components)
            elif comp_type == LightOccluder2D:
                self.add_light_occluder_ui(components)

        # Add Component Button
        self.add_btn = QPushButton("Add Component")
        self.add_btn.clicked.connect(self.show_add_component_menu)
        self.layout.addWidget(self.add_btn)
        
        # Stretch to push everything up
        self.layout.addStretch()

    def refresh_values(self):
        # Trigger any registered callbacks to refresh UI values without rebuilding
        if hasattr(self, 'update_callbacks'):
            for callback in self.update_callbacks:
                callback()

    def set_entity(self, entity):
        # Backward compatibility wrapper
        self.set_entities([entity] if entity else [])

    def on_name_changed(self, text):
        if len(self.current_entities) == 1:
            self.current_entities[0].name = text
            # Refresh hierarchy name
            if self.parent() and hasattr(self.parent(), 'hierarchy_dock'):
                self.parent().hierarchy_dock.refresh()

    def refresh_name(self):
        if len(self.current_entities) == 1 and hasattr(self, 'name_edit'):
             self.name_edit.blockSignals(True)
             self.name_edit.setText(self.current_entities[0].name)
             self.name_edit.blockSignals(False)

    def _ordered_component_types(self, entity):
        ordered = list(entity.components.keys())
        if Transform in ordered:
            ordered.remove(Transform)
            ordered.insert(0, Transform)
        return ordered

    def _rebuild_component_order(self, entity, ordered_types):
        rebuilt = {}
        for comp_type in ordered_types:
            component = entity.components.get(comp_type)
            if component is not None:
                rebuilt[comp_type] = component
        for comp_type, component in entity.components.items():
            if comp_type not in rebuilt:
                rebuilt[comp_type] = component
        entity.components = rebuilt

    def _move_component_in_selection(self, component_type, direction):
        if component_type == Transform:
            return
        for entity in self.current_entities:
            if component_type not in entity.components:
                continue
            ordered = self._ordered_component_types(entity)
            index = ordered.index(component_type)
            target = index + direction
            if target < 0 or target >= len(ordered):
                continue
            if target == 0 and ordered[0] == Transform:
                continue
            ordered[index], ordered[target] = ordered[target], ordered[index]
            if Transform in ordered and ordered[0] != Transform:
                ordered.remove(Transform)
                ordered.insert(0, Transform)
            self._rebuild_component_order(entity, ordered)
        self.set_entities(self.current_entities)

    def _remove_component_from_selection(self, component_type):
        if component_type == Transform:
            return
        if component_type == CameraComponent:
            protected = [
                entity for entity in self.current_entities
                if self._is_protected_main_camera(entity) and CameraComponent in entity.components
            ]
            if protected:
                QMessageBox.information(self, "Protected Component", "Main Camera CameraComponent cannot be removed. You can deactivate it or give more priority to your custom camera component")
        if component_type == SpriteRenderer:
            entities_with_collaborator = [
                entity for entity in self.current_entities
                if SpriteRenderer in entity.components and AnimatorComponent in entity.components
            ]
            if entities_with_collaborator:
                message = "Removing SpriteRenderer will also remove AnimatorComponent. Continue?"
                if len(entities_with_collaborator) > 1:
                    message = "Removing SpriteRenderer will also remove AnimatorComponent on selected entities. Continue?"
                reply = QMessageBox.question(
                    self,
                    "Remove Collaborating Components",
                    message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            for entity in self.current_entities:
                if SpriteRenderer not in entity.components:
                    continue
                if AnimatorComponent in entity.components:
                    entity.remove_component(AnimatorComponent)
                entity.remove_component(SpriteRenderer)
            self.set_entities(self.current_entities)
            return
        for entity in self.current_entities:
            if component_type == CameraComponent and self._is_protected_main_camera(entity):
                continue
            if component_type in entity.components:
                entity.remove_component(component_type)
        self.set_entities(self.current_entities)

    _COMPONENT_ICONS = {
        "Transform": ("fa5s.arrows-alt", None),  # None = use theme_icon_color()
        "SpriteRenderer": ("fa5s.image", "#64b4ff"),
        "CameraComponent": ("fa5s.camera", "#78c878"),
        "ScriptComponent": ("fa5s.scroll", "#dcb450"),
        "SoundComponent": ("fa5s.volume-up", "#b482dc"),
        "WebSocketComponent": ("fa5s.plug", "#50b4dc"),
        "HTTPClientComponent": ("fa5s.satellite-dish", "#50b4dc"),
        "HTTPRequestComponent": ("fa5s.envelope", "#50b4dc"),
        "WebviewComponent": ("fa5s.globe", "#50b4dc"),
        "WebRTCComponent": ("fa5s.video", "#50b4dc"),
        "MultiplayerComponent": ("fa5s.users", "#50b4dc"),
        "NetworkIdentityComponent": ("fa5s.id-badge", "#50b4dc"),
        "Rigidbody2D": ("fa5s.magnet", "#ffb43c"),
        "BoxCollider2D": ("fa5s.vector-square", "#64dc64"),
        "CircleCollider2D": ("fa5s.circle", "#64dc64"),
        "PolygonCollider2D": ("fa5s.draw-polygon", "#64dc64"),
        "AnimatorComponent": ("fa5s.film", "#ff8c64"),
        "ParticleEmitterComponent": ("fa5s.magic", "#ffdc50"),
        "TilemapComponent": ("fa5s.th", "#78c8a0"),
        "TextRenderer": ("fa5s.font", "#c896ff"),
        "ButtonComponent": ("fa5s.hand-pointer", "#c896ff"),
        "TextInputComponent": ("fa5s.keyboard", "#c896ff"),
        "SliderComponent": ("fa5s.sliders-h", "#c896ff"),
        "ProgressBarComponent": ("fa5s.tasks", "#c896ff"),
        "CheckBoxComponent": ("fa5s.check-square", "#c896ff"),
        "ImageRenderer": ("fa5s.image", "#c896ff"),
        "HBoxContainerComponent": ("fa5s.arrows-alt-h", "#c896ff"),
        "VBoxContainerComponent": ("fa5s.arrows-alt-v", "#c896ff"),
        "GridBoxContainerComponent": ("fa5s.border-all", "#c896ff"),
        "TimerComponent": ("fa5s.stopwatch", "#b4dc78"),
        "SteeringAgentComponent": ("fa5s.crosshairs", "#b4c864"),
        "SeekBehavior": ("fa5s.arrow-right", "#b4c864"),
        "FleeBehavior": ("fa5s.arrow-left", "#b4c864"),
        "ArriveBehavior": ("fa5s.bullseye", "#b4c864"),
        "WanderBehavior": ("fa5s.random", "#b4c864"),
        "SeparationBehavior": ("fa5s.expand-arrows-alt", "#b4c864"),
        "CohesionBehavior": ("fa5s.link", "#b4c864"),
        "AlignmentBehavior": ("fa5s.arrow-up", "#b4c864"),
        "PointLight2D": ("fa5s.lightbulb", "#ffd700"),
        "SpotLight2D": ("fa5s.caret-down", "#ffd700"),
        "LightOccluder2D": ("fa5s.square", "#8b8b8b"),
    }

    def _add_component_section(self, name, component_type, count, content_widget):
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = name if count <= 1 else f"{name} (Multi-Edit)"

        collapse_btn = QToolButton()
        collapse_btn.setCheckable(True)
        expanded = self._component_section_expanded.get(name, True)
        collapse_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        collapse_btn.setFixedSize(22, 22)
        collapse_btn.setStyleSheet("QToolButton { border: none; }")
        collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        collapse_btn.blockSignals(True)
        collapse_btn.setChecked(expanded)
        collapse_btn.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        content_widget.setVisible(expanded)
        collapse_btn.blockSignals(False)
        header_layout.addWidget(collapse_btn)

        icon_info = self._COMPONENT_ICONS.get(name)
        if icon_info:
            color = icon_info[1] if icon_info[1] is not None else theme_icon_color()
            icon_label = QLabel()
            icon_label.setPixmap(self._component_icon(icon_info[0], color).pixmap(16, 16))
            icon_label.setFixedSize(20, 20)
            header_layout.addWidget(icon_label)
        label = QLabel(f"<b>{title}</b>")
        header_layout.addWidget(label)
        header_layout.addStretch()

        c = theme_icon_color()
        up_btn = QPushButton()
        up_btn.setIcon(qta.icon("fa5s.chevron-up", color=c))
        down_btn = QPushButton()
        down_btn.setIcon(qta.icon("fa5s.chevron-down", color=c))
        remove_btn = QPushButton()
        remove_btn.setIcon(qta.icon("fa5s.times", color="#ff6b6b"))
        up_btn.setFixedWidth(28)
        down_btn.setFixedWidth(28)
        remove_btn.setFixedWidth(28)

        up_btn.clicked.connect(lambda _=False, ct=component_type: self._move_component_in_selection(ct, -1))
        down_btn.clicked.connect(lambda _=False, ct=component_type: self._move_component_in_selection(ct, 1))
        remove_btn.clicked.connect(lambda _=False, ct=component_type: self._remove_component_from_selection(ct))

        if component_type == Transform:
            up_btn.setEnabled(False)
            down_btn.setEnabled(False)
            remove_btn.setEnabled(False)
        elif component_type == CameraComponent:
            removable_exists = any(
                CameraComponent in entity.components and not self._is_protected_main_camera(entity)
                for entity in self.current_entities
            )
            remove_btn.setEnabled(removable_exists)

        header_layout.addWidget(up_btn)
        header_layout.addWidget(down_btn)
        header_layout.addWidget(remove_btn)
        self.layout.addWidget(header)
        self.layout.addWidget(content_widget)

        def on_collapse_toggled(is_expanded):
            self._component_section_expanded[name] = is_expanded
            content_widget.setVisible(is_expanded)
            collapse_btn.setArrowType(Qt.ArrowType.DownArrow if is_expanded else Qt.ArrowType.RightArrow)

        collapse_btn.toggled.connect(on_collapse_toggled)

    def _is_protected_main_camera(self, entity):
        if not entity:
            return False
        if entity.name != "Main Camera":
            return False
        return entity.get_component(CameraComponent) is not None

    def update_theme_icons(self):
        """Refresh icons when the theme changes."""
        if self.current_entities:
            self.set_entities(self.current_entities)

    def _component_icon(self, icon_name, color="#c8c8c8"):
        try:
            return qta.icon(icon_name, color=color)
        except Exception:
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)
            return QIcon(pixmap)

    def show_add_component_menu(self):
        if not self.current_entities:
            return
            
        menu = QMenu(self)
        actions_added = False
        
        # Check if ALL entities lack the component to allow adding
        # Or allow adding if ANY lacks it? 
        # Strict approach: only allow if ALL lack it (to ensure commonality)
        # Or check individually.
        # For simplicity, let's say we can only add if NONE have it (common scenario)
        # or if we are smart, we add to those who don't have it.
        
        # Let's check common components again to see what is missing

        # We can add SpriteRenderer if not present in common types?
        # Or better: check if we can add to all.
        
        can_add_sprite = all(SpriteRenderer not in e.components for e in self.current_entities)
        if can_add_sprite:
            menu.addAction(self._component_icon("fa5s.image", "#64b4ff"), "Sprite Renderer", lambda: self.batch_add_component(SpriteRenderer))
            actions_added = True

        can_add_camera = all(CameraComponent not in e.components for e in self.current_entities)
        if can_add_camera:
            menu.addAction(self._component_icon("fa5s.camera", "#78c878"), "Camera Component", lambda: self.batch_add_component(CameraComponent))
            actions_added = True
            
        can_add_script = True # Scripts can be multiple? No, ScriptComponent is unique per entity currently in this engine design?
        # Looking at ECS, components are stored by type. So only one ScriptComponent per entity.
        can_add_script = all(ScriptComponent not in e.components for e in self.current_entities)
        
        if can_add_script:
            menu.addAction(self._component_icon("fa5s.scroll", "#dcb450"), "Script Component", self.add_new_script_component)
            actions_added = True

        can_add_sound = all(SoundComponent not in e.components for e in self.current_entities)
        if can_add_sound:
            menu.addAction(self._component_icon("fa5s.volume-up", "#b482dc"), "Sound Component", lambda: self.batch_add_component(SoundComponent))
            actions_added = True

        # Network submenu
        network_menu = menu.addMenu(self._component_icon("fa5s.network-wired", "#50b4dc"), "Network")
        network_actions_added = False

        if all(WebSocketComponent not in e.components for e in self.current_entities):
            network_menu.addAction(self._component_icon("fa5s.plug", "#50b4dc"), "WebSocket", lambda: self.batch_add_component(WebSocketComponent))
            network_actions_added = True
        if all(HTTPClientComponent not in e.components for e in self.current_entities):
            network_menu.addAction(self._component_icon("fa5s.satellite-dish", "#50b4dc"), "HTTP Client", lambda: self.batch_add_component(HTTPClientComponent))
            network_actions_added = True
        if all(HTTPRequestComponent not in e.components for e in self.current_entities):
            network_menu.addAction(self._component_icon("fa5s.envelope", "#50b4dc"), "HTTP Request", lambda: self.batch_add_component(HTTPRequestComponent))
            network_actions_added = True
        if all(WebviewComponent not in e.components for e in self.current_entities):
            network_menu.addAction(self._component_icon("fa5s.globe", "#50b4dc"), "Webview", lambda: self.batch_add_component(WebviewComponent))
            network_actions_added = True
        if all(WebRTCComponent not in e.components for e in self.current_entities):
            network_menu.addAction(self._component_icon("fa5s.video", "#50b4dc"), "WebRTC", lambda: self.batch_add_component(WebRTCComponent))
            network_actions_added = True
        if all(MultiplayerComponent not in e.components for e in self.current_entities):
            network_menu.addAction(self._component_icon("fa5s.users", "#50b4dc"), "Multiplayer", lambda: self.batch_add_component(MultiplayerComponent))
            network_actions_added = True
        if all(NetworkIdentityComponent not in e.components for e in self.current_entities):
            network_menu.addAction(self._component_icon("fa5s.id-badge", "#50b4dc"), "Network Identity", lambda: self.batch_add_component(NetworkIdentityComponent))
            network_actions_added = True

        if network_actions_added:
            actions_added = True
        else:
            network_menu.deleteLater()

        physics_menu = menu.addMenu(self._component_icon("fa5s.bolt", "#ffb43c"), "Physics")
        physics_actions_added = False

        can_add_rigidbody = all(Rigidbody2D not in e.components for e in self.current_entities)
        if can_add_rigidbody:
            physics_menu.addAction(self._component_icon("fa5s.magnet", "#ffb43c"), "Rigidbody 2D", self.batch_add_rigidbody)
            physics_actions_added = True

        can_add_box_collider = all(BoxCollider2D not in e.components for e in self.current_entities)
        if can_add_box_collider:
            physics_menu.addAction(self._component_icon("fa5s.vector-square", "#64dc64"), "Box Collider 2D", self.batch_add_box_collider)
            physics_actions_added = True

        can_add_circle_collider = all(CircleCollider2D not in e.components for e in self.current_entities)
        if can_add_circle_collider:
            physics_menu.addAction(self._component_icon("fa5s.circle", "#64dc64"), "Circle Collider 2D", self.batch_add_circle_collider)
            physics_actions_added = True

        can_add_polygon_collider = all(PolygonCollider2D not in e.components for e in self.current_entities)
        if can_add_polygon_collider:
            physics_menu.addAction(self._component_icon("fa5s.draw-polygon", "#64dc64"), "Polygon Collider 2D", self.batch_add_polygon_collider)
            physics_actions_added = True

        if physics_actions_added:
            actions_added = True
        else:
            physics_menu.deleteLater()

        can_add_animator = all(AnimatorComponent not in e.components for e in self.current_entities)
        if can_add_animator:
            menu.addAction(self._component_icon("fa5s.film", "#ff8c64"), "Animator Component", lambda: self.batch_add_component(AnimatorComponent))
            actions_added = True

        can_add_particle_emitter = all(ParticleEmitterComponent not in e.components for e in self.current_entities)
        if can_add_particle_emitter:
            menu.addAction(self._component_icon("fa5s.magic", "#ffdc50"), "Particle Emitter", lambda: self.batch_add_component(ParticleEmitterComponent))
            actions_added = True

        can_add_tilemap = all(TilemapComponent not in e.components for e in self.current_entities)
        if can_add_tilemap:
            menu.addAction(self._component_icon("fa5s.th", "#78c8a0"), "Tilemap", lambda: self.batch_add_component(TilemapComponent))
            actions_added = True

        can_add_timer = all(TimerComponent not in e.components for e in self.current_entities)
        if can_add_timer:
            menu.addAction(self._component_icon("fa5s.stopwatch", "#b4dc78"), "Timer", lambda: self.batch_add_component(TimerComponent))
            actions_added = True

        # UI Components Submenu
        ui_menu = menu.addMenu(self._component_icon("fa5s.palette", "#c896ff"), "UI")
        ui_actions_added = False
        
        if all(TextRenderer not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.font", "#c896ff"), "Text Renderer", lambda: self.batch_add_component(TextRenderer))
            ui_actions_added = True
            
        if all(ButtonComponent not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.hand-pointer", "#c896ff"), "Button", lambda: self.batch_add_component(ButtonComponent))
            ui_actions_added = True
            
        if all(TextInputComponent not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.keyboard", "#c896ff"), "Text Input", lambda: self.batch_add_component(TextInputComponent))
            ui_actions_added = True
            
        if all(SliderComponent not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.sliders-h", "#c896ff"), "Slider", lambda: self.batch_add_component(SliderComponent))
            ui_actions_added = True
            
        if all(ProgressBarComponent not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.tasks", "#c896ff"), "Progress Bar", lambda: self.batch_add_component(ProgressBarComponent))
            ui_actions_added = True
            
        if all(CheckBoxComponent not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.check-square", "#c896ff"), "Check Box", lambda: self.batch_add_component(CheckBoxComponent))
            ui_actions_added = True
            
        if all(ImageRenderer not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.image", "#c896ff"), "Image (UI)", lambda: self.batch_add_component(ImageRenderer))
            ui_actions_added = True
            
        if all(HBoxContainerComponent not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.arrows-alt-h", "#c896ff"), "HBox Container", lambda: self.batch_add_component(HBoxContainerComponent))
            ui_actions_added = True
            
        if all(VBoxContainerComponent not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.arrows-alt-v", "#c896ff"), "VBox Container", lambda: self.batch_add_component(VBoxContainerComponent))
            ui_actions_added = True
            
        if all(GridBoxContainerComponent not in e.components for e in self.current_entities):
            ui_menu.addAction(self._component_icon("fa5s.border-all", "#c896ff"), "GridBox Container", lambda: self.batch_add_component(GridBoxContainerComponent))
            ui_actions_added = True

        if ui_actions_added:
            actions_added = True
        else:
            ui_menu.deleteLater()

        # Steering AI Submenu
        nav_menu = menu.addMenu(self._component_icon("fa5s.compass", "#b4c864"), "Steering AI")
        nav_actions_added = False

        if all(SteeringAgentComponent not in e.components for e in self.current_entities):
            nav_menu.addAction(self._component_icon("fa5s.crosshairs", "#b4c864"), "Steering Agent", lambda: self.batch_add_component(SteeringAgentComponent))
            nav_actions_added = True
        if all(SeekBehavior not in e.components for e in self.current_entities):
            nav_menu.addAction(self._component_icon("fa5s.arrow-right", "#b4c864"), "Seek Behavior", lambda: self.batch_add_component(SeekBehavior))
            nav_actions_added = True
        if all(FleeBehavior not in e.components for e in self.current_entities):
            nav_menu.addAction(self._component_icon("fa5s.arrow-left", "#b4c864"), "Flee Behavior", lambda: self.batch_add_component(FleeBehavior))
            nav_actions_added = True
        if all(ArriveBehavior not in e.components for e in self.current_entities):
            nav_menu.addAction(self._component_icon("fa5s.bullseye", "#b4c864"), "Arrive Behavior", lambda: self.batch_add_component(ArriveBehavior))
            nav_actions_added = True
        if all(WanderBehavior not in e.components for e in self.current_entities):
            nav_menu.addAction(self._component_icon("fa5s.random", "#b4c864"), "Wander Behavior", lambda: self.batch_add_component(WanderBehavior))
            nav_actions_added = True
        if all(SeparationBehavior not in e.components for e in self.current_entities):
            nav_menu.addAction(self._component_icon("fa5s.expand-arrows-alt", "#b4c864"), "Separation Behavior", lambda: self.batch_add_component(SeparationBehavior))
            nav_actions_added = True
        if all(CohesionBehavior not in e.components for e in self.current_entities):
            nav_menu.addAction(self._component_icon("fa5s.link", "#b4c864"), "Cohesion Behavior", lambda: self.batch_add_component(CohesionBehavior))
            nav_actions_added = True
        if all(AlignmentBehavior not in e.components for e in self.current_entities):
            nav_menu.addAction(self._component_icon("fa5s.arrow-up", "#b4c864"), "Alignment Behavior", lambda: self.batch_add_component(AlignmentBehavior))
            nav_actions_added = True

        if nav_actions_added:
            actions_added = True
        else:
            nav_menu.deleteLater()

        # Lighting Submenu
        light_menu = menu.addMenu(self._component_icon("fa5s.lightbulb", "#ffd700"), "Lighting")
        light_actions_added = False

        if all(PointLight2D not in e.components for e in self.current_entities):
            light_menu.addAction(self._component_icon("fa5s.lightbulb", "#ffd700"), "Point Light 2D", lambda: self.batch_add_component(PointLight2D))
            light_actions_added = True
        if all(SpotLight2D not in e.components for e in self.current_entities):
            light_menu.addAction(self._component_icon("fa5s.caret-down", "#ffd700"), "Spot Light 2D", lambda: self.batch_add_component(SpotLight2D))
            light_actions_added = True
        if all(LightOccluder2D not in e.components for e in self.current_entities):
            light_menu.addAction(self._component_icon("fa5s.square", "#8b8b8b"), "Light Occluder 2D", self.batch_add_light_occluder)
            light_actions_added = True

        if light_actions_added:
            actions_added = True
        else:
            light_menu.deleteLater()

        if not actions_added:
            action = menu.addAction("No more components available")
            action.setEnabled(False)
            
        # Use cursor position to ensure menu is visible
        menu.exec(QCursor.pos())

    def batch_add_component(self, component_class, **kwargs):
        if component_class == AnimatorComponent:
            for entity in self.current_entities:
                if AnimatorComponent in entity.components:
                    continue
                if SpriteRenderer not in entity.components:
                    entity.add_component(SpriteRenderer())
                entity.add_component(AnimatorComponent(**kwargs))
            self.set_entities(self.current_entities)
            return
        
        for entity in self.current_entities:
            if component_class not in entity.components:
                component = component_class(**kwargs)
                # Set entity reference for components that need it
                if hasattr(component, 'entity'):
                    component.entity = entity
                entity.add_component(component)
        self.set_entities(self.current_entities)

    def batch_add_rigidbody(self):
        self.batch_add_component(
            Rigidbody2D,
            velocity_x=0.0,
            velocity_y=0.0,
            mass=1.0,
            angular_velocity=0.0,
            gravity_scale=1.0,
            use_gravity=True,
            body_type=Rigidbody2D.BODY_TYPE_DYNAMIC,
            restitution=0.0,
            linear_damping=0.0,
            angular_damping=0.0,
            freeze_rotation=False
        )

    def batch_add_box_collider(self):
        for entity in self.current_entities:
            if BoxCollider2D in entity.components:
                continue
            sprite = entity.get_component(SpriteRenderer)
            transform = entity.get_component(Transform)
            width = 50.0
            height = 50.0
            if sprite:
                width = sprite.width
                height = sprite.height
            elif transform:
                width = max(1.0, 50.0 * abs(transform.scale_x))
                height = max(1.0, 50.0 * abs(transform.scale_y))
            entity.add_component(BoxCollider2D(width=width, height=height))
        self.set_entities(self.current_entities)

    def batch_add_circle_collider(self):
        for entity in self.current_entities:
            if CircleCollider2D in entity.components:
                continue
            sprite = entity.get_component(SpriteRenderer)
            transform = entity.get_component(Transform)
            radius = 25.0
            if sprite:
                radius = max(sprite.width, sprite.height) * 0.5
            elif transform:
                radius = max(1.0, 25.0 * max(abs(transform.scale_x), abs(transform.scale_y)))
            entity.add_component(CircleCollider2D(radius=radius))
        self.set_entities(self.current_entities)

    def batch_add_polygon_collider(self):
        for entity in self.current_entities:
            if PolygonCollider2D in entity.components:
                continue
            sprite = entity.get_component(SpriteRenderer)
            transform = entity.get_component(Transform)
            width = 50.0
            height = 50.0
            if sprite:
                width = max(1.0, float(sprite.width))
                height = max(1.0, float(sprite.height))
            elif transform:
                width = max(1.0, 50.0 * abs(transform.scale_x))
                height = max(1.0, 50.0 * abs(transform.scale_y))
            half_w = width * 0.5
            half_h = height * 0.5
            points = [
                (-half_w, -half_h),
                (half_w, -half_h),
                (half_w, half_h),
                (-half_w, half_h)
            ]
            entity.add_component(PolygonCollider2D(points=points))
        self.set_entities(self.current_entities)

    def batch_add_light_occluder(self):
        for entity in self.current_entities:
            if LightOccluder2D in entity.components:
                continue
            sprite = entity.get_component(SpriteRenderer)
            width = 50.0
            height = 50.0
            if sprite:
                width = max(1.0, float(sprite.width))
                height = max(1.0, float(sprite.height))
            occ = LightOccluder2D(shape="box", width=width, height=height)
            occ.entity = entity
            entity.add_component(occ)
        self.set_entities(self.current_entities)

    def add_new_script_component(self):
        if not self.current_entities:
            return

        menu = QMenu(self)
        menu.addAction("Use Existing Script", self._attach_existing_script)
        menu.addAction("Create New Script", self._create_and_attach_script)
        menu.exec(QCursor.pos())

    def _attach_existing_script(self):
        if not self.current_entities:
            return

        start_dir = self._project_base_dir()

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Existing Script", start_dir, "Python Files (*.py)")
        if not file_path:
            return

        try:
            class_name = self._detect_script_class_name(file_path)
            final_path = self._to_project_relative_path(file_path)

            for entity in self.current_entities:
                if ScriptComponent not in entity.components:
                    comp = ScriptComponent(script_path=final_path, class_name=class_name)
                    entity.add_component(comp)

            self.set_entities(self.current_entities)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to attach script: {e}")

    def _detect_script_class_name(self, file_path: str) -> str:
        """Scan a .py file for a class that extends ScriptComponent and return its name."""
        import re
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r'class\s+(\w+)\s*\(\s*ScriptComponent\s*\)', content)
            if match:
                return match.group(1)
        except Exception:
            pass
        # Fallback: derive from filename
        name = os.path.basename(file_path).replace(".py", "")
        name = "".join(x for x in name if x.isalnum() or x == '_')
        if not name or not name[0].isalpha():
            name = "Script" + name
        return name

    def _create_and_attach_script(self):
        if not self.current_entities:
            return

        entity = self.current_entities[0]
        default_name = "".join(x for x in entity.name if x.isalnum()) or "NewScript"
        default_name = default_name[0].upper() + default_name[1:]

        start_dir = QDir.currentPath()
        if self.parent() and hasattr(self.parent(), 'project_path') and self.parent().project_path:
             start_dir = self.parent().project_path

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Create Script", os.path.join(start_dir, f"{default_name}.py"), "Python Files (*.py)")

        if file_path:
            try:
                class_name = os.path.basename(file_path).replace(".py", "")
                class_name = "".join(x for x in class_name if x.isalnum() or x == '_')
                if not class_name[0].isalpha():
                    class_name = "Script" + class_name

                template = f"""from core.components.script import ScriptComponent
from core.input import Input
from core.components import Transform
import pygame

class {class_name}(ScriptComponent):
    def on_start(self):
        # Called once when the script starts
        print("{class_name} started on " + self.entity.name)

    def on_update(self, dt: float):
        # Called every frame
        pass
        
    
"""
                with open(file_path, "w") as f:
                    f.write(template)

                try:
                    base_dir = os.getcwd()
                    if self.parent() and hasattr(self.parent(), 'project_path') and self.parent().project_path:
                        base_dir = self.parent().project_path
                    final_path = os.path.relpath(file_path, base_dir)
                except Exception:
                    final_path = file_path

                for entity in self.current_entities:
                    if ScriptComponent not in entity.components:
                        comp = ScriptComponent(script_path=final_path, class_name=class_name)
                        entity.add_component(comp)

                self.set_entities(self.current_entities)
                print(f"Created script {class_name} at {file_path} and added to {len(self.current_entities)} entities")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create script: {e}")

    def add_component(self, component):
        # Backward compatibility, unused mostly now
        pass

    def add_transform_ui(self, transforms):
        if not isinstance(transforms, list):
            transforms = [transforms]
            
        group = QWidget()
        form = QFormLayout(group)
        
        def apply_val(attr, val):
            for t in transforms:
                setattr(t, attr, val)

        def create_spin(attr, range_min, range_max, step=1.0):
            values = [getattr(t, attr) for t in transforms]
            spin = UndoableDoubleSpinBox()
            spin.setRange(range_min, range_max)
            spin.setSingleStep(step)
            
            # Check for mixed values
            # Use a small tolerance for floats
            first = values[0]
            is_mixed = any(abs(v - first) > 0.0001 for v in values)
            
            # Capture start values for Undo
            old_values = []
            def on_focus():
                nonlocal old_values
                old_values = [getattr(t, attr) for t in transforms]
            spin.focused.connect(on_focus)
            
            if is_mixed:
                spin.setValue(first)
                # Visual indicator for mixed values (yellow-ish background)
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;") 
                spin.setToolTip(f"Mixed values. First value shown: {first}")
                
                # When value changes, remove the mixed style
                def on_change(val):
                    spin.setStyleSheet("")
                    apply_val(attr, val)
                
                spin.valueChanged.connect(on_change)
            else:
                spin.setValue(first)
                spin.valueChanged.connect(lambda v: apply_val(attr, v))
                
            # Commit change to UndoManager
            def on_commit():
                # Get current main window
                mw = spin.window()
                if hasattr(mw, 'undo_manager'):
                    new_val = spin.value()
                    # Only push if we have old_values (focus happened)
                    if old_values:
                        # Check if actually changed from start (approx)
                        # Actually we should just push, command system handles it?
                        # Or optimize.
                        # If mixed, any change is a change.
                        # If uniform, check against first.
                        cmd = PropertyChangeCommand([t.entity for t in transforms], Transform, attr, old_values, new_val)
                        mw.undo_manager.push(cmd)
            
            spin.editingFinished.connect(on_commit)
                
            return spin

        def create_entity_check(getter, setter):
            entities = [t.entity for t in transforms if t.entity is not None]
            values = [bool(getter(entity)) for entity in entities]
            check = QCheckBox()
            first = values[0]
            is_mixed = any(v != first for v in values)
            if is_mixed:
                check.setTristate(True)
                check.setCheckState(Qt.CheckState.PartiallyChecked)
                check.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
            else:
                check.setChecked(first)

            def on_changed(state):
                checked = state == Qt.CheckState.Checked.value
                old_values = [bool(getter(entity)) for entity in entities]
                for entity in entities:
                    setter(entity, checked)
                check.setTristate(False)
                check.setStyleSheet("")
                mw = check.window()
                if hasattr(mw, "undo_manager"):
                    cmd = EntityPropertyChangeCommand(entities, getter, setter, old_values, checked)
                    mw.undo_manager.push(cmd)

            check.stateChanged.connect(on_changed)
            return check

        x_spin = create_spin('x', -10000, 10000)
        y_spin = create_spin('y', -10000, 10000)
        rot_spin = create_spin('rotation', -360, 360)
        scale_x_spin = create_spin('scale_x', 0.01, 100, 0.1)
        scale_y_spin = create_spin('scale_y', 0.01, 100, 0.1)

        def refresh_spins():
            if not transforms:
                return
            spins_and_attrs = [
                (x_spin, 'x'),
                (y_spin, 'y'),
                (rot_spin, 'rotation'),
                (scale_x_spin, 'scale_x'),
                (scale_y_spin, 'scale_y')
            ]
            for spin, attr in spins_and_attrs:
                values = [getattr(t, attr) for t in transforms]
                if not values:
                    continue
                first = values[0]
                is_mixed = any(abs(v - first) > 0.0001 for v in values)
                spin.blockSignals(True)
                if not is_mixed:
                    spin.setValue(first)
                    spin.setStyleSheet("")
                else:
                    spin.setValue(first)
                    spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
                spin.blockSignals(False)

        if hasattr(self, 'update_callbacks'):
            self.update_callbacks.append(refresh_spins)

        form.addRow("X", x_spin)
        form.addRow("Y", y_spin)
        form.addRow("Rotation", rot_spin)
        form.addRow("Scale X", scale_x_spin)
        form.addRow("Scale Y", scale_y_spin)
        form.addRow("Visible", create_entity_check(lambda e: e.is_visible(), lambda e, v: e.show() if v else e.hide()))
        form.addRow("Process Physics", create_entity_check(lambda e: e.is_physics_processing(), lambda e, v: e.process_physics(v)))
        
        # Layer Management
        def create_layer_combo():
            combo = NoScrollComboBox()
            
            # Get layers from world
            world = transforms[0].entity.world if transforms and transforms[0].entity else None
            layers = world.layers if world else ["Default"]
            combo.addItems(layers)
            
            # Set initial value
            current_layers = [t.entity.layer for t in transforms if t.entity]
            if not current_layers:
                combo.setCurrentIndex(0)
            else:
                first_layer = current_layers[0]
                is_mixed = any(l != first_layer for l in current_layers)
                
                if is_mixed:
                    combo.addItem("Mixed...", "mixed")
                    combo.setCurrentText("Mixed...")
                else:
                    if first_layer in layers:
                        combo.setCurrentText(first_layer)
                    else:
                        combo.setCurrentIndex(0)
            
            def on_layer_changed(index):
                new_layer = combo.currentText()
                if new_layer == "Mixed...":
                    return
                    
                old_values = [t.entity.layer for t in transforms if t.entity]
                entities = [t.entity for t in transforms if t.entity]
                
                for entity in entities:
                    entity.set_layer(new_layer)
                    
                mw = combo.window()
                if hasattr(mw, "undo_manager"):
                    # Use a lambda for getter/setter to adapt to EntityPropertyChangeCommand interface
                    # Or simpler: custom command for layer change?
                    # Let's reuse EntityPropertyChangeCommand but we need to pass methods
                    cmd = EntityPropertyChangeCommand(
                        entities, 
                        lambda e: e.layer, 
                        lambda e, v: e.set_layer(v), 
                        old_values, 
                        new_layer
                    )
                    mw.undo_manager.push(cmd)

            combo.currentIndexChanged.connect(on_layer_changed)
            return combo

        layer_combo = create_layer_combo()
        
        # Layer Edit Button
        layer_edit_btn = QPushButton("Edit Layers")
        def open_layer_editor():
            # Basic dialog to edit layers
            # Ideally this should be a full dialog class, but inline for now
            world = transforms[0].entity.world if transforms and transforms[0].entity else None
            if not world:
                return
                
            dialog = QDialog(group)
            dialog.setWindowTitle("Edit Layers")
            dialog.resize(300, 400)
            layout = QVBoxLayout(dialog)
            
            list_widget = QListWidget()
            list_widget.addItems(world.layers)
            layout.addWidget(list_widget)

            def refresh_layer_combo():
                current = transforms[0].entity.layer
                layer_combo.clear()
                layer_combo.addItems(world.layers)
                if current in world.layers:
                    layer_combo.setCurrentText(current)
                elif "Default" in world.layers:
                    layer_combo.setCurrentText("Default")

            def sync_world_layers_from_list():
                world.layers = [list_widget.item(i).text() for i in range(list_widget.count())]
                refresh_layer_combo()
            
            btn_layout = QHBoxLayout()
            add_btn = QPushButton("Add")
            del_btn = QPushButton("Remove")
            up_btn = QPushButton("Up")
            down_btn = QPushButton("Down")
            btn_layout.addWidget(add_btn)
            btn_layout.addWidget(del_btn)
            btn_layout.addWidget(up_btn)
            btn_layout.addWidget(down_btn)
            layout.addLayout(btn_layout)
            
            def add_layer():
                name, ok = QInputDialog.getText(dialog, "Add Layer", "Layer Name:")
                if ok and name:
                    if name in world.layers:
                        QMessageBox.warning(dialog, "Error", "Layer already exists")
                        return
                    world.layers.append(name)
                    list_widget.addItem(name)
                    refresh_layer_combo()
            
            def remove_layer():
                items = list_widget.selectedItems()
                if not items:
                    return
                name = items[0].text()
                if name == "Default":
                    QMessageBox.warning(dialog, "Error", "Cannot delete Default layer")
                    return
                
                # Check if used? Maybe just fallback to Default
                if name in world.layers:
                    world.layers.remove(name)
                    list_widget.takeItem(list_widget.row(items[0]))
                    
                    # Move entities on this layer to Default
                    for ent in world.entities:
                        if ent.layer == name:
                            ent.set_layer("Default")
                            
                    refresh_layer_combo()

            def move_layer_up():
                row = list_widget.currentRow()
                if row <= 0:
                    return
                item = list_widget.item(row)
                if item.text() == "Default":
                    QMessageBox.warning(dialog, "Error", "Default layer cannot be reordered")
                    return
                previous_item = list_widget.item(row - 1)
                if previous_item and previous_item.text() == "Default":
                    QMessageBox.warning(dialog, "Error", "Default layer cannot be reordered")
                    return
                moving = list_widget.takeItem(row)
                list_widget.insertItem(row - 1, moving)
                list_widget.setCurrentRow(row - 1)
                sync_world_layers_from_list()

            def move_layer_down():
                row = list_widget.currentRow()
                if row < 0 or row >= list_widget.count() - 1:
                    return
                item = list_widget.item(row)
                if item.text() == "Default":
                    QMessageBox.warning(dialog, "Error", "Default layer cannot be reordered")
                    return
                next_item = list_widget.item(row + 1)
                if next_item and next_item.text() == "Default":
                    QMessageBox.warning(dialog, "Error", "Default layer cannot be reordered")
                    return
                moving = list_widget.takeItem(row)
                list_widget.insertItem(row + 1, moving)
                list_widget.setCurrentRow(row + 1)
                sync_world_layers_from_list()

            add_btn.clicked.connect(add_layer)
            del_btn.clicked.connect(remove_layer)
            up_btn.clicked.connect(move_layer_up)
            down_btn.clicked.connect(move_layer_down)
            
            dialog.exec()

        layer_edit_btn.clicked.connect(open_layer_editor)
        
        layer_layout = QHBoxLayout()
        layer_layout.addWidget(layer_combo)
        layer_layout.addWidget(layer_edit_btn)
        form.addRow("Layer", layer_layout)

        # Groups Management
        def create_groups_ui():
            # Similar to layers but multi-select
            # We can use a button to open a dialog or a list widget
            # Let's use a readonly line edit + Edit button
            
            groups_edit = QLineEdit()
            groups_edit.setReadOnly(True)
            
            entities = [t.entity for t in transforms if t.entity]
            if not entities:
                return None
                
            # Determine common groups
            common_groups = set(entities[0].groups)
            for e in entities[1:]:
                common_groups &= e.groups
            
            groups_edit.setText(", ".join(sorted(list(common_groups))))
            
            edit_btn = QPushButton("Edit Groups")
            
            def open_group_editor():
                world = entities[0].world
                if not world:
                    return
                    
                dialog = QDialog(group)
                dialog.setWindowTitle("Edit Groups")
                dialog.resize(360, 460)
                layout = QVBoxLayout(dialog)

                list_widget = QListWidget()
                layout.addWidget(list_widget)

                btn_layout = QHBoxLayout()
                add_group_btn = QPushButton("Create Group")
                delete_group_btn = QPushButton("Delete Group")
                select_members_btn = QPushButton("Select Members")
                btn_layout.addWidget(add_group_btn)
                btn_layout.addWidget(delete_group_btn)
                btn_layout.addWidget(select_members_btn)
                layout.addLayout(btn_layout)

                def refresh_group_items():
                    all_groups = sorted(list(world.groups.keys()), key=lambda value: value.lower())
                    list_widget.clear()
                    for grp in all_groups:
                        item = QListWidgetItem(f"{grp} ({len(world.groups.get(grp, set()))})")
                        item.setData(Qt.ItemDataRole.UserRole, grp)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        has_all = all(e.has_group(grp) for e in entities)
                        has_any = any(e.has_group(grp) for e in entities)
                        if has_all:
                            item.setCheckState(Qt.CheckState.Checked)
                        elif has_any:
                            item.setCheckState(Qt.CheckState.PartiallyChecked)
                        else:
                            item.setCheckState(Qt.CheckState.Unchecked)
                        list_widget.addItem(item)

                def create_group():
                    name, ok = QInputDialog.getText(dialog, "Create Group", "Group Name:")
                    if not ok:
                        return
                    name = str(name).strip()
                    if not name:
                        return
                    for existing_name in world.groups.keys():
                        if existing_name.lower() == name.lower():
                            QMessageBox.warning(dialog, "Error", "Group already exists")
                            return
                    world.groups[name] = set()
                    refresh_group_items()

                def delete_group():
                    item = list_widget.currentItem()
                    if not item:
                        return
                    grp = item.data(Qt.ItemDataRole.UserRole)
                    if grp not in world.groups:
                        return
                    members = list(world.groups.get(grp, set()))
                    for member in members:
                        member.remove_group(grp)
                    if grp in world.groups:
                        del world.groups[grp]
                    refresh_group_items()
                    new_common = set(entities[0].groups)
                    for e in entities[1:]:
                        new_common &= e.groups
                    groups_edit.setText(", ".join(sorted(list(new_common))))

                def select_members():
                    item = list_widget.currentItem()
                    if not item:
                        return
                    grp = item.data(Qt.ItemDataRole.UserRole)
                    members = sorted(list(world.groups.get(grp, set())), key=lambda e: e.name.lower())
                    mw = groups_edit.window()
                    if hasattr(mw, "on_viewport_entity_selected"):
                        mw.on_viewport_entity_selected(members)

                add_group_btn.clicked.connect(create_group)
                delete_group_btn.clicked.connect(delete_group)
                select_members_btn.clicked.connect(select_members)
                refresh_group_items()
                
                btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                layout.addWidget(btn_box)
                
                btn_box.accepted.connect(dialog.accept)
                btn_box.rejected.connect(dialog.reject)
                
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    for i in range(list_widget.count()):
                        item = list_widget.item(i)
                        grp = item.data(Qt.ItemDataRole.UserRole)
                        state = item.checkState()
                        
                        if state == Qt.CheckState.Checked:
                            for e in entities:
                                if not e.has_group(grp):
                                    e.add_group(grp)
                        elif state == Qt.CheckState.Unchecked:
                            for e in entities:
                                if e.has_group(grp):
                                    e.remove_group(grp)
                    
                    new_common = set(entities[0].groups)
                    for e in entities[1:]:
                        new_common &= e.groups
                    groups_edit.setText(", ".join(sorted(list(new_common))))

            edit_btn.clicked.connect(open_group_editor)
            
            container = QWidget()
            l = QHBoxLayout(container)
            l.setContentsMargins(0,0,0,0)
            l.addWidget(groups_edit)
            l.addWidget(edit_btn)
            return container

        groups_ui = create_groups_ui()
        if groups_ui:
            form.addRow("Groups", groups_ui)

        self._add_component_section("Transform", Transform, len(transforms), group)

    def add_camera_ui(self, cameras):
        if not isinstance(cameras, list):
            cameras = [cameras]

        group = QWidget()
        form = QFormLayout(group)

        world = None
        if cameras and cameras[0].entity:
            world = cameras[0].entity.world
        camera_entities = {camera.entity for camera in cameras if camera.entity}

        def create_spin(attr, range_min, range_max, step=0.1, is_int=False):
            values = [getattr(c, attr) for c in cameras]
            spin = NoScrollSpinBox() if is_int else UndoableDoubleSpinBox()
            spin.setRange(range_min, range_max)
            if hasattr(spin, "setSingleStep"):
                spin.setSingleStep(step)

            first = values[0]
            is_mixed = any(v != first for v in values)
            old_values = []

            if hasattr(spin, "focused"):
                def on_focus():
                    nonlocal old_values
                    old_values = [getattr(c, attr) for c in cameras]
                spin.focused.connect(on_focus)

            def apply_value(value):
                for camera in cameras:
                    setattr(camera, attr, int(value) if is_int else float(value))

            if is_mixed:
                spin.setValue(int(first) if is_int else float(first))
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
                def on_change(value):
                    spin.setStyleSheet("")
                    apply_value(value)
                spin.valueChanged.connect(on_change)
            else:
                spin.setValue(int(first) if is_int else float(first))
                spin.valueChanged.connect(apply_value)

            def on_commit():
                mw = spin.window()
                if hasattr(mw, 'undo_manager') and old_values:
                    cmd = PropertyChangeCommand([c.entity for c in cameras], CameraComponent, attr, old_values, spin.value())
                    mw.undo_manager.push(cmd)
            if hasattr(spin, "editingFinished"):
                spin.editingFinished.connect(on_commit)
            return spin

        def create_check(attr):
            values = [bool(getattr(c, attr)) for c in cameras]
            check = QCheckBox()
            old_values = []
            first = values[0]
            is_mixed = any(v != first for v in values)
            if is_mixed:
                check.setTristate(True)
                check.setCheckState(Qt.CheckState.PartiallyChecked)
                check.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
            else:
                check.setChecked(first)

            def on_changed(state):
                nonlocal old_values
                old_values = [bool(getattr(c, attr)) for c in cameras]
                checked = state == Qt.CheckState.Checked.value
                for camera in cameras:
                    setattr(camera, attr, checked)
                check.setTristate(False)
                check.setStyleSheet("")
                mw = check.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = PropertyChangeCommand([c.entity for c in cameras], CameraComponent, attr, old_values, checked)
                    mw.undo_manager.push(cmd)
            check.stateChanged.connect(on_changed)
            return check

        def create_follow_target_selector():
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            search = QLineEdit()
            search.setObjectName("camera_follow_search")
            search.setPlaceholderText("Search entity...")
            follow_list = QListWidget()
            follow_list.setObjectName("camera_follow_list")
            follow_list.setMaximumHeight(220)
            container_layout.addWidget(search)
            container_layout.addWidget(follow_list)
            targets = []
            if world:
                for entity in world.entities:
                    if entity in camera_entities:
                        continue
                    targets.append(entity)
            all_items = [("None", "")]
            all_items.extend((f"{entity.name} ({entity.id[:8]})", entity.id) for entity in targets)

            values = [getattr(c, "follow_target_id", "") for c in cameras]
            first = values[0] if values else ""
            is_mixed = any(v != first for v in values)

            def rebuild_list(filter_text="", target_id=None):
                text = (filter_text or "").strip().lower()
                follow_list.blockSignals(True)
                follow_list.clear()
                for label, item_id in all_items:
                    if item_id == "" or text in label.lower():
                        item = QListWidgetItem(label)
                        item.setData(Qt.ItemDataRole.UserRole, item_id)
                        follow_list.addItem(item)
                follow_list.blockSignals(False)
                if target_id is None:
                    target_id = ""
                selected_row = 0
                for row in range(follow_list.count()):
                    if (follow_list.item(row).data(Qt.ItemDataRole.UserRole) or "") == target_id:
                        selected_row = row
                        break
                if follow_list.count() > 0:
                    follow_list.setCurrentRow(selected_row)

            rebuild_list("", first)
            if is_mixed:
                follow_list.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
                follow_list.setToolTip("Mixed values. First value shown.")

            def on_changed(_current, _previous):
                current_item = follow_list.currentItem()
                if current_item is None:
                    return
                old_values = [getattr(c, "follow_target_id", "") for c in cameras]
                new_value = current_item.data(Qt.ItemDataRole.UserRole) or ""
                for camera in cameras:
                    camera.follow_target_id = new_value
                follow_list.setStyleSheet("")
                follow_list.setToolTip("")
                mw = follow_list.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = PropertyChangeCommand([c.entity for c in cameras], CameraComponent, "follow_target_id", old_values, new_value)
                    mw.undo_manager.push(cmd)

            follow_list.currentItemChanged.connect(on_changed)
            def on_search_changed(text):
                current_item = follow_list.currentItem()
                selected_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else ""
                rebuild_list(text, selected_id)

            search.textChanged.connect(on_search_changed)
            return container

        active_chk = create_check("active")
        priority_spin = create_spin("priority", -1000, 1000, 1, is_int=True)
        zoom_spin = create_spin("zoom", 0.01, 20.0, 0.05)
        rotation_spin = create_spin("rotation", -360.0, 360.0, 1.0)
        viewport_x_spin = create_spin("viewport_x", 0.0, 1.0, 0.05)
        viewport_y_spin = create_spin("viewport_y", 0.0, 1.0, 0.05)
        viewport_w_spin = create_spin("viewport_width", 0.0, 1.0, 0.05)
        viewport_h_spin = create_spin("viewport_height", 0.0, 1.0, 0.05)
        follow_target_combo = create_follow_target_selector()
        follow_rotation_chk = create_check("follow_rotation")

        form.addRow("Active", active_chk)
        form.addRow("Priority", priority_spin)
        form.addRow("Zoom", zoom_spin)
        form.addRow("Rotation", rotation_spin)
        form.addRow("Viewport X", viewport_x_spin)
        form.addRow("Viewport Y", viewport_y_spin)
        form.addRow("Viewport W", viewport_w_spin)
        form.addRow("Viewport H", viewport_h_spin)
        form.addRow("Camera Follow", follow_target_combo)
        form.addRow("Follow Rotation", follow_rotation_chk)

        self._add_component_section("CameraComponent", CameraComponent, len(cameras), group)

    def add_sprite_ui(self, sprites):
        if not isinstance(sprites, list):
            sprites = [sprites]

        group = QWidget()
        form = QFormLayout(group)
        
        def apply_val(attr, val):
            for s in sprites:
                setattr(s, attr, int(val))

        def create_spin(attr, range_min, range_max):
            values = [getattr(s, attr) for s in sprites]
            spin = UndoableDoubleSpinBox()
            spin.setRange(range_min, range_max)
            
            first = values[0]
            is_mixed = any(v != first for v in values)
            
            # Capture start values
            old_values = []
            def on_focus():
                nonlocal old_values
                old_values = [getattr(s, attr) for s in sprites]
            spin.focused.connect(on_focus)
            
            if is_mixed:
                spin.setValue(first)
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
                spin.setToolTip(f"Mixed values. First: {first}")
                
                def on_change(val):
                    spin.setStyleSheet("")
                    apply_val(attr, val)
                spin.valueChanged.connect(on_change)
            else:
                spin.setValue(first)
                spin.valueChanged.connect(lambda v: apply_val(attr, v))
            
            # Commit
            def on_commit():
                mw = spin.window()
                if hasattr(mw, 'undo_manager') and old_values:
                    cmd = PropertyChangeCommand([s.entity for s in sprites], SpriteRenderer, attr, old_values, spin.value())
                    mw.undo_manager.push(cmd)
            spin.editingFinished.connect(on_commit)
            
            return spin

        w_spin = create_spin('width', 1, 10000)
        h_spin = create_spin('height', 1, 10000)
        
        # Image Path
        path_layout = QVBoxLayout()
        
        # Check mixed paths
        paths = [getattr(s, "image_path", "") or "" for s in sprites]
        first_path = paths[0]
        mixed_paths = any(p != first_path for p in paths)
        
        path_edit = UndoableLineEdit(first_path)
        path_edit.setPlaceholderText("Path to image")
        
        # Capture old values
        old_paths = []
        def on_focus():
            nonlocal old_paths
            old_paths = [getattr(s, "image_path", "") or "" for s in sprites]
        path_edit.focused.connect(on_focus)
        
        if mixed_paths:
            path_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
            path_edit.setToolTip("Mixed image paths")
            
        def on_path_edit():
            path_edit.setStyleSheet("")
            self.update_sprites_image(sprites, path_edit.text(), w_spin, h_spin)
            
            # Push undo
            mw = path_edit.window()
            if hasattr(mw, 'undo_manager') and old_paths:
                cmd = PropertyChangeCommand([s.entity for s in sprites], SpriteRenderer, "image_path", old_paths, path_edit.text())
                mw.undo_manager.push(cmd)
            
        path_edit.editingFinished.connect(on_path_edit)
        
        browse_btn = QPushButton("Browse Image...")
        browse_btn.clicked.connect(lambda: self.browse_image(sprites, path_edit, w_spin, h_spin))
        
        path_layout.addWidget(path_edit)
        path_layout.addWidget(browse_btn)

        form.addRow("Image", path_layout)
        form.addRow("Width", w_spin)
        form.addRow("Height", h_spin)
        
        self._add_component_section("SpriteRenderer", SpriteRenderer, len(sprites), group)

    def browse_image(self, sprites, line_edit, w_spin=None, h_spin=None):
        start_dir = self._project_base_dir()
             
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", start_dir, "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            final_path = self._to_project_relative_path(file_path)

            self.update_sprites_image(sprites, final_path, w_spin, h_spin)
            line_edit.setText(final_path)
            line_edit.setStyleSheet("")

    def update_sprites_image(self, sprites, path, w_spin=None, h_spin=None):
        # Resolve path
        load_path = path
        if not os.path.isabs(path) and self.parent() and hasattr(self.parent(), 'project_path') and self.parent().project_path:
            full_path = os.path.join(self.parent().project_path, path)
            if os.path.exists(full_path):
                load_path = full_path
                
        for sprite in sprites:
            if hasattr(sprite, 'load_image'):
                sprite.load_image(load_path)
            elif hasattr(sprite, 'image'): # For ImageRenderer
                 if os.path.exists(load_path):
                      sprite.image = pygame.image.load(load_path)
                      sprite.width = float(sprite.image.get_width())
                      sprite.height = float(sprite.image.get_height())
                 
            if path != load_path:
                sprite.image_path = path # Restore relative path
            
        # Update width/height spins (using first sprite's new dimensions)
        if w_spin:
            w_spin.setValue(sprites[0].width)
            w_spin.setStyleSheet("")
        if h_spin:
            h_spin.setValue(sprites[0].height)
            h_spin.setStyleSheet("")

    def add_script_ui(self, scripts):
        if not isinstance(scripts, list):
            scripts = [scripts]
            
        group = QWidget()
        form = QFormLayout(group)
        
        first = scripts[0]
        
        # Path input with browse button
        path_layout = QHBoxLayout()
        path_edit = UndoableLineEdit(first.script_path)
        path_edit.setPlaceholderText("Path to script .py")
        
        # Add open script button
        open_btn = QPushButton()
        open_btn.setIcon(qta.icon("fa5s.edit", color=theme_icon_color()))
        open_btn.setToolTip("Open script in editor")
        open_btn.setMaximumWidth(30)
        
        # Add browse/change script button
        browse_btn = QPushButton()
        browse_btn.setIcon(qta.icon("fa5s.folder-open", color=theme_icon_color()))
        browse_btn.setToolTip("Change or create script")
        browse_btn.setMaximumWidth(30)
        
        def open_script_in_editor():
            if first.script_path:
                # Find the main window and call open_script
                parent = self
                while parent and not hasattr(parent, 'open_script'):
                    parent = parent.parent()
                if parent:
                    # Convert relative path to absolute if needed
                    if not os.path.isabs(first.script_path):
                        base_path = os.getcwd()
                        if hasattr(parent, 'project_path') and parent.project_path:
                            base_path = parent.project_path
                        script_path = os.path.join(base_path, first.script_path)
                    else:
                        script_path = first.script_path
                    
                    # If file doesn't exist, create it with a basic template
                    if not os.path.exists(script_path):
                        os.makedirs(os.path.dirname(script_path), exist_ok=True)
                        template = f"""from core.components.script import ScriptComponent

class {first.class_name}:
    def on_start(self):
        # Called once when the script starts
        pass
    
    def on_update(self, dt: float):
        # Called every frame
        pass
"""
                        with open(script_path, "w") as f:
                            f.write(template)
                    
                    parent.open_script(script_path)
        
        def browse_script():
            # Find the main window to get project path
            parent = self
            while parent and not hasattr(parent, 'project_path'):
                parent = parent.parent()
            
            start_dir = os.getcwd()
            if parent and hasattr(parent, 'project_path') and parent.project_path:
                start_dir = parent.project_path
            
            # Create menu with options
            menu = QMenu(self)
            select_action = menu.addAction(qta.icon("fa5s.file", color=theme_icon_color()), "Select Existing Script")
            create_action = menu.addAction(qta.icon("fa5s.plus", color=theme_icon_color()), "Create New Script")
            
            # Show menu at button position
            action = menu.exec_(browse_btn.mapToGlobal(browse_btn.rect().bottomLeft()))
            
            if action == select_action:
                # Select existing script
                file_path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Script File", 
                    start_dir,
                    "Python Files (*.py);;All Files (*)"
                )
                
                if file_path:
                    # Convert to relative path if possible
                    try:
                        if parent and hasattr(parent, 'project_path') and parent.project_path:
                            rel_path = os.path.relpath(file_path, parent.project_path)
                            if not rel_path.startswith('..'):
                                file_path = rel_path
                    except:
                        pass
                    
                    # Detect class name from file
                    class_name = self._detect_script_class_name(file_path)
                    
                    # Update all selected script components
                    for s in scripts:
                        s.script_path = file_path
                        s.class_name = class_name
                    
                    # Update the UI
                    path_edit.setText(file_path)
                    # Refresh the inspector to show new class name
                    self.set_entities(self.current_entities)
            
            elif action == create_action:
                # Create new script
                entity = self.current_entities[0] if self.current_entities else None
                default_name = "".join(x for x in entity.name if x.isalnum()) if entity else "NewScript"
                default_name = default_name[0].upper() + default_name[1:]
                
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Create New Script",
                    os.path.join(start_dir, "scripts", f"{default_name}.py"),
                    "Python Files (*.py);;All Files (*)"
                )
                
                if file_path:
                    # Ensure .py extension
                    if not file_path.endswith('.py'):
                        file_path += '.py'
                    
                    # Get class name from filename
                    class_name = os.path.basename(file_path).replace('.py', '')
                    class_name = "".join(x for x in class_name if x.isalnum() or x == '_')
                    if not class_name[0].isalpha():
                        class_name = "Script" + class_name
                    
                    # Create script with template
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    template = f"""from core.components.script import ScriptComponent
from core.input import Input
from core.components import Transform
import pygame

class {class_name}:
    def on_start(self):
        # Called once when the script starts
        print("{class_name} started on " + self.entity.name)

    def on_update(self, dt: float):
        # Called every frame
        pass
        
    
"""
                    with open(file_path, "w") as f:
                        f.write(template)
                    
                    # Convert to relative path if possible
                    try:
                        if parent and hasattr(parent, 'project_path') and parent.project_path:
                            rel_path = os.path.relpath(file_path, parent.project_path)
                            if not rel_path.startswith('..'):
                                file_path = rel_path
                    except:
                        pass
                    
                    # Update all selected script components
                    for s in scripts:
                        s.script_path = file_path
                        s.class_name = class_name
                    
                    # Update the UI
                    path_edit.setText(file_path)
                    # Refresh the inspector to show new class name
                    self.set_entities(self.current_entities)
                    
                    # Open the new script in editor
                    if parent and hasattr(parent, 'open_script'):
                        if not os.path.isabs(file_path):
                            script_path = os.path.join(parent.project_path or os.getcwd(), file_path)
                        else:
                            script_path = file_path
                        parent.open_script(script_path)
        
        open_btn.clicked.connect(open_script_in_editor)
        browse_btn.clicked.connect(browse_script)
        
        path_layout.addWidget(path_edit)
        path_layout.addWidget(open_btn)
        path_layout.addWidget(browse_btn)
        
        # Capture old values
        old_paths = []
        def on_focus():
            nonlocal old_paths
            old_paths = [s.script_path for s in scripts]
        path_edit.focused.connect(on_focus)
        
        # Check mixed
        paths = [s.script_path for s in scripts]
        if any(p != paths[0] for p in paths):
             path_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
             path_edit.setToolTip("Mixed script paths")
        
        def update_path(text):
            path_edit.setStyleSheet("")
            for s in scripts:
                s.script_path = text
                
        path_edit.textChanged.connect(update_path)
        
        def on_commit():
             mw = path_edit.window()
             if hasattr(mw, 'undo_manager') and old_paths:
                 cmd = PropertyChangeCommand([s.entity for s in scripts], ScriptComponent, "script_path", old_paths, path_edit.text())
                 mw.undo_manager.push(cmd)
        path_edit.editingFinished.connect(on_commit)
        
        form.addRow("Script Path", path_layout)
        form.addRow("Class Name", QLabel(first.class_name))
        
        self._add_component_section("ScriptComponent", ScriptComponent, len(scripts), group)

    def add_sound_ui(self, sounds):
        if not isinstance(sounds, list):
            sounds = [sounds]
            
        group = QWidget()
        form = QFormLayout(group)
        
        # File Path
        path_layout = QVBoxLayout()
        paths = [s.file_path for s in sounds]
        first_path = paths[0]
        mixed_paths = any(p != first_path for p in paths)
        
        path_edit = UndoableLineEdit(first_path)
        path_edit.setPlaceholderText("Path to audio file")
        
        old_paths = []
        def on_path_focus():
            nonlocal old_paths
            old_paths = [s.file_path for s in sounds]
        path_edit.focused.connect(on_path_focus)
        
        if mixed_paths:
            path_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
            path_edit.setToolTip("Mixed audio paths")
            
        def on_path_edit():
            path_edit.setStyleSheet("")
            new_path = path_edit.text()
            for s in sounds:
                s.file_path = new_path
                
            mw = path_edit.window()
            if hasattr(mw, 'undo_manager') and old_paths:
                cmd = PropertyChangeCommand([s.entity for s in sounds], SoundComponent, "file_path", old_paths, new_path)
                mw.undo_manager.push(cmd)
        
        path_edit.editingFinished.connect(on_path_edit)
        
        browse_btn = QPushButton("Browse Audio...")
        
        def browse_audio():
            start_dir = self._project_base_dir()
                 
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Audio", start_dir, "Audio Files (*.wav *.mp3 *.ogg)")
            if file_path:
                final_path = self._to_project_relative_path(file_path)
                
                path_edit.setText(final_path)
                on_path_edit() # Trigger update
        
        browse_btn.clicked.connect(browse_audio)
        
        path_layout.addWidget(path_edit)
        path_layout.addWidget(browse_btn)
        form.addRow("Audio File", path_layout)

        # Volume
        vol_vals = [s.volume for s in sounds]
        vol_spin = UndoableDoubleSpinBox()
        vol_spin.setRange(0.0, 1.0)
        vol_spin.setSingleStep(0.1)
        
        first_vol = vol_vals[0]
        mixed_vol = any(abs(v - first_vol) > 0.0001 for v in vol_vals)
        
        old_vols = []
        def on_vol_focus():
            nonlocal old_vols
            old_vols = [s.volume for s in sounds]
        vol_spin.focused.connect(on_vol_focus)
        
        if mixed_vol:
            vol_spin.setValue(first_vol)
            vol_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
        else:
            vol_spin.setValue(first_vol)
            
        def on_vol_change(val):
            vol_spin.setStyleSheet("")
            for s in sounds:
                s.set_volume(val)
        
        vol_spin.valueChanged.connect(on_vol_change)
        
        def on_vol_commit():
            mw = vol_spin.window()
            if hasattr(mw, 'undo_manager') and old_vols:
                cmd = PropertyChangeCommand([s.entity for s in sounds], SoundComponent, "volume", old_vols, vol_spin.value())
                mw.undo_manager.push(cmd)
        vol_spin.editingFinished.connect(on_vol_commit)
        
        form.addRow("Volume", vol_spin)

        def create_float_spin(attr, label, min_val, max_val, step=1.0):
            values = [float(getattr(s, attr)) for s in sounds]
            spin = UndoableDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setSingleStep(step)

            first = values[0]
            mixed = any(abs(v - first) > 0.0001 for v in values)
            old_values = []

            def on_focus():
                nonlocal old_values
                old_values = [float(getattr(s, attr)) for s in sounds]

            spin.focused.connect(on_focus)

            spin.setValue(first)
            if mixed:
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

            def on_change(val):
                spin.setStyleSheet("")
                for s in sounds:
                    setattr(s, attr, float(val))
                if attr == "min_distance":
                    for s in sounds:
                        if s.max_distance < s.min_distance:
                            s.max_distance = s.min_distance
                elif attr == "max_distance":
                    for s in sounds:
                        if s.max_distance < s.min_distance:
                            s.min_distance = s.max_distance
                spin.blockSignals(True)
                spin.setValue(float(getattr(sounds[0], attr)))
                spin.blockSignals(False)

            spin.valueChanged.connect(on_change)

            def on_commit():
                mw = spin.window()
                if hasattr(mw, 'undo_manager') and old_values:
                    cmd = PropertyChangeCommand(
                        [s.entity for s in sounds],
                        SoundComponent,
                        attr,
                        old_values,
                        float(getattr(sounds[0], attr))
                    )
                    mw.undo_manager.push(cmd)

            spin.editingFinished.connect(on_commit)
            form.addRow(label, spin)
        
        # Checkboxes helper
        def create_checkbox(attr, label):
            vals = [getattr(s, attr) for s in sounds]
            chk = QCheckBox()
            
            first_val = vals[0]
            mixed = any(v != first_val for v in vals)
            
            if mixed:
                chk.setTristate(True)
                chk.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                chk.setChecked(first_val)
            
            # Capture old values for undo is tricky with closures if not careful, 
            # but here we create function per call so it's fine.
            
            def on_chk_change(state):
                is_checked = (state == Qt.CheckState.Checked.value or state == 2)
                chk.setTristate(False)
                
                old_vals = [getattr(s, attr) for s in sounds]
                for s in sounds:
                    setattr(s, attr, is_checked)
                    
                mw = chk.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = PropertyChangeCommand([s.entity for s in sounds], SoundComponent, attr, old_vals, is_checked)
                    mw.undo_manager.push(cmd)
            
            chk.stateChanged.connect(on_chk_change)
            form.addRow(label, chk)
            
        create_checkbox("loop", "Loop")
        create_checkbox("is_music", "Is Music (Stream)")
        create_checkbox("autoplay", "Autoplay")
        create_checkbox("spatialize", "Spatialize")
        create_float_spin("min_distance", "Min Distance", 0.0, 1000000.0, 10.0)
        create_float_spin("max_distance", "Max Distance", 0.0, 1000000.0, 10.0)
        create_float_spin("pan_distance", "Pan Distance", 0.0001, 1000000.0, 10.0)
        
        self._add_component_section("SoundComponent", SoundComponent, len(sounds), group)

    def add_websocket_ui(self, websockets_list):
        if not isinstance(websockets_list, list):
            websockets_list = [websockets_list]

        group = QWidget()
        form = QFormLayout(group)

        # Mode combo
        modes = ["client", "server"]
        mode_vals = [ws.mode for ws in websockets_list]
        mode_combo = QComboBox()
        mode_combo.addItems(modes)

        first_mode = mode_vals[0]
        mixed_mode = any(m != first_mode for m in mode_vals)
        if not mixed_mode:
            mode_combo.setCurrentText(first_mode)
        else:
            mode_combo.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_mode_change(text):
            mode_combo.setStyleSheet("")
            old_vals = [ws.mode for ws in websockets_list]
            for ws in websockets_list:
                ws.mode = text
            mw = mode_combo.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([ws.entity for ws in websockets_list], WebSocketComponent, "mode", old_vals, text)
                mw.undo_manager.push(cmd)
        mode_combo.currentTextChanged.connect(on_mode_change)
        form.addRow("Mode", mode_combo)

        # Host
        host_vals = [ws.host for ws in websockets_list]
        host_edit = UndoableLineEdit()
        first_host = host_vals[0]
        mixed_host = any(h != first_host for h in host_vals)
        host_edit.setText(first_host)
        if mixed_host:
            host_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_hosts = []
        def on_host_focus():
            nonlocal old_hosts
            old_hosts = [ws.host for ws in websockets_list]
        host_edit.focused.connect(on_host_focus)

        def on_host_edit():
            host_edit.setStyleSheet("")
            new_host = host_edit.text()
            for ws in websockets_list:
                ws.host = new_host
            mw = host_edit.window()
            if hasattr(mw, 'undo_manager') and old_hosts:
                cmd = PropertyChangeCommand([ws.entity for ws in websockets_list], WebSocketComponent, "host", old_hosts, new_host)
                mw.undo_manager.push(cmd)
        host_edit.editingFinished.connect(on_host_edit)
        form.addRow("Host", host_edit)

        # Port
        port_vals = [ws.port for ws in websockets_list]
        port_spin = QSpinBox()
        port_spin.setRange(1, 65535)
        first_port = port_vals[0]
        mixed_port = any(p != first_port for p in port_vals)
        port_spin.setValue(first_port)
        if mixed_port:
            port_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_port_change(val):
            port_spin.setStyleSheet("")
            old_vals = [ws.port for ws in websockets_list]
            for ws in websockets_list:
                ws.port = val
            mw = port_spin.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([ws.entity for ws in websockets_list], WebSocketComponent, "port", old_vals, val)
                mw.undo_manager.push(cmd)
        port_spin.valueChanged.connect(on_port_change)
        form.addRow("Port", port_spin)

        # URL (for client mode)
        url_vals = [ws.url for ws in websockets_list]
        url_edit = UndoableLineEdit()
        first_url = url_vals[0]
        mixed_url = any(u != first_url for u in url_vals)
        url_edit.setText(first_url)
        url_edit.setPlaceholderText("ws://host:port (optional, overrides host/port)")
        if mixed_url:
            url_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_urls = []
        def on_url_focus():
            nonlocal old_urls
            old_urls = [ws.url for ws in websockets_list]
        url_edit.focused.connect(on_url_focus)

        def on_url_edit():
            url_edit.setStyleSheet("")
            new_url = url_edit.text()
            for ws in websockets_list:
                ws.url = new_url
            mw = url_edit.window()
            if hasattr(mw, 'undo_manager') and old_urls:
                cmd = PropertyChangeCommand([ws.entity for ws in websockets_list], WebSocketComponent, "url", old_urls, new_url)
                mw.undo_manager.push(cmd)
        url_edit.editingFinished.connect(on_url_edit)
        form.addRow("URL", url_edit)

        # Autostart checkbox
        autostart_vals = [ws.autostart for ws in websockets_list]
        autostart_chk = QCheckBox()
        first_auto = autostart_vals[0]
        mixed_auto = any(a != first_auto for a in autostart_vals)
        if mixed_auto:
            autostart_chk.setTristate(True)
            autostart_chk.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            autostart_chk.setChecked(first_auto)

        def on_autostart_change(state):
            is_checked = (state == Qt.CheckState.Checked.value or state == 2)
            autostart_chk.setTristate(False)
            old_vals = [ws.autostart for ws in websockets_list]
            for ws in websockets_list:
                ws.autostart = is_checked
            mw = autostart_chk.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([ws.entity for ws in websockets_list], WebSocketComponent, "autostart", old_vals, is_checked)
                mw.undo_manager.push(cmd)
        autostart_chk.stateChanged.connect(on_autostart_change)
        form.addRow("Autostart", autostart_chk)

        # Max Queue Size
        queue_vals = [ws.max_queue_size for ws in websockets_list]
        queue_spin = QSpinBox()
        queue_spin.setRange(1, 100000)
        first_queue = queue_vals[0]
        mixed_queue = any(q != first_queue for q in queue_vals)
        queue_spin.setValue(first_queue)
        if mixed_queue:
            queue_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_queue_change(val):
            queue_spin.setStyleSheet("")
            old_vals = [ws.max_queue_size for ws in websockets_list]
            for ws in websockets_list:
                ws.max_queue_size = val
            mw = queue_spin.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([ws.entity for ws in websockets_list], WebSocketComponent, "max_queue_size", old_vals, val)
                mw.undo_manager.push(cmd)
        queue_spin.valueChanged.connect(on_queue_change)
        form.addRow("Max Queue Size", queue_spin)

        self._add_component_section("WebSocketComponent", WebSocketComponent, len(websockets_list), group)

    def add_http_client_ui(self, clients):
        if not isinstance(clients, list):
            clients = [clients]

        group = QWidget()
        form = QFormLayout(group)

        # Base URL
        url_vals = [c.base_url for c in clients]
        url_edit = UndoableLineEdit()
        first_url = url_vals[0]
        url_edit.setText(first_url)
        url_edit.setPlaceholderText("https://api.example.com")
        if any(u != first_url for u in url_vals):
            url_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_urls = []
        def on_url_focus():
            nonlocal old_urls
            old_urls = [c.base_url for c in clients]
        url_edit.focused.connect(on_url_focus)

        def on_url_edit():
            url_edit.setStyleSheet("")
            new_url = url_edit.text()
            for c in clients:
                c.base_url = new_url
            mw = url_edit.window()
            if hasattr(mw, 'undo_manager') and old_urls:
                cmd = PropertyChangeCommand([c.entity for c in clients], HTTPClientComponent, "base_url", old_urls, new_url)
                mw.undo_manager.push(cmd)
        url_edit.editingFinished.connect(on_url_edit)
        form.addRow("Base URL", url_edit)

        # Timeout
        timeout_vals = [c.timeout for c in clients]
        timeout_spin = UndoableDoubleSpinBox()
        timeout_spin.setRange(1.0, 300.0)
        timeout_spin.setSingleStep(1.0)
        timeout_spin.setDecimals(1)
        first_timeout = timeout_vals[0]
        timeout_spin.setValue(first_timeout)
        if any(abs(t - first_timeout) > 0.01 for t in timeout_vals):
            timeout_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_timeout_change(val):
            timeout_spin.setStyleSheet("")
            for c in clients:
                c.timeout = val
        timeout_spin.valueChanged.connect(on_timeout_change)
        form.addRow("Timeout (s)", timeout_spin)

        # Max Concurrent
        conc_vals = [c.max_concurrent for c in clients]
        conc_spin = QSpinBox()
        conc_spin.setRange(1, 32)
        first_conc = conc_vals[0]
        conc_spin.setValue(first_conc)
        if any(v != first_conc for v in conc_vals):
            conc_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_conc_change(val):
            conc_spin.setStyleSheet("")
            for c in clients:
                c.max_concurrent = val
        conc_spin.valueChanged.connect(on_conc_change)
        form.addRow("Max Concurrent", conc_spin)

        self._add_component_section("HTTPClientComponent", HTTPClientComponent, len(clients), group)

    def add_http_request_ui(self, requests_list):
        if not isinstance(requests_list, list):
            requests_list = [requests_list]

        group = QWidget()
        form = QFormLayout(group)

        # URL
        url_vals = [r.url for r in requests_list]
        url_edit = UndoableLineEdit()
        first_url = url_vals[0]
        url_edit.setText(first_url)
        url_edit.setPlaceholderText("https://api.example.com/endpoint")
        if any(u != first_url for u in url_vals):
            url_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_urls = []
        def on_url_focus():
            nonlocal old_urls
            old_urls = [r.url for r in requests_list]
        url_edit.focused.connect(on_url_focus)

        def on_url_edit():
            url_edit.setStyleSheet("")
            new_url = url_edit.text()
            for r in requests_list:
                r.url = new_url
            mw = url_edit.window()
            if hasattr(mw, 'undo_manager') and old_urls:
                cmd = PropertyChangeCommand([r.entity for r in requests_list], HTTPRequestComponent, "url", old_urls, new_url)
                mw.undo_manager.push(cmd)
        url_edit.editingFinished.connect(on_url_edit)
        form.addRow("URL", url_edit)

        # Method combo
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        method_vals = [r.method for r in requests_list]
        method_combo = QComboBox()
        method_combo.addItems(methods)
        first_method = method_vals[0]
        if any(m != first_method for m in method_vals):
            method_combo.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
        else:
            method_combo.setCurrentText(first_method)

        def on_method_change(text):
            method_combo.setStyleSheet("")
            old_vals = [r.method for r in requests_list]
            for r in requests_list:
                r.method = text
            mw = method_combo.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([r.entity for r in requests_list], HTTPRequestComponent, "method", old_vals, text)
                mw.undo_manager.push(cmd)
        method_combo.currentTextChanged.connect(on_method_change)
        form.addRow("Method", method_combo)

        # Request Body
        body_vals = [r.request_body for r in requests_list]
        body_edit = UndoableLineEdit()
        first_body = body_vals[0]
        body_edit.setText(first_body)
        body_edit.setPlaceholderText('{"key": "value"}')
        if any(b != first_body for b in body_vals):
            body_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_bodies = []
        def on_body_focus():
            nonlocal old_bodies
            old_bodies = [r.request_body for r in requests_list]
        body_edit.focused.connect(on_body_focus)

        def on_body_edit():
            body_edit.setStyleSheet("")
            new_body = body_edit.text()
            for r in requests_list:
                r.request_body = new_body
            mw = body_edit.window()
            if hasattr(mw, 'undo_manager') and old_bodies:
                cmd = PropertyChangeCommand([r.entity for r in requests_list], HTTPRequestComponent, "request_body", old_bodies, new_body)
                mw.undo_manager.push(cmd)
        body_edit.editingFinished.connect(on_body_edit)
        form.addRow("Request Body", body_edit)

        # Content Type
        ct_vals = [r.content_type for r in requests_list]
        ct_edit = UndoableLineEdit()
        first_ct = ct_vals[0]
        ct_edit.setText(first_ct)
        if any(c != first_ct for c in ct_vals):
            ct_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_cts = []
        def on_ct_focus():
            nonlocal old_cts
            old_cts = [r.content_type for r in requests_list]
        ct_edit.focused.connect(on_ct_focus)

        def on_ct_edit():
            ct_edit.setStyleSheet("")
            new_ct = ct_edit.text()
            for r in requests_list:
                r.content_type = new_ct
            mw = ct_edit.window()
            if hasattr(mw, 'undo_manager') and old_cts:
                cmd = PropertyChangeCommand([r.entity for r in requests_list], HTTPRequestComponent, "content_type", old_cts, new_ct)
                mw.undo_manager.push(cmd)
        ct_edit.editingFinished.connect(on_ct_edit)
        form.addRow("Content Type", ct_edit)

        # Timeout
        timeout_vals = [r.timeout for r in requests_list]
        timeout_spin = UndoableDoubleSpinBox()
        timeout_spin.setRange(1.0, 300.0)
        timeout_spin.setSingleStep(1.0)
        timeout_spin.setDecimals(1)
        first_timeout = timeout_vals[0]
        timeout_spin.setValue(first_timeout)
        if any(abs(t - first_timeout) > 0.01 for t in timeout_vals):
            timeout_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_timeout_change(val):
            timeout_spin.setStyleSheet("")
            for r in requests_list:
                r.timeout = val
        timeout_spin.valueChanged.connect(on_timeout_change)
        form.addRow("Timeout (s)", timeout_spin)

        # Send on Start checkbox
        sos_vals = [r.send_on_start for r in requests_list]
        sos_chk = QCheckBox()
        first_sos = sos_vals[0]
        mixed_sos = any(s != first_sos for s in sos_vals)
        if mixed_sos:
            sos_chk.setTristate(True)
            sos_chk.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            sos_chk.setChecked(first_sos)

        def on_sos_change(state):
            is_checked = (state == Qt.CheckState.Checked.value or state == 2)
            sos_chk.setTristate(False)
            old_vals = [r.send_on_start for r in requests_list]
            for r in requests_list:
                r.send_on_start = is_checked
            mw = sos_chk.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([r.entity for r in requests_list], HTTPRequestComponent, "send_on_start", old_vals, is_checked)
                mw.undo_manager.push(cmd)
        sos_chk.stateChanged.connect(on_sos_change)
        form.addRow("Send on Start", sos_chk)

        self._add_component_section("HTTPRequestComponent", HTTPRequestComponent, len(requests_list), group)

    def add_webview_ui(self, webviews):
        if not isinstance(webviews, list):
            webviews = [webviews]

        group = QWidget()
        form = QFormLayout(group)

        # URL
        url_vals = [wv.url for wv in webviews]
        url_edit = UndoableLineEdit()
        first_url = url_vals[0]
        url_edit.setText(first_url)
        url_edit.setPlaceholderText("https://example.com")
        if any(u != first_url for u in url_vals):
            url_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_urls = []
        def on_url_focus():
            nonlocal old_urls
            old_urls = [wv.url for wv in webviews]
        url_edit.focused.connect(on_url_focus)

        def on_url_edit():
            url_edit.setStyleSheet("")
            new_url = url_edit.text()
            for wv in webviews:
                wv.url = new_url
            mw = url_edit.window()
            if hasattr(mw, 'undo_manager') and old_urls:
                cmd = PropertyChangeCommand([wv.entity for wv in webviews], WebviewComponent, "url", old_urls, new_url)
                mw.undo_manager.push(cmd)
        url_edit.editingFinished.connect(on_url_edit)
        form.addRow("URL", url_edit)

        # Title
        title_vals = [wv.title for wv in webviews]
        title_edit = UndoableLineEdit()
        first_title = title_vals[0]
        title_edit.setText(first_title)
        if any(t != first_title for t in title_vals):
            title_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_titles = []
        def on_title_focus():
            nonlocal old_titles
            old_titles = [wv.title for wv in webviews]
        title_edit.focused.connect(on_title_focus)

        def on_title_edit():
            title_edit.setStyleSheet("")
            new_title = title_edit.text()
            for wv in webviews:
                wv.title = new_title
            mw = title_edit.window()
            if hasattr(mw, 'undo_manager') and old_titles:
                cmd = PropertyChangeCommand([wv.entity for wv in webviews], WebviewComponent, "title", old_titles, new_title)
                mw.undo_manager.push(cmd)
        title_edit.editingFinished.connect(on_title_edit)
        form.addRow("Title", title_edit)

        # Width
        width_vals = [wv.width for wv in webviews]
        width_spin = QSpinBox()
        width_spin.setRange(100, 4096)
        first_w = width_vals[0]
        width_spin.setValue(first_w)
        if any(w != first_w for w in width_vals):
            width_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_width_change(val):
            width_spin.setStyleSheet("")
            for wv in webviews:
                wv.width = val
        width_spin.valueChanged.connect(on_width_change)
        form.addRow("Width", width_spin)

        # Height
        height_vals = [wv.height for wv in webviews]
        height_spin = QSpinBox()
        height_spin.setRange(100, 4096)
        first_h = height_vals[0]
        height_spin.setValue(first_h)
        if any(h != first_h for h in height_vals):
            height_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_height_change(val):
            height_spin.setStyleSheet("")
            for wv in webviews:
                wv.height = val
        height_spin.valueChanged.connect(on_height_change)
        form.addRow("Height", height_spin)

        # Checkboxes
        def create_checkbox(attr, label):
            vals = [getattr(wv, attr) for wv in webviews]
            chk = QCheckBox()
            first_val = vals[0]
            mixed = any(v != first_val for v in vals)
            if mixed:
                chk.setTristate(True)
                chk.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                chk.setChecked(first_val)

            def on_chk_change(state):
                is_checked = (state == Qt.CheckState.Checked.value or state == 2)
                chk.setTristate(False)
                old_vals = [getattr(wv, attr) for wv in webviews]
                for wv in webviews:
                    setattr(wv, attr, is_checked)
                mw = chk.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = PropertyChangeCommand([wv.entity for wv in webviews], WebviewComponent, attr, old_vals, is_checked)
                    mw.undo_manager.push(cmd)
            chk.stateChanged.connect(on_chk_change)
            form.addRow(label, chk)

        create_checkbox("resizable", "Resizable")
        create_checkbox("frameless", "Frameless")
        create_checkbox("autoopen", "Auto Open")

        self._add_component_section("WebviewComponent", WebviewComponent, len(webviews), group)

    def add_webrtc_ui(self, rtc_list):
        if not isinstance(rtc_list, list):
            rtc_list = [rtc_list]

        group = QWidget()
        form = QFormLayout(group)

        # ICE Servers
        ice_vals = [r.ice_servers for r in rtc_list]
        ice_edit = UndoableLineEdit()
        first_ice = ice_vals[0]
        ice_edit.setText(first_ice)
        ice_edit.setPlaceholderText("stun:stun.l.google.com:19302")
        if any(v != first_ice for v in ice_vals):
            ice_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_ices = []
        def on_ice_focus():
            nonlocal old_ices
            old_ices = [r.ice_servers for r in rtc_list]
        ice_edit.focused.connect(on_ice_focus)

        def on_ice_edit():
            ice_edit.setStyleSheet("")
            new_val = ice_edit.text()
            for r in rtc_list:
                r.ice_servers = new_val
            mw = ice_edit.window()
            if hasattr(mw, 'undo_manager') and old_ices:
                cmd = PropertyChangeCommand([r.entity for r in rtc_list], WebRTCComponent, "ice_servers", old_ices, new_val)
                mw.undo_manager.push(cmd)
        ice_edit.editingFinished.connect(on_ice_edit)
        form.addRow("ICE Servers", ice_edit)

        # Data Channel Label
        label_vals = [r.data_channel_label for r in rtc_list]
        label_edit = UndoableLineEdit()
        first_label = label_vals[0]
        label_edit.setText(first_label)
        if any(v != first_label for v in label_vals):
            label_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_labels = []
        def on_label_focus():
            nonlocal old_labels
            old_labels = [r.data_channel_label for r in rtc_list]
        label_edit.focused.connect(on_label_focus)

        def on_label_edit():
            label_edit.setStyleSheet("")
            new_val = label_edit.text()
            for r in rtc_list:
                r.data_channel_label = new_val
            mw = label_edit.window()
            if hasattr(mw, 'undo_manager') and old_labels:
                cmd = PropertyChangeCommand([r.entity for r in rtc_list], WebRTCComponent, "data_channel_label", old_labels, new_val)
                mw.undo_manager.push(cmd)
        label_edit.editingFinished.connect(on_label_edit)
        form.addRow("Channel Label", label_edit)

        # Max Retransmits
        retrans_vals = [r.max_retransmits for r in rtc_list]
        retrans_spin = QSpinBox()
        retrans_spin.setRange(-1, 65535)
        retrans_spin.setSpecialValueText("Unlimited (-1)")
        first_retrans = retrans_vals[0]
        retrans_spin.setValue(first_retrans)
        if any(v != first_retrans for v in retrans_vals):
            retrans_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_retrans_change(val):
            retrans_spin.setStyleSheet("")
            old_vals = [r.max_retransmits for r in rtc_list]
            for r in rtc_list:
                r.max_retransmits = val
            mw = retrans_spin.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([r.entity for r in rtc_list], WebRTCComponent, "max_retransmits", old_vals, val)
                mw.undo_manager.push(cmd)
        retrans_spin.valueChanged.connect(on_retrans_change)
        form.addRow("Max Retransmits", retrans_spin)

        # Max Queue Size
        queue_vals = [r.max_queue_size for r in rtc_list]
        queue_spin = QSpinBox()
        queue_spin.setRange(1, 100000)
        first_queue = queue_vals[0]
        queue_spin.setValue(first_queue)
        if any(v != first_queue for v in queue_vals):
            queue_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_queue_change(val):
            queue_spin.setStyleSheet("")
            old_vals = [r.max_queue_size for r in rtc_list]
            for r in rtc_list:
                r.max_queue_size = val
            mw = queue_spin.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([r.entity for r in rtc_list], WebRTCComponent, "max_queue_size", old_vals, val)
                mw.undo_manager.push(cmd)
        queue_spin.valueChanged.connect(on_queue_change)
        form.addRow("Max Queue Size", queue_spin)

        # Checkboxes
        def create_checkbox(attr, label):
            vals = [getattr(r, attr) for r in rtc_list]
            chk = QCheckBox()
            first_val = vals[0]
            mixed = any(v != first_val for v in vals)
            if mixed:
                chk.setTristate(True)
                chk.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                chk.setChecked(first_val)

            def on_chk_change(state):
                is_checked = (state == Qt.CheckState.Checked.value or state == 2)
                chk.setTristate(False)
                old_vals = [getattr(r, attr) for r in rtc_list]
                for r in rtc_list:
                    setattr(r, attr, is_checked)
                mw = chk.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = PropertyChangeCommand([r.entity for r in rtc_list], WebRTCComponent, attr, old_vals, is_checked)
                    mw.undo_manager.push(cmd)
            chk.stateChanged.connect(on_chk_change)
            form.addRow(label, chk)

        create_checkbox("ordered", "Ordered")
        create_checkbox("autostart", "Autostart")

        self._add_component_section("WebRTCComponent", WebRTCComponent, len(rtc_list), group)

    def add_multiplayer_ui(self, mp_list):
        if not isinstance(mp_list, list):
            mp_list = [mp_list]

        group = QWidget()
        form = QFormLayout(group)

        # Player Name
        name_vals = [m.player_name for m in mp_list]
        name_edit = UndoableLineEdit()
        first_name = name_vals[0]
        name_edit.setText(first_name)
        name_edit.setPlaceholderText("Player")
        if any(v != first_name for v in name_vals):
            name_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_names = []
        def on_name_focus():
            nonlocal old_names
            old_names = [m.player_name for m in mp_list]
        name_edit.focused.connect(on_name_focus)

        def on_name_edit():
            name_edit.setStyleSheet("")
            new_val = name_edit.text()
            for m in mp_list:
                m.player_name = new_val
            mw = name_edit.window()
            if hasattr(mw, 'undo_manager') and old_names:
                cmd = PropertyChangeCommand([m.entity for m in mp_list], MultiplayerComponent, "player_name", old_names, new_val)
                mw.undo_manager.push(cmd)
        name_edit.editingFinished.connect(on_name_edit)
        form.addRow("Player Name", name_edit)

        # Max Players
        max_vals = [m.max_players for m in mp_list]
        max_spin = QSpinBox()
        max_spin.setRange(2, 64)
        first_max = max_vals[0]
        max_spin.setValue(first_max)
        if any(v != first_max for v in max_vals):
            max_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_max_change(val):
            max_spin.setStyleSheet("")
            for m in mp_list:
                m.max_players = val
        max_spin.valueChanged.connect(on_max_change)
        form.addRow("Max Players", max_spin)

        # Sync Rate
        sync_vals = [m.sync_rate for m in mp_list]
        sync_spin = UndoableDoubleSpinBox()
        sync_spin.setRange(1.0, 120.0)
        sync_spin.setSingleStep(1.0)
        sync_spin.setDecimals(1)
        first_sync = sync_vals[0]
        sync_spin.setValue(first_sync)
        if any(abs(v - first_sync) > 0.01 for v in sync_vals):
            sync_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_sync_change(val):
            sync_spin.setStyleSheet("")
            for m in mp_list:
                m.sync_rate = val
        sync_spin.valueChanged.connect(on_sync_change)
        form.addRow("Sync Rate (Hz)", sync_spin)

        # Port
        port_vals = [m.port for m in mp_list]
        port_spin = QSpinBox()
        port_spin.setRange(1, 65535)
        first_port = port_vals[0]
        port_spin.setValue(first_port)
        if any(v != first_port for v in port_vals):
            port_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_port_change(val):
            port_spin.setStyleSheet("")
            for m in mp_list:
                m.port = val
        port_spin.valueChanged.connect(on_port_change)
        form.addRow("Port", port_spin)

        self._add_component_section("MultiplayerComponent", MultiplayerComponent, len(mp_list), group)

    def add_network_identity_ui(self, nid_list):
        if not isinstance(nid_list, list):
            nid_list = [nid_list]

        group = QWidget()
        form = QFormLayout(group)

        # Network ID
        id_vals = [n.network_id for n in nid_list]
        id_edit = UndoableLineEdit()
        first_id = id_vals[0]
        id_edit.setText(first_id)
        id_edit.setPlaceholderText("Auto-assigned at runtime")
        if any(v != first_id for v in id_vals):
            id_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_ids = []
        def on_id_focus():
            nonlocal old_ids
            old_ids = [n.network_id for n in nid_list]
        id_edit.focused.connect(on_id_focus)

        def on_id_edit():
            id_edit.setStyleSheet("")
            new_val = id_edit.text()
            for n in nid_list:
                n.network_id = new_val
            mw = id_edit.window()
            if hasattr(mw, 'undo_manager') and old_ids:
                cmd = PropertyChangeCommand([n.entity for n in nid_list], NetworkIdentityComponent, "network_id", old_ids, new_val)
                mw.undo_manager.push(cmd)
        id_edit.editingFinished.connect(on_id_edit)
        form.addRow("Network ID", id_edit)

        # Owner ID
        owner_vals = [n.owner_id for n in nid_list]
        owner_edit = UndoableLineEdit()
        first_owner = owner_vals[0]
        owner_edit.setText(first_owner)
        owner_edit.setPlaceholderText("Assigned by host at runtime")
        if any(v != first_owner for v in owner_vals):
            owner_edit.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        old_owners = []
        def on_owner_focus():
            nonlocal old_owners
            old_owners = [n.owner_id for n in nid_list]
        owner_edit.focused.connect(on_owner_focus)

        def on_owner_edit():
            owner_edit.setStyleSheet("")
            new_val = owner_edit.text()
            for n in nid_list:
                n.owner_id = new_val
            mw = owner_edit.window()
            if hasattr(mw, 'undo_manager') and old_owners:
                cmd = PropertyChangeCommand([n.entity for n in nid_list], NetworkIdentityComponent, "owner_id", old_owners, new_val)
                mw.undo_manager.push(cmd)
        owner_edit.editingFinished.connect(on_owner_edit)
        form.addRow("Owner ID", owner_edit)

        # Sync Interval
        interval_vals = [n.sync_interval for n in nid_list]
        interval_spin = UndoableDoubleSpinBox()
        interval_spin.setRange(0.01, 5.0)
        interval_spin.setSingleStep(0.01)
        interval_spin.setDecimals(3)
        first_interval = interval_vals[0]
        interval_spin.setValue(first_interval)
        if any(abs(v - first_interval) > 0.001 for v in interval_vals):
            interval_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_interval_change(val):
            interval_spin.setStyleSheet("")
            for n in nid_list:
                n.sync_interval = val
        interval_spin.valueChanged.connect(on_interval_change)
        form.addRow("Sync Interval (s)", interval_spin)

        # Checkboxes
        def create_checkbox(attr, label):
            vals = [getattr(n, attr) for n in nid_list]
            chk = QCheckBox()
            first_val = vals[0]
            mixed = any(v != first_val for v in vals)
            if mixed:
                chk.setTristate(True)
                chk.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                chk.setChecked(first_val)

            def on_chk_change(state):
                is_checked = (state == Qt.CheckState.Checked.value or state == 2)
                chk.setTristate(False)
                old_vals = [getattr(n, attr) for n in nid_list]
                for n in nid_list:
                    setattr(n, attr, is_checked)
                mw = chk.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = PropertyChangeCommand([n.entity for n in nid_list], NetworkIdentityComponent, attr, old_vals, is_checked)
                    mw.undo_manager.push(cmd)
            chk.stateChanged.connect(on_chk_change)
            form.addRow(label, chk)

        create_checkbox("sync_transform", "Sync Transform")
        create_checkbox("interpolate", "Interpolate")

        self._add_component_section("NetworkIdentityComponent", NetworkIdentityComponent, len(nid_list), group)

    def add_rigidbody_ui(self, rigidbodies):
        if not isinstance(rigidbodies, list):
            rigidbodies = [rigidbodies]

        group = QWidget()
        form = QFormLayout(group)

        def create_spin(attr, min_val, max_val, step=0.1):
            values = [getattr(rb, attr) for rb in rigidbodies]
            spin = UndoableDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setSingleStep(step)

            first = values[0]
            mixed = any(abs(v - first) > 0.0001 for v in values)
            old_values = []

            def on_focus():
                nonlocal old_values
                old_values = [getattr(rb, attr) for rb in rigidbodies]

            spin.focused.connect(on_focus)

            if mixed:
                spin.setValue(first)
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
            else:
                spin.setValue(first)

            def on_change(val):
                spin.setStyleSheet("")
                for rb in rigidbodies:
                    setattr(rb, attr, val)

            spin.valueChanged.connect(on_change)

            def on_commit():
                mw = spin.window()
                if hasattr(mw, 'undo_manager') and old_values:
                    cmd = PropertyChangeCommand([rb.entity for rb in rigidbodies], Rigidbody2D, attr, old_values, spin.value())
                    mw.undo_manager.push(cmd)

            spin.editingFinished.connect(on_commit)
            return spin

        def create_checkbox(attr, label_text):
            values = [getattr(rb, attr) for rb in rigidbodies]
            chk = QCheckBox()
            first = values[0]
            mixed = any(v != first for v in values)

            if mixed:
                chk.setTristate(True)
                chk.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                chk.setChecked(first)

            def on_change(state):
                is_checked = state == Qt.CheckState.Checked.value
                chk.setTristate(False)
                old_values = [getattr(rb, attr) for rb in rigidbodies]
                for rb in rigidbodies:
                    setattr(rb, attr, is_checked)
                mw = chk.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = PropertyChangeCommand([rb.entity for rb in rigidbodies], Rigidbody2D, attr, old_values, is_checked)
                    mw.undo_manager.push(cmd)

            chk.stateChanged.connect(on_change)
            form.addRow(label_text, chk)

        def create_body_type_combo():
            values = [rb.body_type for rb in rigidbodies]
            first = values[0]
            mixed = any(v != first for v in values)
            combo = NoScrollComboBox()
            combo.addItem("Dynamic", Rigidbody2D.BODY_TYPE_DYNAMIC)
            combo.addItem("Kinematic", Rigidbody2D.BODY_TYPE_KINEMATIC)
            combo.addItem("Static", Rigidbody2D.BODY_TYPE_STATIC)
            combo.setCurrentIndex(max(0, combo.findData(first)))

            if mixed:
                combo.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

            def on_change(_index):
                combo.setStyleSheet("")
                new_value = combo.currentData()
                old_values = [rb.body_type for rb in rigidbodies]
                for rb in rigidbodies:
                    rb.body_type = new_value
                mw = combo.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = PropertyChangeCommand([rb.entity for rb in rigidbodies], Rigidbody2D, "body_type", old_values, new_value)
                    mw.undo_manager.push(cmd)

            combo.currentIndexChanged.connect(on_change)
            form.addRow("Body Type", combo)

        vx_spin = create_spin("velocity_x", -10000.0, 10000.0, 10.0)
        vy_spin = create_spin("velocity_y", -10000.0, 10000.0, 10.0)
        mass_spin = create_spin("mass", 0.0001, 100000.0, 0.1)
        angular_velocity_spin = create_spin("angular_velocity", -10000.0, 10000.0, 1.0)
        gravity_spin = create_spin("gravity_scale", -10.0, 10.0, 0.1)
        elasticity_spin = create_spin("elasticity", 0.0, 1.0, 0.05)
        friction_spin = create_spin("friction", 0.0, 5.0, 0.05)
        damping_spin = create_spin("linear_damping", 0.0, 50.0, 0.1)
        angular_damping_spin = create_spin("angular_damping", 0.0, 50.0, 0.1)

        form.addRow("Velocity X", vx_spin)
        form.addRow("Velocity Y", vy_spin)
        form.addRow("Mass", mass_spin)
        form.addRow("Angular Velocity", angular_velocity_spin)
        form.addRow("Gravity Scale", gravity_spin)
        form.addRow("Elasticity", elasticity_spin)
        form.addRow("Friction", friction_spin)
        form.addRow("Linear Damping", damping_spin)
        form.addRow("Angular Damping", angular_damping_spin)
        create_body_type_combo()
        create_checkbox("use_gravity", "Use Gravity")
        create_checkbox("freeze_rotation", "Freeze Rotation")

        self._add_component_section("Rigidbody2D", Rigidbody2D, len(rigidbodies), group)

    def add_box_collider_ui(self, colliders):
        if not isinstance(colliders, list):
            colliders = [colliders]

        group = QWidget()
        form = QFormLayout(group)

        def create_spin(attr, min_val, max_val, step=0.1):
            values = [getattr(c, attr) for c in colliders]
            normalized_values = [0.0 if v is None else v for v in values]
            spin = UndoableDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setSingleStep(step)

            first = normalized_values[0]
            mixed = any(abs(v - first) > 0.0001 for v in normalized_values)
            old_values = []

            def on_focus():
                nonlocal old_values
                old_values = [getattr(c, attr) for c in colliders]

            spin.focused.connect(on_focus)

            if mixed:
                spin.setValue(first)
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
            else:
                spin.setValue(first)

            def on_change(val):
                spin.setStyleSheet("")
                for c in colliders:
                    setattr(c, attr, val)

            spin.valueChanged.connect(on_change)

            def on_commit():
                mw = spin.window()
                if hasattr(mw, 'undo_manager') and old_values:
                    cmd = PropertyChangeCommand([c.entity for c in colliders], BoxCollider2D, attr, old_values, spin.value())
                    mw.undo_manager.push(cmd)

            spin.editingFinished.connect(on_commit)
            return spin

        width_spin = create_spin("width", 0.0, 10000.0, 1.0)
        height_spin = create_spin("height", 0.0, 10000.0, 1.0)
        offset_x_spin = create_spin("offset_x", -10000.0, 10000.0, 1.0)
        offset_y_spin = create_spin("offset_y", -10000.0, 10000.0, 1.0)
        rotation_spin = create_spin("rotation", -360.0, 360.0, 1.0)

        def refresh_box_spins():
            if not colliders: return
            for spin, attr in [(width_spin, 'width'), (height_spin, 'height'), (offset_x_spin, 'offset_x'), (offset_y_spin, 'offset_y'), (rotation_spin, 'rotation')]:
                values = [getattr(c, attr) for c in colliders]
                if not values: continue
                first = values[0] if values[0] is not None else 0.0
                is_mixed = any(abs((v if v is not None else 0.0) - first) > 0.0001 for v in values)
                spin.blockSignals(True)
                spin.setValue(first)
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;" if is_mixed else "")
                spin.blockSignals(False)

        if hasattr(self, 'update_callbacks'):
            self.update_callbacks.append(refresh_box_spins)

        form.addRow("Width", width_spin)
        form.addRow("Height", height_spin)
        form.addRow("Offset X", offset_x_spin)
        form.addRow("Offset Y", offset_y_spin)
        form.addRow("Rotation", rotation_spin)

        trigger_chk = QCheckBox()
        trigger_values = [c.is_trigger for c in colliders]
        trigger_mixed = any(v != trigger_values[0] for v in trigger_values)
        if trigger_mixed:
            trigger_chk.setTristate(True)
            trigger_chk.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            trigger_chk.setChecked(trigger_values[0])

        def on_trigger_change(state):
            is_checked = state == Qt.CheckState.Checked.value
            trigger_chk.setTristate(False)
            old_values = [c.is_trigger for c in colliders]
            for c in colliders:
                c.is_trigger = is_checked
            mw = trigger_chk.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([c.entity for c in colliders], BoxCollider2D, "is_trigger", old_values, is_checked)
                mw.undo_manager.push(cmd)

        trigger_chk.stateChanged.connect(on_trigger_change)
        form.addRow("Is Trigger", trigger_chk)

        self._add_component_section("BoxCollider2D", BoxCollider2D, len(colliders), group)

    def add_circle_collider_ui(self, colliders):
        if not isinstance(colliders, list):
            colliders = [colliders]

        group = QWidget()
        form = QFormLayout(group)

        def create_spin(attr, min_val, max_val, step=0.1):
            values = [getattr(c, attr) for c in colliders]
            normalized_values = [0.0 if v is None else v for v in values]
            spin = UndoableDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setSingleStep(step)

            first = normalized_values[0]
            mixed = any(abs(v - first) > 0.0001 for v in normalized_values)
            old_values = []

            def on_focus():
                nonlocal old_values
                old_values = [getattr(c, attr) for c in colliders]

            spin.focused.connect(on_focus)

            if mixed:
                spin.setValue(first)
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")
            else:
                spin.setValue(first)

            def on_change(val):
                spin.setStyleSheet("")
                for c in colliders:
                    setattr(c, attr, val)

            spin.valueChanged.connect(on_change)

            def on_commit():
                mw = spin.window()
                if hasattr(mw, 'undo_manager') and old_values:
                    cmd = PropertyChangeCommand([c.entity for c in colliders], CircleCollider2D, attr, old_values, spin.value())
                    mw.undo_manager.push(cmd)

            spin.editingFinished.connect(on_commit)
            return spin

        radius_spin = create_spin("radius", 0.0, 10000.0, 1.0)
        offset_x_spin = create_spin("offset_x", -10000.0, 10000.0, 1.0)
        offset_y_spin = create_spin("offset_y", -10000.0, 10000.0, 1.0)
        rotation_spin = create_spin("rotation", -360.0, 360.0, 1.0)

        def refresh_circle_spins():
            if not colliders: return
            for spin, attr in [(radius_spin, 'radius'), (offset_x_spin, 'offset_x'), (offset_y_spin, 'offset_y'), (rotation_spin, 'rotation')]:
                values = [getattr(c, attr) for c in colliders]
                if not values: continue
                first = values[0] if values[0] is not None else 0.0
                is_mixed = any(abs((v if v is not None else 0.0) - first) > 0.0001 for v in values)
                spin.blockSignals(True)
                spin.setValue(first)
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;" if is_mixed else "")
                spin.blockSignals(False)

        if hasattr(self, 'update_callbacks'):
            self.update_callbacks.append(refresh_circle_spins)

        form.addRow("Radius", radius_spin)
        form.addRow("Offset X", offset_x_spin)
        form.addRow("Offset Y", offset_y_spin)
        form.addRow("Rotation", rotation_spin)

        trigger_chk = QCheckBox()
        trigger_values = [c.is_trigger for c in colliders]
        trigger_mixed = any(v != trigger_values[0] for v in trigger_values)
        if trigger_mixed:
            trigger_chk.setTristate(True)
            trigger_chk.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            trigger_chk.setChecked(trigger_values[0])

        def on_trigger_change(state):
            is_checked = state == Qt.CheckState.Checked.value
            trigger_chk.setTristate(False)
            old_values = [c.is_trigger for c in colliders]
            for c in colliders:
                c.is_trigger = is_checked
            mw = trigger_chk.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([c.entity for c in colliders], CircleCollider2D, "is_trigger", old_values, is_checked)
                mw.undo_manager.push(cmd)

        trigger_chk.stateChanged.connect(on_trigger_change)
        form.addRow("Is Trigger", trigger_chk)

        self._add_component_section("CircleCollider2D", CircleCollider2D, len(colliders), group)

    def add_polygon_collider_ui(self, colliders):
        if not isinstance(colliders, list):
            colliders = [colliders]

        group = QWidget()
        form = QFormLayout(group)

        def create_spin(attr, min_val, max_val, step=0.1):
            values = [getattr(c, attr) for c in colliders]
            spin = UndoableDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setSingleStep(step)

            first = values[0]
            mixed = any(abs(v - first) > 0.0001 for v in values)
            old_values = []

            def on_focus():
                nonlocal old_values
                old_values = [getattr(c, attr) for c in colliders]

            spin.focused.connect(on_focus)
            spin.setValue(first)
            if mixed:
                spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

            def on_change(val):
                spin.setStyleSheet("")
                for c in colliders:
                    setattr(c, attr, val)

            spin.valueChanged.connect(on_change)

            def on_commit():
                mw = spin.window()
                if hasattr(mw, 'undo_manager') and old_values:
                    cmd = PropertyChangeCommand([c.entity for c in colliders], PolygonCollider2D, attr, old_values, spin.value())
                    mw.undo_manager.push(cmd)

            spin.editingFinished.connect(on_commit)
            return spin

        offset_x_spin = create_spin("offset_x", -10000.0, 10000.0, 1.0)
        offset_y_spin = create_spin("offset_y", -10000.0, 10000.0, 1.0)
        rotation_spin = create_spin("rotation", -360.0, 360.0, 1.0)

        points_section = QWidget()
        points_section_layout = QVBoxLayout(points_section)
        points_section_layout.setContentsMargins(0, 0, 0, 0)
        points_section_layout.setSpacing(4)
        points_header = QWidget()
        points_header_layout = QHBoxLayout(points_header)
        points_header_layout.setContentsMargins(0, 0, 0, 0)
        points_toggle_btn = QToolButton()
        points_toggle_btn.setText(f"Points ({len(colliders[0].points) if colliders else 0})")
        points_toggle_btn.setCheckable(True)
        points_toggle_btn.setChecked(True)
        points_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        points_toggle_btn.setArrowType(Qt.ArrowType.DownArrow)
        points_toggle_btn.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        points_header_layout.addWidget(points_toggle_btn)
        points_header_layout.addStretch()
        points_section_layout.addWidget(points_header)
        points_container = QWidget()
        points_list_layout = QVBoxLayout(points_container)
        points_list_layout.setContentsMargins(14, 0, 0, 0)
        points_list_layout.setSpacing(4)
        points_container.setVisible(True)
        points_section_layout.addWidget(points_container)

        def on_toggle_points(expanded):
            points_container.setVisible(expanded)
            points_toggle_btn.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

        points_toggle_btn.toggled.connect(on_toggle_points)

        if len(colliders) == 1:
            collider = colliders[0]
            add_row = QWidget()
            add_row_layout = QHBoxLayout(add_row)
            add_row_layout.setContentsMargins(0, 0, 0, 0)
            add_point_btn = QPushButton("Add New Point")
            add_status_label = QLabel("")
            add_row_layout.addWidget(add_point_btn)
            add_row_layout.addWidget(add_status_label)
            points_list_layout.addWidget(add_row)

            def refresh_add_state_label():
                viewport = None
                mw = self.window()
                if hasattr(mw, "viewport"):
                    viewport = mw.viewport
                if viewport and viewport.is_polygon_point_add_active(collider.entity):
                    add_point_btn.setText("Cancel Adding Points")
                    add_status_label.setText("Click in Scene view to place a point")
                else:
                    add_point_btn.setText("Start Adding New Point")
                    add_status_label.setText("")

            def on_add_point_clicked():
                viewport = None
                mw = self.window()
                if hasattr(mw, "viewport"):
                    viewport = mw.viewport
                if not viewport:
                    return
                if viewport.is_polygon_point_add_active(collider.entity):
                    viewport.stop_polygon_point_add_mode()
                else:
                    viewport.start_polygon_point_add_mode(collider.entity)
                refresh_add_state_label()

            add_point_btn.clicked.connect(on_add_point_clicked)
            refresh_add_state_label()

            for index in range(len(collider.points)):
                point = collider.points[index]
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                x_spin = UndoableDoubleSpinBox()
                x_spin.setFixedSize(60, 20)
                y_spin = UndoableDoubleSpinBox()
                y_spin.setFixedSize(60, 20)
                x_spin.setRange(-100000.0, 100000.0)
                y_spin.setRange(-100000.0, 100000.0)
                x_spin.setSingleStep(1.0)
                y_spin.setSingleStep(1.0)
                x_spin.setValue(point.x)
                y_spin.setValue(point.y)
                delete_btn = QPushButton("❌")
                delete_btn.setEnabled(len(collider.points) > 3)
                delete_btn.setFixedSize(20, 20)
                delete_btn.setStyleSheet("padding: 0px;")
                row_layout.addWidget(QLabel(f"P{index}"))
                row_layout.addWidget(QLabel("X"))
                row_layout.addWidget(x_spin)
                row_layout.addWidget(QLabel("Y"))
                row_layout.addWidget(y_spin)
                row_layout.addWidget(delete_btn)
                points_list_layout.addWidget(row)

                old_points_state = []

                def on_point_focus():
                    nonlocal old_points_state
                    old_points_state = [Vector2(p.x, p.y) for p in collider.points]

                x_spin.focused.connect(on_point_focus)
                y_spin.focused.connect(on_point_focus)

                def commit_point_change():
                    if not old_points_state:
                        return
                    new_points = [Vector2(p.x, p.y) for p in collider.points]
                    if len(new_points) != len(old_points_state):
                        changed = True
                    else:
                        changed = any(
                            abs(new_points[i].x - old_points_state[i].x) > 1e-6
                            or abs(new_points[i].y - old_points_state[i].y) > 1e-6
                            for i in range(len(new_points))
                        )
                    if not changed:
                        return
                    mw = self.window()
                    if hasattr(mw, 'undo_manager'):
                        cmd = PropertyChangeCommand(
                            [collider.entity],
                            PolygonCollider2D,
                            "points",
                            [old_points_state],
                            [Vector2(p.x, p.y) for p in new_points]
                        )
                        mw.undo_manager.push(cmd)

                def on_x_changed(value, point_index=index):
                    updated = [Vector2(p.x, p.y) for p in collider.points]
                    if 0 <= point_index < len(updated):
                        updated[point_index].x = value
                        collider.points = updated

                def on_y_changed(value, point_index=index):
                    updated = [Vector2(p.x, p.y) for p in collider.points]
                    if 0 <= point_index < len(updated):
                        updated[point_index].y = value
                        collider.points = updated

                def on_delete_point(point_index=index):
                    if len(collider.points) <= 3:
                        return
                    old_points = [Vector2(p.x, p.y) for p in collider.points]
                    updated = [Vector2(p.x, p.y) for p in collider.points]
                    if 0 <= point_index < len(updated):
                        del updated[point_index]
                    if len(updated) < 3:
                        return
                    collider.points = updated
                    mw = self.window()
                    if hasattr(mw, 'undo_manager'):
                        cmd = PropertyChangeCommand(
                            [collider.entity],
                            PolygonCollider2D,
                            "points",
                            [old_points],
                            [Vector2(p.x, p.y) for p in updated]
                        )
                        mw.undo_manager.push(cmd)
                    self.set_entities(self.current_entities)

                x_spin.valueChanged.connect(on_x_changed)
                y_spin.valueChanged.connect(on_y_changed)
                x_spin.editingFinished.connect(commit_point_change)
                y_spin.editingFinished.connect(commit_point_change)
                delete_btn.clicked.connect(on_delete_point)
        else:
            points_list_layout.addWidget(QLabel("Point editing available for single-entity selection"))

        form.addRow(points_section)
        form.addRow("Offset X", offset_x_spin)
        form.addRow("Offset Y", offset_y_spin)

        trigger_chk = QCheckBox()
        trigger_values = [c.is_trigger for c in colliders]
        trigger_mixed = any(v != trigger_values[0] for v in trigger_values)
        if trigger_mixed:
            trigger_chk.setTristate(True)
            trigger_chk.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            trigger_chk.setChecked(trigger_values[0])

        def on_trigger_change(state):
            is_checked = state == Qt.CheckState.Checked.value
            trigger_chk.setTristate(False)
            old_values = [c.is_trigger for c in colliders]
            for c in colliders:
                c.is_trigger = is_checked
            mw = trigger_chk.window()
            if hasattr(mw, 'undo_manager'):
                cmd = PropertyChangeCommand([c.entity for c in colliders], PolygonCollider2D, "is_trigger", old_values, is_checked)
                mw.undo_manager.push(cmd)

        trigger_chk.stateChanged.connect(on_trigger_change)
        form.addRow("Is Trigger", trigger_chk)

        self._add_component_section("PolygonCollider2D", PolygonCollider2D, len(colliders), group)

    def _project_base_dir(self):
        if self.parent() and hasattr(self.parent(), 'project_path') and self.parent().project_path:
            return self.parent().project_path
        return os.getcwd()

    def _to_project_relative_path(self, path):
        try:
            rel_path = os.path.relpath(path, self._project_base_dir())
            if not rel_path.startswith(".."):
                return ResourceManager.portable_path(rel_path)
        except Exception:
            pass
        return ResourceManager.portable_path(path)

    def _clone_clip(self, clip):
        cloned = dict(clip)
        frames = clip.get("frames", [])
        cloned["frames"] = list(frames)
        image_paths = clip.get("image_paths", [])
        cloned["image_paths"] = list(image_paths)
        return cloned

    def _copy_animator_data(self, source, target):
        target.clips = {name: self._clone_clip(clip) for name, clip in source.clips.items()}
        target.default_clip = source.default_clip if source.default_clip in target.clips else (next(iter(target.clips), None))
        target.play_on_start = bool(source.play_on_start)
        target.speed = float(source.speed)
        target.current_clip = target.default_clip
        target.current_frame_index = 0
        target._frame_timer = 0.0
        target.is_playing = False
        target.is_paused = False

    def _load_animator_into_targets(self, path, animators):
        loaded = SceneSerializer.load_animation_clip(path)
        for animator in animators:
            self._copy_animator_data(loaded, animator)

    def _save_animator_to_path(self, path, animator):
        SceneSerializer.save_animation_clip(path, animator)

    def apply_animation_clip_file(self, path, entities=None):
        target_entities = entities if entities is not None else list(self.current_entities)
        if not target_entities:
            return False
        animators = []
        for entity in target_entities:
            animator = entity.get_component(AnimatorComponent)
            if animator is None:
                animator = AnimatorComponent()
                entity.add_component(animator)
            animators.append(animator)
        self._load_animator_into_targets(path, animators)
        self.set_entities(target_entities)
        return True

    def add_animator_ui(self, animators):
        if not isinstance(animators, list):
            animators = [animators]

        group = QWidget()
        form = QFormLayout(group)

        # Speed
        speed_values = [float(animator.speed) for animator in animators]
        speed_spin = UndoableDoubleSpinBox()
        speed_spin.setRange(0.01, 100.0)
        speed_spin.setSingleStep(0.1)
        speed_spin.setValue(speed_values[0])
        if any(abs(value - speed_values[0]) > 0.0001 for value in speed_values):
            speed_spin.setStyleSheet("background-color: #4d4d33; color: #ffff99;")

        def on_speed_change(value):
            speed_spin.setStyleSheet("")
            for animator in animators:
                animator.speed = float(value)

        speed_spin.valueChanged.connect(on_speed_change)
        form.addRow("Speed", speed_spin)

        # Play On Start
        play_on_start_values = [bool(animator.play_on_start) for animator in animators]
        play_on_start_chk = QCheckBox()
        if any(value != play_on_start_values[0] for value in play_on_start_values):
            play_on_start_chk.setTristate(True)
            play_on_start_chk.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            play_on_start_chk.setChecked(play_on_start_values[0])

        def on_play_on_start_change(state):
            is_checked = state == Qt.CheckState.Checked.value
            play_on_start_chk.setTristate(False)
            for animator in animators:
                animator.play_on_start = is_checked

        play_on_start_chk.stateChanged.connect(on_play_on_start_change)
        form.addRow("Play On Start", play_on_start_chk)

        if len(animators) == 1:
            animator = animators[0]
            
            # State selection
            if animator.controller:
                state_combo = NoScrollComboBox()
                state_combo.addItem("")
                for node_name in animator.controller.nodes.keys():
                    if node_name == AnimationController.ROOT_NODE_NAME:
                        continue
                    state_combo.addItem(node_name)
                    
                if animator.current_state in animator.controller.nodes and animator.current_state != AnimationController.ROOT_NODE_NAME:
                    state_combo.setCurrentText(animator.current_state)
                else:
                    default_state = animator.controller.get_default_state()
                    if default_state:
                        state_combo.setCurrentText(default_state)
                    
                def on_state_changed(text):
                    if text:
                        # Ensure we have the latest data if modified in editor
                        if animator.controller_path:
                            animator.load_controller(animator.controller_path)
                        animator.play(text, restart=True)
                    else:
                        animator.stop(reset=True)
                        
                state_combo.currentTextChanged.connect(on_state_changed)
                form.addRow("State", state_combo)
                
                # Playback Controls
                ctrl_layout = QHBoxLayout()
                c = theme_icon_color()
                play_btn = QPushButton()
                play_btn.setIcon(qta.icon("fa5s.play", color=c))
                pause_btn = QPushButton()
                pause_btn.setIcon(qta.icon("fa5s.pause", color=c))
                stop_btn = QPushButton()
                stop_btn.setIcon(qta.icon("fa5s.stop", color=c))
                
                def on_play_clicked():
                    state = state_combo.currentText()
                    if state:
                        if animator.controller_path:
                            animator.load_controller(animator.controller_path)
                        animator.play(state, restart=True)
                        
                play_btn.clicked.connect(on_play_clicked)
                pause_btn.clicked.connect(animator.pause)
                stop_btn.clicked.connect(lambda: animator.stop(reset=True))
                
                ctrl_layout.addWidget(play_btn)
                ctrl_layout.addWidget(pause_btn)
                ctrl_layout.addWidget(stop_btn)
                
                form.addRow("Playback", ctrl_layout)

                trigger_row = QWidget()
                trigger_layout = QHBoxLayout(trigger_row)
                trigger_layout.setContentsMargins(0, 0, 0, 0)
                trigger_edit = QLineEdit()
                trigger_btn = QPushButton("Trigger")

                def on_trigger_clicked():
                    trigger_name = trigger_edit.text().strip()
                    if trigger_name:
                        animator.set_trigger(trigger_name)

                trigger_btn.clicked.connect(on_trigger_clicked)
                trigger_layout.addWidget(trigger_edit)
                trigger_layout.addWidget(trigger_btn)
                form.addRow("Trigger", trigger_row)
            
            path_row = QWidget()
            path_layout = QHBoxLayout(path_row)
            path_layout.setContentsMargins(0, 0, 0, 0)
            
            path_edit = QLineEdit(animator.controller_path or "")
            path_edit.setReadOnly(True)
            
            browse_btn = QPushButton("...")
            browse_btn.setFixedWidth(30)

            def refresh_animator_ui():
                self.set_entities(self.current_entities)
            
            def on_browse():
                start_dir = self._project_base_dir()
                file_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Select Animation Controller",
                    start_dir,
                    "Animation Controllers (*.actrl)"
                )
                if file_path:
                    try:
                        animator.controller_path = self._to_project_relative_path(file_path)
                        animator.load_controller(file_path)
                        path_edit.setText(animator.controller_path)
                        refresh_animator_ui()
                    except Exception as e:
                        print(f"Error loading controller: {e}")
            
            browse_btn.clicked.connect(on_browse)
            
            path_layout.addWidget(path_edit)
            path_layout.addWidget(browse_btn)
            
            form.addRow("Controller", path_row)
            
            # Create Controller Button
            create_btn = QPushButton("Create New Controller")
            
            def on_create_controller():
                start_dir = self._project_base_dir()
                suggested_name = "NewController.actrl"
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Create Animation Controller",
                    os.path.join(start_dir, suggested_name),
                    "Animation Controllers (*.actrl)"
                )
                if file_path:
                    if not file_path.endswith(".actrl"):
                        file_path += ".actrl"
                    
                    # Create empty controller
                    ctrl = AnimationController()
                    try:
                        SceneSerializer.save_animation_controller(file_path, ctrl)
                        
                        animator.controller_path = self._to_project_relative_path(file_path)
                        animator.load_controller(file_path)
                        path_edit.setText(animator.controller_path)
                        refresh_animator_ui()
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to create controller: {e}")
            
            create_btn.clicked.connect(on_create_controller)
            form.addRow("", create_btn)
            
            # Edit Controller Button (Launch Editor)
            edit_btn = QPushButton("Edit Controller")
            
            def on_edit_controller():
                if animator.controller_path:
                    # Resolve full path
                    path = animator.controller_path
                    if not os.path.isabs(path):
                        path = os.path.join(self._project_base_dir(), path)
                    self.open_controller_editor(path)
                else:
                    QMessageBox.warning(self, "Warning", "No controller selected.")

            edit_btn.clicked.connect(on_edit_controller)
            form.addRow("", edit_btn)
            
            # Runtime info
            if animator.current_state:
                 form.addRow("Current State", QLabel(animator.current_state))

        self._add_component_section("AnimatorComponent", AnimatorComponent, len(animators), group)

    def open_controller_editor(self, path):
        mw = self.window()
        if hasattr(mw, 'open_animation_controller_editor'):
            mw.open_animation_controller_editor(path)
        else:
            QMessageBox.information(self, "Info", f"Controller Editor not implemented yet.\nPath: {path}")

    def add_particle_emitter_ui(self, emitters):
        if not isinstance(emitters, list):
            emitters = [emitters]

        group = QWidget()
        form = QFormLayout(group)

        def create_combo(attr, options):
            combo = NoScrollComboBox()
            for label, value in options:
                combo.addItem(label, value)
            first = getattr(emitters[0], attr)
            combo.setCurrentIndex(max(0, combo.findData(first)))

            def on_change(_index):
                self._apply_value(emitters, attr, combo.currentData())

            combo.currentIndexChanged.connect(on_change)
            return combo

        form.addRow("Emitting", self._create_check(emitters, "emitting"))
        form.addRow("One Shot", self._create_check(emitters, "one_shot"))
        form.addRow("Local Space", self._create_check(emitters, "local_space"))
        form.addRow("Render Layer", create_combo("render_layer", [
            ("Behind", ParticleEmitterComponent.LAYER_BEHIND),
            ("Front", ParticleEmitterComponent.LAYER_FRONT),
        ]))
        form.addRow("Additive Blend", self._create_check(emitters, "blend_additive"))
        form.addRow("Shape", create_combo("shape", [
            ("Circle", ParticleEmitterComponent.SHAPE_CIRCLE),
            ("Square", ParticleEmitterComponent.SHAPE_SQUARE),
            ("Pixel", ParticleEmitterComponent.SHAPE_PIXEL),
        ]))

        form.addRow("Max Particles", self._create_spin(emitters, "max_particles", 1, 100000, 1, True))
        form.addRow("Emission Rate", self._create_spin(emitters, "emission_rate", 0.0, 100000.0, 1.0))
        form.addRow("Burst Count", self._create_spin(emitters, "burst_count", 0, 100000, 1, True))
        form.addRow("Burst Interval", self._create_spin(emitters, "burst_interval", 0.01, 3600.0, 0.01))
        form.addRow("Lifetime Min", self._create_spin(emitters, "lifetime_min", 0.01, 3600.0, 0.01))
        form.addRow("Lifetime Max", self._create_spin(emitters, "lifetime_max", 0.01, 3600.0, 0.01))
        form.addRow("Speed Min", self._create_spin(emitters, "speed_min", -100000.0, 100000.0, 1.0))
        form.addRow("Speed Max", self._create_spin(emitters, "speed_max", -100000.0, 100000.0, 1.0))
        form.addRow("Direction", self._create_spin(emitters, "direction_degrees", -3600.0, 3600.0, 1.0))
        form.addRow("Spread", self._create_spin(emitters, "spread_degrees", 0.0, 360.0, 1.0))
        form.addRow("Gravity X", self._create_spin(emitters, "gravity_x", -100000.0, 100000.0, 1.0))
        form.addRow("Gravity Y", self._create_spin(emitters, "gravity_y", -100000.0, 100000.0, 1.0))
        form.addRow("Damping", self._create_spin(emitters, "damping", 0.0, 1000.0, 0.01))
        form.addRow("Radial Offset Min", self._create_spin(emitters, "radial_offset_min", 0.0, 100000.0, 0.1))
        form.addRow("Radial Offset Max", self._create_spin(emitters, "radial_offset_max", 0.0, 100000.0, 0.1))
        form.addRow("Angular Velocity Min", self._create_spin(emitters, "angular_velocity_min", -100000.0, 100000.0, 1.0))
        form.addRow("Angular Velocity Max", self._create_spin(emitters, "angular_velocity_max", -100000.0, 100000.0, 1.0))
        form.addRow("Start Size Min", self._create_spin(emitters, "start_size_min", 0.1, 10000.0, 0.1))
        form.addRow("Start Size Max", self._create_spin(emitters, "start_size_max", 0.1, 10000.0, 0.1))
        form.addRow("End Size Min", self._create_spin(emitters, "end_size_min", 0.0, 10000.0, 0.1))
        form.addRow("End Size Max", self._create_spin(emitters, "end_size_max", 0.0, 10000.0, 0.1))
        form.addRow("Start Color", self._create_color_edit(emitters, "start_color"))
        form.addRow("End Color", self._create_color_edit(emitters, "end_color"))
        form.addRow("Emitter Lifetime", self._create_spin(emitters, "emitter_lifetime", -1.0, 3600.0, 0.1))

        self._add_component_section("ParticleEmitterComponent", ParticleEmitterComponent, len(emitters), group)

    def add_timer_ui(self, timers):
        if not isinstance(timers, list):
            timers = [timers]

        group = QWidget()
        form = QFormLayout(group)

        form.addRow("Duration", self._create_spin(timers, "duration", 0.0, 3600.0, 0.1))
        form.addRow("One Shot", self._create_check(timers, "one_shot"))
        form.addRow("Autostart", self._create_check(timers, "_running"))

        # Read-only status labels
        status_label = QLabel()
        elapsed_label = QLabel()

        def update_status():
            first = timers[0]
            if first.is_running:
                status_label.setText("Running")
                status_label.setStyleSheet("color: #88ff88;")
            elif first.is_finished:
                status_label.setText("Finished")
                status_label.setStyleSheet("color: #ffaa44;")
            else:
                status_label.setText("Stopped")
                status_label.setStyleSheet("color: #aaaaaa;")
            elapsed_label.setText(f"{first.elapsed:.2f}s / {first.duration:.2f}s")

        update_status()
        form.addRow("Status", status_label)
        form.addRow("Elapsed", elapsed_label)

        self.update_callbacks.append(update_status)

        self._add_component_section("TimerComponent", TimerComponent, len(timers), group)

    def _apply_value(self, components, attr, value):
        old_values = [getattr(c, attr) for c in components]
        for c in components:
            setattr(c, attr, value)
            
        mw = self.window()
        if hasattr(mw, 'undo_manager'):
             cmd = PropertyChangeCommand([c.entity for c in components], type(components[0]), attr, old_values, value)
             mw.undo_manager.push(cmd)

    def _create_spin(self, components, attr, min_val, max_val, step=1.0, is_int=False):
        vals = [getattr(c, attr) for c in components]
        spin = UndoableDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setValue(vals[0])
        
        def on_change():
            v = spin.value()
            if is_int: v = int(v)
            self._apply_value(components, attr, v)
            
        spin.editingFinished.connect(on_change)
        return spin
        
    def _create_text(self, components, attr):
        vals = [getattr(c, attr) for c in components]
        edit = UndoableLineEdit(str(vals[0]))
        def on_change():
            self._apply_value(components, attr, edit.text())
        edit.editingFinished.connect(on_change)
        return edit
        
    def _create_check(self, components, attr):
        vals = [getattr(c, attr) for c in components]
        chk = QCheckBox()
        chk.setChecked(bool(vals[0]))
        def on_change(state):
            self._apply_value(components, attr, state == 2) # 2 is Checked
        chk.stateChanged.connect(on_change)
        return chk

    def _create_color_edit(self, components, attr):
        vals = [getattr(c, attr) for c in components]
        # vals are tuples/lists of (r, g, b) or (r, g, b, a)
        first_val = vals[0]
        
        # Helper to convert tuple/list to QColor
        def to_qcolor(c):
            if len(c) >= 3:
                return QColor(int(c[0]), int(c[1]), int(c[2]), int(c[3]) if len(c) > 3 else 255)
            return QColor(255, 255, 255)

        btn = QPushButton()
        btn.setFlat(True)
        btn.setAutoFillBackground(True)
        
        def update_btn_style(color_tuple):
            c = to_qcolor(color_tuple)
            # Determine contrasting text color (black or white)
            luminance = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255
            text_color = "black" if luminance > 0.5 else "white"
            btn.setStyleSheet(f"background-color: {c.name()}; border: 1px solid #555; color: {text_color};")
            btn.setText(f"{c.name()}")

        update_btn_style(first_val)

        def on_click():
            initial = to_qcolor(vals[0])
            color = QColorDialog.getColor(initial, self, "Select Color", QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if color.isValid():
                new_val = (color.red(), color.green(), color.blue(), color.alpha())
                self._apply_value(components, attr, new_val)
                update_btn_style(new_val)
        
        btn.clicked.connect(on_click)
        return btn

    def add_text_renderer_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Text", self._create_text(components, "text"))
        form.addRow("Font Size", self._create_spin(components, "font_size", 1, 500, 1, True))
        form.addRow("Color", self._create_color_edit(components, "color"))
        self._add_component_section("TextRenderer", TextRenderer, len(components), group)

    def add_button_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Text", self._create_text(components, "text"))
        form.addRow("Width", self._create_spin(components, "width", 0, 10000))
        form.addRow("Height", self._create_spin(components, "height", 0, 10000))
        form.addRow("Normal Color", self._create_color_edit(components, "normal_color"))
        form.addRow("Hover Color", self._create_color_edit(components, "hover_color"))
        form.addRow("Pressed Color", self._create_color_edit(components, "pressed_color"))
        form.addRow("Text Color", self._create_color_edit(components, "text_color"))
        self._add_component_section("ButtonComponent", ButtonComponent, len(components), group)

    def add_text_input_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Text", self._create_text(components, "text"))
        form.addRow("Placeholder", self._create_text(components, "placeholder"))
        form.addRow("Width", self._create_spin(components, "width", 0, 10000))
        form.addRow("Height", self._create_spin(components, "height", 0, 10000))
        form.addRow("Text Color", self._create_color_edit(components, "text_color"))
        form.addRow("Background Color", self._create_color_edit(components, "bg_color"))
        self._add_component_section("TextInputComponent", TextInputComponent, len(components), group)

    def add_slider_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Value", self._create_spin(components, "value", -10000, 10000))
        form.addRow("Min Value", self._create_spin(components, "min_value", -10000, 10000))
        form.addRow("Max Value", self._create_spin(components, "max_value", -10000, 10000))
        form.addRow("Width", self._create_spin(components, "width", 0, 10000))
        form.addRow("Height", self._create_spin(components, "height", 0, 10000))
        form.addRow("Track Color", self._create_color_edit(components, "track_color"))
        form.addRow("Handle Color", self._create_color_edit(components, "handle_color"))
        self._add_component_section("SliderComponent", SliderComponent, len(components), group)

    def add_progress_bar_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Value", self._create_spin(components, "value", -10000, 10000))
        form.addRow("Min Value", self._create_spin(components, "min_value", -10000, 10000))
        form.addRow("Max Value", self._create_spin(components, "max_value", -10000, 10000))
        form.addRow("Width", self._create_spin(components, "width", 0, 10000))
        form.addRow("Height", self._create_spin(components, "height", 0, 10000))
        form.addRow("Background Color", self._create_color_edit(components, "bg_color"))
        form.addRow("Fill Color", self._create_color_edit(components, "fill_color"))
        self._add_component_section("ProgressBarComponent", ProgressBarComponent, len(components), group)

    def add_checkbox_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Checked", self._create_check(components, "checked"))
        form.addRow("Size", self._create_spin(components, "size", 0, 1000))
        form.addRow("Checked Color", self._create_color_edit(components, "checked_color"))
        form.addRow("Unchecked Color", self._create_color_edit(components, "unchecked_color"))
        self._add_component_section("CheckBoxComponent", CheckBoxComponent, len(components), group)

    def add_ui_image_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Width", self._create_spin(components, "width", 0, 10000))
        form.addRow("Height", self._create_spin(components, "height", 0, 10000))
        
        # Image path (reuse sprite logic simplified)
        path_edit = self._create_text(components, "image_path")
        path_edit.setPlaceholderText("Path to image")
        
        def on_path_change():
             # Load image logic
             path = path_edit.text()
             # Resolve path
             load_path = path
             if not os.path.isabs(path) and self.parent() and hasattr(self.parent(), 'project_path') and self.parent().project_path:
                 load_path = os.path.join(self.parent().project_path, path)
             
             for c in components:
                 if os.path.exists(load_path):
                      c.image = pygame.image.load(load_path)
                      c.image_path = path
                      c.width = float(c.image.get_width())
                      c.height = float(c.image.get_height())
                 else:
                      c.image_path = path
                      
        path_edit.editingFinished.connect(on_path_change)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self.browse_image(components, path_edit, None, None)) # Reusing browse_image if possible or create new
        
        # browse_image expects w_spin, h_spin. I passed None.
        # I should probably just implement simple browse here or fix browse_image to handle None.
        
        form.addRow("Image Path", path_edit)
        form.addRow(browse_btn)
        
        self._add_component_section("ImageRenderer (UI)", ImageRenderer, len(components), group)

    def add_hbox_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Spacing", self._create_spin(components, "spacing", 0, 1000))
        self._add_component_section("HBoxContainer", HBoxContainerComponent, len(components), group)

    def add_vbox_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Spacing", self._create_spin(components, "spacing", 0, 1000))
        self._add_component_section("VBoxContainer", VBoxContainerComponent, len(components), group)

    def add_gridbox_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Columns", self._create_spin(components, "columns", 1, 100, 1, True))
        form.addRow("H Spacing", self._create_spin(components, "spacing_x", 0, 1000))
        form.addRow("V Spacing", self._create_spin(components, "spacing_y", 0, 1000))
        self._add_component_section("GridBoxContainer", GridBoxContainerComponent, len(components), group)

    def add_tilemap_ui(self, components):
        from editor.ui.tilemap_editor import TilemapComponentUI
        
        # Create the tilemap component UI
        tilemap_ui = TilemapComponentUI(components, self)
        self._add_component_section("Tilemap", TilemapComponent, len(components), tilemap_ui)

    # -- Steering AI Inspector UIs -------------------------------------------

    def add_steering_agent_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Max Speed", self._create_spin(components, "max_speed", 0, 10000, 10))
        form.addRow("Max Force", self._create_spin(components, "max_force", 0, 10000, 10))
        form.addRow("Mass", self._create_spin(components, "mass", 0.01, 1000, 0.1))
        form.addRow("Drag", self._create_spin(components, "drag", 0, 100, 0.1))
        self._add_component_section("SteeringAgentComponent", SteeringAgentComponent, len(components), group)

    def add_seek_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Enabled", self._create_check(components, "enabled"))
        form.addRow("Target X", self._create_spin(components, "target_x", -100000, 100000, 1))
        form.addRow("Target Y", self._create_spin(components, "target_y", -100000, 100000, 1))
        form.addRow("Weight", self._create_spin(components, "weight", 0, 100, 0.1))
        self._add_component_section("SeekBehavior", SeekBehavior, len(components), group)

    def add_flee_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Enabled", self._create_check(components, "enabled"))
        form.addRow("Target X", self._create_spin(components, "target_x", -100000, 100000, 1))
        form.addRow("Target Y", self._create_spin(components, "target_y", -100000, 100000, 1))
        form.addRow("Weight", self._create_spin(components, "weight", 0, 100, 0.1))
        form.addRow("Panic Distance", self._create_spin(components, "panic_distance", 0, 10000, 10))
        self._add_component_section("FleeBehavior", FleeBehavior, len(components), group)

    def add_arrive_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Enabled", self._create_check(components, "enabled"))
        form.addRow("Target X", self._create_spin(components, "target_x", -100000, 100000, 1))
        form.addRow("Target Y", self._create_spin(components, "target_y", -100000, 100000, 1))
        form.addRow("Weight", self._create_spin(components, "weight", 0, 100, 0.1))
        form.addRow("Slow Radius", self._create_spin(components, "slow_radius", 1, 10000, 10))
        self._add_component_section("ArriveBehavior", ArriveBehavior, len(components), group)

    def add_wander_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Enabled", self._create_check(components, "enabled"))
        form.addRow("Weight", self._create_spin(components, "weight", 0, 100, 0.1))
        form.addRow("Circle Distance", self._create_spin(components, "circle_distance", 0, 1000, 1))
        form.addRow("Circle Radius", self._create_spin(components, "circle_radius", 0, 1000, 1))
        form.addRow("Angle Change", self._create_spin(components, "angle_change", 0, 360, 1))
        self._add_component_section("WanderBehavior", WanderBehavior, len(components), group)

    def add_separation_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Enabled", self._create_check(components, "enabled"))
        form.addRow("Weight", self._create_spin(components, "weight", 0, 100, 0.1))
        form.addRow("Neighbor Radius", self._create_spin(components, "neighbor_radius", 0, 10000, 10))
        self._add_component_section("SeparationBehavior", SeparationBehavior, len(components), group)

    def add_cohesion_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Enabled", self._create_check(components, "enabled"))
        form.addRow("Weight", self._create_spin(components, "weight", 0, 100, 0.1))
        form.addRow("Neighbor Radius", self._create_spin(components, "neighbor_radius", 0, 10000, 10))
        self._add_component_section("CohesionBehavior", CohesionBehavior, len(components), group)

    def add_alignment_ui(self, components):
        group = QWidget()
        form = QFormLayout(group)
        form.addRow("Enabled", self._create_check(components, "enabled"))
        form.addRow("Weight", self._create_spin(components, "weight", 0, 100, 0.1))
        form.addRow("Neighbor Radius", self._create_spin(components, "neighbor_radius", 0, 10000, 10))
        self._add_component_section("AlignmentBehavior", AlignmentBehavior, len(components), group)

    # ------------------------------------------------------------------
    # Lighting component UIs
    # ------------------------------------------------------------------

    def add_point_light_ui(self, components):
        if not isinstance(components, list):
            components = [components]

        group = QWidget()
        form = QFormLayout(group)

        form.addRow("Radius", self._create_spin(components, "radius", 1.0, 10000.0, 10.0))
        form.addRow("Intensity", self._create_spin(components, "intensity", 0.0, 10.0, 0.05))
        form.addRow("Falloff", self._create_spin(components, "falloff", 0.1, 10.0, 0.1))
        form.addRow("Color", self._create_color_edit(components, "color"))

        self._add_component_section("PointLight2D", PointLight2D, len(components), group)

    def add_spot_light_ui(self, components):
        if not isinstance(components, list):
            components = [components]

        group = QWidget()
        form = QFormLayout(group)

        form.addRow("Radius", self._create_spin(components, "radius", 1.0, 10000.0, 10.0))
        form.addRow("Intensity", self._create_spin(components, "intensity", 0.0, 10.0, 0.05))
        form.addRow("Falloff", self._create_spin(components, "falloff", 0.1, 10.0, 0.1))
        form.addRow("Angle", self._create_spin(components, "angle", -360.0, 360.0, 5.0))
        form.addRow("Cone Angle", self._create_spin(components, "cone_angle", 1.0, 180.0, 5.0))
        form.addRow("Offset X", self._create_spin(components, "offset_x", -10000.0, 10000.0, 1.0))
        form.addRow("Offset Y", self._create_spin(components, "offset_y", -10000.0, 10000.0, 1.0))
        form.addRow("Color", self._create_color_edit(components, "color"))

        self._add_component_section("SpotLight2D", SpotLight2D, len(components), group)

    def add_light_occluder_ui(self, components):
        if not isinstance(components, list):
            components = [components]

        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        form = QFormLayout()
        layout.addLayout(form)

        # Shape dropdown
        shape_combo = QComboBox()
        shape_combo.addItems(["box", "circle", "polygon"])
        current_shape = components[0].shape if components else "box"
        shape_combo.setCurrentText(current_shape)

        def on_shape_changed(new_shape):
            for c in components:
                old_shape = c.shape
                if old_shape != new_shape:
                    c.shape = new_shape
                    # Auto-size from sprite if switching to box or circle
                    if new_shape in ("box", "circle") and hasattr(c, 'entity') and c.entity:
                        sprite = c.entity.get_component(SpriteRenderer)
                        if sprite:
                            if new_shape == "box":
                                c.width = max(1.0, float(sprite.width))
                                c.height = max(1.0, float(sprite.height))
                            elif new_shape == "circle":
                                c.radius = max(1.0, max(float(sprite.width), float(sprite.height)) * 0.5)
                    if new_shape == "polygon":
                        if len(c.points) < 3:
                            c.points = None  # triggers default polygon
            self._apply_value(components, "shape", new_shape)
            self.set_entities(self.current_entities)

        shape_combo.currentTextChanged.connect(on_shape_changed)
        form.addRow("Shape", shape_combo)

        # Offset
        form.addRow("Offset X", self._create_spin(components, "offset_x", -10000.0, 10000.0, 1.0))
        form.addRow("Offset Y", self._create_spin(components, "offset_y", -10000.0, 10000.0, 1.0))

        # Rotation
        form.addRow("Rotation", self._create_spin(components, "rotation", -360.0, 360.0, 1.0))

        # Receive light / receive shadow flags
        form.addRow("Receive Light", self._create_check(components, "receive_light"))
        form.addRow("Receive Shadow", self._create_check(components, "receive_shadow"))

        # Shape-specific fields
        if current_shape == "box":
            form.addRow("Width", self._create_spin(components, "width", 1.0, 10000.0, 1.0))
            form.addRow("Height", self._create_spin(components, "height", 1.0, 10000.0, 1.0))
        elif current_shape == "circle":
            form.addRow("Radius", self._create_spin(components, "radius", 1.0, 10000.0, 1.0))
        elif current_shape == "polygon":
            # Polygon point editing — mirrors PolygonCollider2D UI
            points_section = QWidget()
            points_section_layout = QVBoxLayout(points_section)
            points_section_layout.setContentsMargins(0, 0, 0, 0)
            points_section_layout.setSpacing(4)
            points_header = QWidget()
            points_header_layout = QHBoxLayout(points_header)
            points_header_layout.setContentsMargins(0, 0, 0, 0)
            points_toggle_btn = QToolButton()
            points_toggle_btn.setText(f"Points ({len(components[0].points) if components else 0})")
            points_toggle_btn.setCheckable(True)
            points_toggle_btn.setChecked(True)
            points_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            points_toggle_btn.setArrowType(Qt.ArrowType.DownArrow)
            points_toggle_btn.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
            points_header_layout.addWidget(points_toggle_btn)
            points_header_layout.addStretch()
            points_section_layout.addWidget(points_header)
            points_container = QWidget()
            points_list_layout = QVBoxLayout(points_container)
            points_list_layout.setContentsMargins(14, 0, 0, 0)
            points_list_layout.setSpacing(4)
            points_container.setVisible(True)
            points_section_layout.addWidget(points_container)

            def on_toggle_points(expanded):
                points_container.setVisible(expanded)
                points_toggle_btn.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
            points_toggle_btn.toggled.connect(on_toggle_points)

            if len(components) == 1:
                occluder = components[0]

                # Add point button (reuses polygon collider viewport logic)
                add_row = QWidget()
                add_row_layout = QHBoxLayout(add_row)
                add_row_layout.setContentsMargins(0, 0, 0, 0)
                add_point_btn = QPushButton("Add New Point")
                add_status_label = QLabel("")
                add_row_layout.addWidget(add_point_btn)
                add_row_layout.addWidget(add_status_label)
                points_list_layout.addWidget(add_row)

                def refresh_occ_add_state():
                    viewport = None
                    mw = self.window()
                    if hasattr(mw, "viewport"):
                        viewport = mw.viewport
                    if viewport and getattr(viewport, '_occ_point_add_entity', None) is occluder.entity:
                        add_point_btn.setText("Cancel Adding Points")
                        add_status_label.setText("Click in Scene view to place a point")
                    else:
                        add_point_btn.setText("Start Adding New Point")
                        add_status_label.setText("")

                def on_occ_add_point_clicked():
                    viewport = None
                    mw = self.window()
                    if hasattr(mw, "viewport"):
                        viewport = mw.viewport
                    if not viewport:
                        return
                    if getattr(viewport, '_occ_point_add_entity', None) is occluder.entity:
                        viewport._occ_point_add_entity = None
                    else:
                        viewport._occ_point_add_entity = occluder.entity
                    refresh_occ_add_state()

                add_point_btn.clicked.connect(on_occ_add_point_clicked)
                refresh_occ_add_state()

                for index in range(len(occluder.points)):
                    point = occluder.points[index]
                    row = QWidget()
                    row_layout = QHBoxLayout(row)
                    row_layout.setContentsMargins(0, 0, 0, 0)
                    x_spin = UndoableDoubleSpinBox()
                    x_spin.setFixedSize(60, 20)
                    y_spin = UndoableDoubleSpinBox()
                    y_spin.setFixedSize(60, 20)
                    x_spin.setRange(-100000.0, 100000.0)
                    y_spin.setRange(-100000.0, 100000.0)
                    x_spin.setSingleStep(1.0)
                    y_spin.setSingleStep(1.0)
                    x_spin.setValue(point.x)
                    y_spin.setValue(point.y)
                    delete_btn = QPushButton("\u274c")
                    delete_btn.setEnabled(len(occluder.points) > 3)
                    delete_btn.setFixedSize(20, 20)
                    delete_btn.setStyleSheet("padding: 0px;")
                    row_layout.addWidget(QLabel(f"P{index}"))
                    row_layout.addWidget(QLabel("X"))
                    row_layout.addWidget(x_spin)
                    row_layout.addWidget(QLabel("Y"))
                    row_layout.addWidget(y_spin)
                    row_layout.addWidget(delete_btn)
                    points_list_layout.addWidget(row)

                    old_points_state = []

                    def on_point_focus():
                        nonlocal old_points_state
                        old_points_state = [Vector2(p.x, p.y) for p in occluder.points]
                    x_spin.focused.connect(on_point_focus)
                    y_spin.focused.connect(on_point_focus)

                    def commit_occ_point_change():
                        if not old_points_state:
                            return
                        new_points = [Vector2(p.x, p.y) for p in occluder.points]
                        if len(new_points) != len(old_points_state):
                            changed = True
                        else:
                            changed = any(
                                abs(new_points[i].x - old_points_state[i].x) > 1e-6
                                or abs(new_points[i].y - old_points_state[i].y) > 1e-6
                                for i in range(len(new_points))
                            )
                        if not changed:
                            return
                        mw = self.window()
                        if hasattr(mw, 'undo_manager'):
                            cmd = PropertyChangeCommand(
                                [occluder.entity], LightOccluder2D, "points",
                                [old_points_state],
                                [Vector2(p.x, p.y) for p in new_points]
                            )
                            mw.undo_manager.push(cmd)

                    def on_occ_x_changed(value, pi=index):
                        updated = [Vector2(p.x, p.y) for p in occluder.points]
                        if 0 <= pi < len(updated):
                            updated[pi].x = value
                            occluder.points = updated

                    def on_occ_y_changed(value, pi=index):
                        updated = [Vector2(p.x, p.y) for p in occluder.points]
                        if 0 <= pi < len(updated):
                            updated[pi].y = value
                            occluder.points = updated

                    def on_occ_delete_point(pi=index):
                        if len(occluder.points) <= 3:
                            return
                        old_points = [Vector2(p.x, p.y) for p in occluder.points]
                        updated = [Vector2(p.x, p.y) for p in occluder.points]
                        if 0 <= pi < len(updated):
                            del updated[pi]
                        if len(updated) < 3:
                            return
                        occluder.points = updated
                        mw = self.window()
                        if hasattr(mw, 'undo_manager'):
                            cmd = PropertyChangeCommand(
                                [occluder.entity], LightOccluder2D, "points",
                                [old_points],
                                [Vector2(p.x, p.y) for p in updated]
                            )
                            mw.undo_manager.push(cmd)
                        self.set_entities(self.current_entities)

                    x_spin.valueChanged.connect(on_occ_x_changed)
                    y_spin.valueChanged.connect(on_occ_y_changed)
                    x_spin.editingFinished.connect(commit_occ_point_change)
                    y_spin.editingFinished.connect(commit_occ_point_change)
                    delete_btn.clicked.connect(on_occ_delete_point)
            else:
                points_list_layout.addWidget(QLabel("Point editing available for single-entity selection"))

            layout.addWidget(points_section)

        self._add_component_section("LightOccluder2D", LightOccluder2D, len(components), group)
