from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QFileDialog, 
    QMessageBox, QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem, 
    QGraphicsLineItem, QGraphicsTextItem, QFormLayout, QLineEdit, QSpinBox, 
    QDoubleSpinBox, QCheckBox, QPushButton, QLabel, QSplitter, QComboBox, QListWidget,
    QGroupBox, QDockWidget
)
from PyQt6.QtGui import QPen, QBrush, QColor, QPainter, QAction, QPixmap
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
import os
import json
from core.animation import AnimationController, AnimationClip, AnimationNode, AnimationTransition
from core.serializer import SceneSerializer
from core.resources import ResourceManager
import qtawesome as qta
from editor.ui.engine_settings import theme_icon_color

class EditorGraphicsView(QGraphicsView):
    def __init__(self, scene, controller_widget=None):
        super().__init__(scene)
        self.controller_widget = controller_widget
        self.setMouseTracking(True)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1 / zoom_in_factor
            if event.angleDelta().y() > 0:
                zoom_factor = zoom_in_factor
            else:
                zoom_factor = zoom_out_factor
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.controller_widget and self.controller_widget.is_dragging_transition:
            self.controller_widget.update_transition_drag(self.mapToScene(event.pos()))

    def mousePressEvent(self, event):
        if self.controller_widget and self.controller_widget.is_dragging_transition:
            if event.button() == Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.pos())
                # Temporarily hide drag line so it doesn't intercept the hit test
                if self.controller_widget.drag_line:
                    self.controller_widget.drag_line.hide()
                
                item = self.scene().itemAt(scene_pos, self.transform())
                
                # Restore drag line visibility just in case
                if self.controller_widget.drag_line:
                    self.controller_widget.drag_line.show()
                    
                self.controller_widget.finish_transition_drag(item)
                return
            elif event.button() == Qt.MouseButton.RightButton:
                self.controller_widget.cancel_transition_drag()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            if self.controller_widget:
                self.controller_widget.delete_selected_item()
        elif event.key() == Qt.Key.Key_Space:
            if self.controller_widget:
                self.controller_widget.replay_selected_node_preview()
        else:
            super().keyPressEvent(event)

class NodeItem(QGraphicsRectItem):
    def __init__(self, node_name, x, y, controller_widget, width=150, height=60):
        super().__init__(0, 0, width, height)
        self.controller_widget = controller_widget
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(60, 60, 60)))
        self.setPen(QPen(QColor(200, 200, 200), 2))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.text_item = QGraphicsTextItem(node_name, self)
        self.text_item.setDefaultTextColor(QColor(255, 255, 255))
        self.text_item.setPos(10, 10)
        
        self.node_name = node_name

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self.controller_widget:
                self.controller_widget.update_edges(self)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        if self.controller_widget:
            self.controller_widget.start_transition_drag(self)
        super().mouseDoubleClickEvent(event)

class EdgeItem(QGraphicsLineItem):
    def __init__(self, start_item, end_item, transition, offset_sign=0):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.transition = transition
        self.offset_sign = offset_sign
        self.setPen(QPen(QColor(80, 220, 120), 1))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_position()

    def update_position(self):
        start_rect = self.start_item.sceneBoundingRect()
        end_rect = self.end_item.sceneBoundingRect()
        
        p1 = start_rect.center()
        p2 = end_rect.center()
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        
        if abs(dx) > abs(dy):
            if dx > 0:
                pt1 = QPointF(start_rect.right(), p1.y())
                pt2 = QPointF(end_rect.left(), p2.y())
            else:
                pt1 = QPointF(start_rect.left(), p1.y())
                pt2 = QPointF(end_rect.right(), p2.y())
        else:
            if dy > 0:
                pt1 = QPointF(p1.x(), start_rect.bottom())
                pt2 = QPointF(p2.x(), end_rect.top())
            else:
                pt1 = QPointF(p1.x(), start_rect.top())
                pt2 = QPointF(p2.x(), end_rect.bottom())

        if self.offset_sign:
            length = max(1.0, ((pt2.x() - pt1.x()) ** 2 + (pt2.y() - pt1.y()) ** 2) ** 0.5)
            nx = -(pt2.y() - pt1.y()) / length
            ny = (pt2.x() - pt1.x()) / length
            offset = 10.0 * float(self.offset_sign)
            pt1 = QPointF(pt1.x() + nx * offset, pt1.y() + ny * offset)
            pt2 = QPointF(pt2.x() + nx * offset, pt2.y() + ny * offset)

        self.setLine(pt1.x(), pt1.y(), pt2.x(), pt2.y())

    def paint(self, painter, option, widget=None):
        pen_color = QColor(150, 255, 180) if self.isSelected() else QColor(80, 220, 120)
        painter.setPen(QPen(pen_color, 5))
        line = self.line()
        painter.drawLine(line)
        dx = line.x2() - line.x1()
        dy = line.y2() - line.y1()
        length = (dx * dx + dy * dy) ** 0.5
        if length > 0:
            ux = dx / length
            uy = dy / length
            arrow_len = 12.0
            arrow_w = 6.0
            tip = QPointF(line.x2(), line.y2())
            base = QPointF(tip.x() - ux * arrow_len, tip.y() - uy * arrow_len)
            nx = -uy
            ny = ux
            left = QPointF(base.x() + nx * arrow_w, base.y() + ny * arrow_w)
            right = QPointF(base.x() - nx * arrow_w, base.y() - ny * arrow_w)
            painter.setBrush(pen_color)
            painter.drawPolygon(tip, left, right)

class ControllerEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = None
        self.controller_path = None
        self.project_dir = os.getcwd()
        self.scene = QGraphicsScene()
        self.view = EditorGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.node_preview_timer = QTimer(self)
        self.node_preview_timer.timeout.connect(self.advance_node_preview)
        self.node_preview_frames = []
        self.node_preview_index = 0
        self.node_preview_loop = True
        
        # Transition drag state
        self.is_dragging_transition = False
        self.drag_start_node = None
        self.drag_line = None
        
        # Selection event
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.selected_node = None
        
        main_layout = QVBoxLayout(self)
        
        toolbar = QHBoxLayout()
        add_node_btn = QPushButton("Add Node")
        add_node_btn.clicked.connect(self.add_node)
        delete_node_btn = QPushButton("Delete Node")
        delete_node_btn.clicked.connect(self.delete_selected_node)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_controller)
        
        toolbar.addWidget(add_node_btn)
        toolbar.addWidget(delete_node_btn)
        toolbar.addWidget(save_btn)
        toolbar.addStretch()
        
        main_layout.addLayout(toolbar)
        
        # Splitter for View and Properties
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.view)
        
        # Properties Panel
        self.props_panel = QGroupBox("Node Properties")
        self.props_layout = QFormLayout(self.props_panel)
        
        self.node_name_edit = QLineEdit()
        self.node_name_edit.editingFinished.connect(self.on_name_changed)
        
        self.node_clip_edit = QLineEdit()
        self.node_clip_edit.setReadOnly(True)
        self.browse_clip_btn = QPushButton("...")
        self.browse_clip_btn.setFixedWidth(30)
        self.browse_clip_btn.clicked.connect(self.browse_clip)
        self.selected_edge = None
        
        self.clip_row_widget = QWidget()
        clip_layout = QHBoxLayout(self.clip_row_widget)
        clip_layout.setContentsMargins(0, 0, 0, 0)
        clip_layout.addWidget(self.node_clip_edit)
        clip_layout.addWidget(self.browse_clip_btn)

        self.node_name_label = QLabel("Name")
        self.node_clip_label = QLabel("Clip (.anim)")
        self.props_layout.addRow(self.node_name_label, self.node_name_edit)
        self.props_layout.addRow(self.node_clip_label, self.clip_row_widget)

        self.transition_trigger_label = QLabel("Trigger")
        self.transition_trigger_edit = QLineEdit()
        self.transition_trigger_edit.editingFinished.connect(self.on_transition_changed)
        self.transition_on_finish_label = QLabel("On Finish")
        self.transition_on_finish_chk = QCheckBox()
        self.transition_on_finish_chk.stateChanged.connect(self.on_transition_changed)
        self.props_layout.addRow(self.transition_trigger_label, self.transition_trigger_edit)
        self.props_layout.addRow(self.transition_on_finish_label, self.transition_on_finish_chk)
        self.transition_trigger_label.setVisible(False)
        self.transition_trigger_edit.setVisible(False)
        self.transition_on_finish_label.setVisible(False)
        self.transition_on_finish_chk.setVisible(False)

        self.node_preview_label = QLabel("No Preview")
        self.node_preview_label.setMinimumSize(220, 180)
        self.node_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.props_layout.addRow("Preview", self.node_preview_label)
        
        self.splitter.addWidget(self.props_panel)
        self.splitter.setSizes([700, 300])
        self.props_panel.setEnabled(False)
        
        main_layout.addWidget(self.splitter)
        
        self.nodes = {} # name -> NodeItem
        self.edges = [] # EdgeItem

    def on_selection_changed(self):
        try:
            selected = self.scene.selectedItems()
        except RuntimeError:
            return
        if not self.controller:
            return

        node_items = [item for item in selected if isinstance(item, NodeItem)]
        edge_items = [item for item in selected if isinstance(item, EdgeItem)]
        self.selected_edge = None

        if len(node_items) == 1:
            self.selected_node = node_items[0]
            self.props_panel.setEnabled(True)
            self.props_panel.setTitle("Node Properties")
            self.node_name_label.setVisible(True)
            self.node_name_edit.setVisible(True)
            self.node_clip_label.setVisible(True)
            self.clip_row_widget.setVisible(True)
            self.node_name_edit.setText(self.selected_node.node_name)
            node_data = self.controller.nodes.get(self.selected_node.node_name)
            self.node_clip_edit.setText(node_data.clip_path if node_data else "")
            is_root = self.selected_node.node_name == AnimationController.ROOT_NODE_NAME
            self.node_name_edit.setReadOnly(is_root)
            self.browse_clip_btn.setEnabled(not is_root)
            self.transition_trigger_label.setVisible(False)
            self.transition_trigger_edit.setVisible(False)
            self.transition_on_finish_label.setVisible(False)
            self.transition_on_finish_chk.setVisible(False)
            self.transition_trigger_edit.setText("")
            self.transition_on_finish_chk.setChecked(False)
            self.start_node_preview(node_data.clip_path if node_data else "")
        elif len(edge_items) == 1:
            self.selected_node = None
            self.selected_edge = edge_items[0]
            self.props_panel.setEnabled(True)
            self.props_panel.setTitle("Transition Properties")
            self.node_name_label.setVisible(False)
            self.node_name_edit.setVisible(False)
            self.node_clip_label.setVisible(False)
            self.clip_row_widget.setVisible(False)
            self.node_name_edit.clear()
            self.node_name_edit.setReadOnly(True)
            self.node_clip_edit.clear()
            self.browse_clip_btn.setEnabled(False)
            transition = self.selected_edge.transition
            self.transition_trigger_label.setVisible(True)
            self.transition_trigger_edit.setVisible(True)
            self.transition_on_finish_label.setVisible(True)
            self.transition_on_finish_chk.setVisible(True)
            self.transition_trigger_edit.setText(transition.trigger)
            self.transition_on_finish_chk.setChecked(bool(transition.on_finish))
            self.stop_node_preview()
        else:
            self.selected_node = None
            self.props_panel.setEnabled(False)
            self.props_panel.setTitle("Node Properties")
            self.node_name_label.setVisible(True)
            self.node_name_edit.setVisible(True)
            self.node_clip_label.setVisible(True)
            self.clip_row_widget.setVisible(True)
            self.node_name_edit.clear()
            self.node_clip_edit.clear()
            self.node_name_edit.setReadOnly(False)
            self.browse_clip_btn.setEnabled(True)
            self.transition_trigger_label.setVisible(False)
            self.transition_trigger_edit.setVisible(False)
            self.transition_on_finish_label.setVisible(False)
            self.transition_on_finish_chk.setVisible(False)
            self.transition_trigger_edit.setText("")
            self.transition_on_finish_chk.setChecked(False)
            self.stop_node_preview()

    def on_name_changed(self):
        if not self.selected_node or not self.controller:
            return
        new_name = self.node_name_edit.text().strip()
        old_name = self.selected_node.node_name

        if old_name == AnimationController.ROOT_NODE_NAME:
            self.node_name_edit.setText(old_name)
            return
        if not new_name or new_name == old_name or new_name in self.controller.nodes:
            self.node_name_edit.setText(old_name)
            return
        if not self.controller.rename_node(old_name, new_name):
            self.node_name_edit.setText(old_name)
            return
        self.nodes[new_name] = self.nodes.pop(old_name)
        self.selected_node.node_name = new_name
        self.selected_node.text_item.setPlainText(new_name)

    def _to_project_relative(self, path):
        """Convert an absolute path to a project-relative portable path (forward slashes)."""
        abs_project = os.path.abspath(self.project_dir)
        abs_path = os.path.abspath(path)
        try:
            rel = os.path.relpath(abs_path, abs_project)
            if not rel.startswith(".."):
                return ResourceManager.portable_path(rel)
        except ValueError:
            pass
        return ResourceManager.portable_path(abs_path)

    def browse_clip(self):
        if not self.selected_node or not self.controller:
            return
        if self.selected_node.node_name == AnimationController.ROOT_NODE_NAME:
            return
            
        path, _ = QFileDialog.getOpenFileName(self, "Select Animation Clip", self.project_dir, "Animation Clips (*.anim)")
        if path:
            rel_path = self._to_project_relative(path)
            self.node_clip_edit.setText(rel_path)
            node_name = self.selected_node.node_name
            self.controller.nodes[node_name].clip_path = rel_path

            clip_base_name = os.path.splitext(os.path.basename(rel_path))[0]
            self.node_name_edit.setText(clip_base_name)
            self.on_name_changed()

    def on_transition_changed(self):
        if not self.selected_edge:
            return
        transition = self.selected_edge.transition
        transition.trigger = self.transition_trigger_edit.text().strip()
        transition.on_finish = self.transition_on_finish_chk.isChecked()

    def resolve_clip_path(self, clip_path: str):
        if not clip_path:
            return ""
        clip_path = ResourceManager.to_os_path(clip_path)
        if os.path.isabs(clip_path) and os.path.exists(clip_path):
            return clip_path
        candidates = []
        if self.controller_path:
            candidates.append(os.path.normpath(os.path.join(os.path.dirname(self.controller_path), clip_path)))
        candidates.append(os.path.normpath(os.path.join(self.project_dir, clip_path)))
        candidates.append(os.path.normpath(os.path.join(os.getcwd(), clip_path)))
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return ""

    def start_node_preview(self, clip_path: str):
        self.stop_node_preview()
        resolved_clip = self.resolve_clip_path(clip_path)
        if not resolved_clip:
            self.node_preview_label.setText("No Preview")
            return
        try:
            clip = SceneSerializer.load_animation_clip(resolved_clip)
        except Exception:
            self.node_preview_label.setText("No Preview")
            return

        self.node_preview_frames = []
        self.node_preview_index = 0
        self.node_preview_loop = bool(clip.loop)

        if clip.type == "spritesheet" and clip.sheet_path:
            sheet_path = self.resolve_clip_path(clip.sheet_path)
            if sheet_path:
                sheet = QPixmap(sheet_path)
                if not sheet.isNull():
                    all_frames = []
                    x = int(clip.margin)
                    y = int(clip.margin)
                    w = int(max(1, clip.frame_width))
                    h = int(max(1, clip.frame_height))
                    spacing = int(max(0, clip.spacing))
                    while y + h <= sheet.height():
                        x = int(clip.margin)
                        while x + w <= sheet.width():
                            all_frames.append(sheet.copy(x, y, w, h))
                            x += w + spacing
                        y += h + spacing
                    start = max(0, int(clip.start_frame))
                    count = int(clip.frame_count)
                    if count > 0:
                        self.node_preview_frames = all_frames[start:start + count]
                    else:
                        self.node_preview_frames = all_frames[start:]
        elif clip.type == "images":
            for image_path in clip.image_paths:
                resolved_image = self.resolve_clip_path(image_path)
                if not resolved_image:
                    continue
                frame = QPixmap(resolved_image)
                if not frame.isNull():
                    self.node_preview_frames.append(frame)

        if not self.node_preview_frames:
            self.node_preview_label.setText("No Preview")
            return

        self.show_node_preview_frame()
        fps = max(0.1, float(clip.fps))
        self.node_preview_timer.start(int(1000.0 / fps))

    def show_node_preview_frame(self):
        if not self.node_preview_frames:
            self.node_preview_label.setText("No Preview")
            return
        if self.node_preview_index >= len(self.node_preview_frames):
            self.node_preview_index = 0
        frame = self.node_preview_frames[self.node_preview_index]
        scaled = frame.scaled(
            self.node_preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.node_preview_label.setPixmap(scaled)

    def advance_node_preview(self):
        if not self.node_preview_frames:
            self.stop_node_preview()
            return
        self.node_preview_index += 1
        if self.node_preview_index >= len(self.node_preview_frames):
            if self.node_preview_loop:
                self.node_preview_index = 0
            else:
                self.node_preview_index = len(self.node_preview_frames) - 1
                self.node_preview_timer.stop()
        self.show_node_preview_frame()

    def stop_node_preview(self):
        self.node_preview_timer.stop()
        self.node_preview_frames = []
        self.node_preview_index = 0
        self.node_preview_label.clear()
        self.node_preview_label.setText("No Preview")

    def replay_selected_node_preview(self):
        if not self.selected_node or not self.controller:
            return
        node_data = self.controller.nodes.get(self.selected_node.node_name)
        if not node_data:
            return
        self.start_node_preview(node_data.clip_path)

    def load_controller(self, path):
        self.controller_path = path
        try:
            self.controller = SceneSerializer.load_animation_controller(path)
            self.refresh_scene()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load controller: {e}")

    def refresh_scene(self):
        self.scene.clear()
        self.nodes = {}
        self.edges = []
        
        if not self.controller:
            return

        # Add nodes
        for name, node in self.controller.nodes.items():
            x, y = node.position
            item = NodeItem(name, x, y, self)
            self.scene.addItem(item)
            self.nodes[name] = item

        # Add Edges (Transitions)
        for transition in self.controller.transitions:
            start_node = self.nodes.get(transition.from_node)
            end_node = self.nodes.get(transition.to_node)
            if start_node and end_node:
                has_opposite = any(
                    t.from_node == transition.to_node and t.to_node == transition.from_node
                    for t in self.controller.transitions
                )
                offset_sign = 1 if has_opposite else 0
                edge = EdgeItem(start_node, end_node, transition, offset_sign)
                self.scene.addItem(edge)
                self.edges.append(edge)

    def update_edges(self, node_item):
        for edge in self.edges:
            if edge.start_item == node_item or edge.end_item == node_item:
                edge.update_position()

    def add_node(self):
        if not self.controller:
            return
        # Find unique name
        base_name = "NewState"
        name = base_name
        i = 1
        while name in self.controller.nodes:
            name = f"{base_name}{i}"
            i += 1
            
        self.controller.add_node(name, "", (100, 100))
        self.refresh_scene()

    def delete_selected_node(self):
        if not self.controller or not self.selected_node:
            return

        node_name = self.selected_node.node_name
        if node_name == AnimationController.ROOT_NODE_NAME:
            QMessageBox.warning(self, "Warning", "Root node cannot be deleted.")
            return
        self.controller.remove_node(node_name)
        self.selected_node = None
        self.props_panel.setEnabled(False)
        self.refresh_scene()

    def delete_selected_edge(self):
        if not self.controller or not self.selected_edge:
            return
        try:
            self.controller.transitions.remove(self.selected_edge.transition)
        except ValueError:
            return
        self.selected_edge = None
        self.props_panel.setEnabled(False)
        self.refresh_scene()

    def delete_selected_item(self):
        if self.selected_edge:
            self.delete_selected_edge()
            return
        self.delete_selected_node()

    def start_transition_drag(self, node_item):
        self.is_dragging_transition = True
        self.drag_start_node = node_item
        
        start_pt = node_item.sceneBoundingRect().center()
        self.drag_line = QGraphicsLineItem(start_pt.x(), start_pt.y(), start_pt.x(), start_pt.y())
        self.drag_line.setPen(QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine))
        self.scene.addItem(self.drag_line)

    def update_transition_drag(self, pos):
        if self.drag_line and self.drag_start_node:
            start_pt = self.drag_start_node.sceneBoundingRect().center()
            self.drag_line.setLine(start_pt.x(), start_pt.y(), pos.x(), pos.y())
            # Put the line below nodes so it doesn't block clicks
            self.drag_line.setZValue(-1)

    def cancel_transition_drag(self):
        self.is_dragging_transition = False
        if self.drag_line:
            try:
                self.scene.removeItem(self.drag_line)
            except RuntimeError:
                pass
            self.drag_line = None
        self.drag_start_node = None

    def finish_transition_drag(self, item):
        if isinstance(item, QGraphicsTextItem):
            item = item.parentItem()

        if isinstance(item, NodeItem) and item != self.drag_start_node:
            start_name = self.drag_start_node.node_name
            end_name = item.node_name
            changed = self.controller.add_transition(start_name, end_name)
            if changed:
                self.cancel_transition_drag()
                self.refresh_scene()
                return
            QMessageBox.information(self, "Info", "Transition is not allowed.")
        self.cancel_transition_drag()

    def save_controller(self):
        if not self.controller or not self.controller_path:
            return
            
        # Update positions from scene
        for name, item in self.nodes.items():
            if name in self.controller.nodes:
                self.controller.nodes[name].position = (item.x(), item.y())
                
        try:
            SceneSerializer.save_animation_controller(self.controller_path, self.controller)
            print(f"Saved controller to {self.controller_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save controller: {e}")

class ClipEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clip = None
        self.clip_path = None
        self.project_dir = os.getcwd() # Should be passed in
        
        # Preview State
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.advance_preview)
        self.preview_frames = []
        self.current_preview_idx = 0
        self.is_playing = False
        
        layout = QHBoxLayout(self)
        
        # Left: Properties
        props_group = QGroupBox("Properties")
        form = QFormLayout(props_group)
        
        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0.1, 240.0)
        self.fps_spin.setValue(12.0)
        self.fps_spin.valueChanged.connect(self.on_prop_changed)
        
        self.loop_chk = QCheckBox()
        self.loop_chk.stateChanged.connect(self.on_prop_changed)
        
        self.type_combo = QComboBox()
        self.type_combo.addItem("Spritesheet", "spritesheet")
        self.type_combo.addItem("Image Sequence", "images")
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        
        form.addRow("FPS", self.fps_spin)
        form.addRow("Loop", self.loop_chk)
        form.addRow("Type", self.type_combo)
        
        # Spritesheet props
        self.ss_widget = QWidget()
        ss_form = QFormLayout(self.ss_widget)
        self.sheet_path = QLineEdit()
        self.browse_sheet_btn = QPushButton("...")
        self.browse_sheet_btn.setFixedWidth(30)
        self.browse_sheet_btn.clicked.connect(self.browse_sheet)
        
        sheet_layout = QHBoxLayout()
        sheet_layout.setContentsMargins(0, 0, 0, 0)
        sheet_layout.addWidget(self.sheet_path)
        sheet_layout.addWidget(self.browse_sheet_btn)

        self.frame_w = QSpinBox(); self.frame_w.setRange(1, 8192); self.frame_w.setValue(32)
        self.frame_h = QSpinBox(); self.frame_h.setRange(1, 8192); self.frame_h.setValue(32)
        self.start_frame = QSpinBox(); self.start_frame.setRange(0, 9999)
        self.frame_count = QSpinBox(); self.frame_count.setRange(0, 9999)
        
        for w in [self.sheet_path, self.frame_w, self.frame_h, self.start_frame, self.frame_count]:
             if isinstance(w, QLineEdit): w.textChanged.connect(self.on_prop_changed)
             else: w.valueChanged.connect(self.on_prop_changed)
             
        ss_form.addRow("Sheet Path", sheet_layout)
        ss_form.addRow("Frame W", self.frame_w)
        ss_form.addRow("Frame H", self.frame_h)
        ss_form.addRow("Start", self.start_frame)
        ss_form.addRow("Count", self.frame_count)
        
        form.addRow(self.ss_widget)

        # Image Sequence props
        self.img_seq_widget = QWidget()
        img_seq_layout = QVBoxLayout(self.img_seq_widget)
        img_seq_layout.setContentsMargins(0, 0, 0, 0)
        
        btn_layout = QHBoxLayout()
        self.add_images_btn = QPushButton("Add Images")
        self.add_images_btn.clicked.connect(self.add_images)
        self.clear_images_btn = QPushButton("Clear")
        self.clear_images_btn.clicked.connect(self.clear_images)
        btn_layout.addWidget(self.add_images_btn)
        btn_layout.addWidget(self.clear_images_btn)
        
        self.images_list = QListWidget()
        
        img_seq_layout.addLayout(btn_layout)
        img_seq_layout.addWidget(self.images_list)
        
        form.addRow(self.img_seq_widget)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_clip)
        form.addRow(save_btn)
        
        layout.addWidget(props_group)
        
        # Right: Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_lbl = QLabel("Preview")
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setMinimumSize(300, 300)
        
        ctrl_layout = QHBoxLayout()
        c = theme_icon_color()
        self.play_btn = QPushButton()
        self.play_btn.setIcon(qta.icon("fa5s.play", color=c))
        self.pause_btn = QPushButton()
        self.pause_btn.setIcon(qta.icon("fa5s.pause", color=c))
        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(qta.icon("fa5s.stop", color=c))
        
        self.play_btn.clicked.connect(self.play_preview)
        self.pause_btn.clicked.connect(self.pause_preview)
        self.stop_btn.clicked.connect(self.stop_preview)
        
        ctrl_layout.addWidget(self.play_btn)
        ctrl_layout.addWidget(self.pause_btn)
        ctrl_layout.addWidget(self.stop_btn)
        
        preview_layout.addWidget(self.preview_lbl)
        preview_layout.addLayout(ctrl_layout)
        layout.addWidget(preview_group)

    def load_clip(self, path):
        self.clip_path = path
        self.stop_preview()
        self.preview_frames.clear()
        try:
            self.clip = SceneSerializer.load_animation_clip(path)
            self.refresh_ui()
            self.extract_preview_frames()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load clip: {e}")

    def _to_project_relative(self, path):
        """Convert an absolute path to a project-relative portable path (forward slashes)."""
        abs_project = os.path.abspath(self.project_dir)
        abs_path = os.path.abspath(path)
        try:
            rel = os.path.relpath(abs_path, abs_project)
            if not rel.startswith(".."):
                return ResourceManager.portable_path(rel)
        except ValueError:
            pass
        return ResourceManager.portable_path(abs_path)

    def browse_sheet(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Spritesheet", self.project_dir, "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.sheet_path.setText(self._to_project_relative(path))
            self.on_prop_changed()

    def add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Images", self.project_dir, "Images (*.png *.jpg *.jpeg *.bmp)")
        if paths:
            for path in paths:
                rel_path = self._to_project_relative(path)
                if rel_path not in self.clip.image_paths:
                    self.clip.image_paths.append(rel_path)
            
            self.refresh_ui()
            self.on_prop_changed()

    def clear_images(self):
        if self.clip:
            self.clip.image_paths = []
            self.refresh_ui()
            self.on_prop_changed()

    def refresh_ui(self):
        if not self.clip:
            return
        self.fps_spin.setValue(self.clip.fps)
        self.loop_chk.setChecked(self.clip.loop)
        idx = self.type_combo.findData(self.clip.type)
        if idx >= 0: self.type_combo.setCurrentIndex(idx)
        
        if self.clip.type == "spritesheet":
            self.sheet_path.setText(self.clip.sheet_path)
            self.frame_w.setValue(self.clip.frame_width)
            self.frame_h.setValue(self.clip.frame_height)
            self.start_frame.setValue(self.clip.start_frame)
            self.frame_count.setValue(self.clip.frame_count)
            self.ss_widget.setVisible(True)
            self.img_seq_widget.setVisible(False)
        else:
            self.ss_widget.setVisible(False)
            self.img_seq_widget.setVisible(True)
            self.images_list.clear()
            for path in self.clip.image_paths:
                self.images_list.addItem(path)

    def on_prop_changed(self):
        if not self.clip: return
        self.clip.fps = self.fps_spin.value()
        self.clip.loop = self.loop_chk.isChecked()
        self.clip.type = self.type_combo.currentData()
        
        if self.clip.type == "spritesheet":
            self.clip.sheet_path = self.sheet_path.text()
            self.clip.frame_width = self.frame_w.value()
            self.clip.frame_height = self.frame_h.value()
            self.clip.start_frame = self.start_frame.value()
            self.clip.frame_count = self.frame_count.value()
            
        self.extract_preview_frames()
        if self.is_playing:
            self.play_preview() # Restart timer with new FPS

    def extract_preview_frames(self):
        self.preview_frames.clear()
        self.current_preview_idx = 0
        if not self.clip:
            self.preview_lbl.setPixmap(QPixmap())
            return
            
        if self.clip.type == "spritesheet" and self.clip.sheet_path:
            os_sheet = ResourceManager.to_os_path(self.clip.sheet_path)
            abs_path = os_sheet if os.path.isabs(os_sheet) else os.path.join(self.project_dir, os_sheet)
            if os.path.exists(abs_path):
                pixmap = QPixmap(abs_path)
                if not pixmap.isNull():
                    w, h = self.clip.frame_width, self.clip.frame_height
                    if w > 0 and h > 0:
                        margin = getattr(self.clip, 'margin', 0)
                        spacing = getattr(self.clip, 'spacing', 0)
                        x, y = margin, margin
                        frames = []
                        while y + h <= pixmap.height():
                            x = margin
                            while x + w <= pixmap.width():
                                frames.append(pixmap.copy(x, y, w, h))
                                x += w + spacing
                            y += h + spacing
                            
                        start = self.clip.start_frame
                        count = self.clip.frame_count if self.clip.frame_count > 0 else len(frames)
                        end = min(len(frames), start + count)
                        self.preview_frames = frames[start:end]
                        
        elif self.clip.type == "images":
            for p in self.clip.image_paths:
                os_p = ResourceManager.to_os_path(p)
                abs_p = os_p if os.path.isabs(os_p) else os.path.join(self.project_dir, os_p)
                if os.path.exists(abs_p):
                    px = QPixmap(abs_p)
                    if not px.isNull():
                        self.preview_frames.append(px)
                        
        self.show_current_preview_frame()

    def show_current_preview_frame(self):
        if not self.preview_frames:
            self.preview_lbl.setText("No Preview")
            return
        if self.current_preview_idx >= len(self.preview_frames):
            self.current_preview_idx = 0
            
        px = self.preview_frames[self.current_preview_idx]
        scaled = px.scaled(self.preview_lbl.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self.preview_lbl.setPixmap(scaled)

    def advance_preview(self):
        if not self.preview_frames: return
        self.current_preview_idx += 1
        if self.current_preview_idx >= len(self.preview_frames):
            if self.clip.loop:
                self.current_preview_idx = 0
            else:
                self.current_preview_idx = len(self.preview_frames) - 1
                self.pause_preview()
        self.show_current_preview_frame()

    def play_preview(self):
        if not self.preview_frames: return
        # Reset to beginning when play is clicked
        self.current_preview_idx = 0
        self.is_playing = True
        self.show_current_preview_frame()
        fps = max(0.1, self.clip.fps)
        self.preview_timer.start(int(1000 / fps))

    def pause_preview(self):
        self.is_playing = False
        self.preview_timer.stop()

    def stop_preview(self):
        self.is_playing = False
        self.preview_timer.stop()
        self.current_preview_idx = 0
        self.show_current_preview_frame()

    def on_type_changed(self):
        is_sheet = self.type_combo.currentData() == "spritesheet"
        self.ss_widget.setVisible(is_sheet)
        self.img_seq_widget.setVisible(not is_sheet)
        self.on_prop_changed()

    def save_clip(self):
        if not self.clip or not self.clip_path: return
        try:
            SceneSerializer.save_animation_clip(self.clip_path, self.clip)
            print(f"Saved clip to {self.clip_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save clip: {e}")

class AnimationEditor(QMainWindow):
    def __init__(self, parent=None, project_dir="."):
        super().__init__(parent)
        self.setWindowTitle("Animation Editor")
        self.resize(1000, 700)
        self.project_dir = project_dir
        
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        
        open_act = QAction("Open File...", self)
        open_act.triggered.connect(self.open_file_dialog)
        self.toolbar.addAction(open_act)
        
        self.central_stack = QWidget() # To switch between editors
        self.setCentralWidget(self.central_stack)
        
        self.layout = QVBoxLayout(self.central_stack)
        
        self.controller_editor = ControllerEditorWidget(self)
        self.clip_editor = ClipEditorWidget(self)
        self.clip_editor.project_dir = project_dir
        
        self.layout.addWidget(self.controller_editor)
        self.layout.addWidget(self.clip_editor)
        
        self.controller_editor.hide()
        self.clip_editor.hide()

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Animation File", self.project_dir, "Animation Files (*.actrl *.anim)")
        if path:
            self.open_file(path)

    def open_file(self, path):
        self.clip_editor.project_dir = self.project_dir
        self.controller_editor.project_dir = self.project_dir
        if path.endswith(".actrl"):
            self.controller_editor.load_controller(path)
            self.controller_editor.show()
            self.clip_editor.hide()
            self.setWindowTitle(f"Animation Editor - {os.path.basename(path)}")
        elif path.endswith(".anim"):
            self.clip_editor.load_clip(path)
            self.clip_editor.show()
            self.controller_editor.hide()
            self.setWindowTitle(f"Animation Editor - {os.path.basename(path)}")
