from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QScrollArea, QSizePolicy
from PyQt6.QtGui import QPixmap, QIcon, QImageReader
from PyQt6.QtCore import Qt, QSize, QTimer
import pygame
import os
import json
from core.resources import ResourceManager

class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setMinimumWidth(300)
        
        # Header
        self.header_label = QLabel("Preview")
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #333; color: white;")
        self.layout.addWidget(self.header_label)
        
        # Container for preview widgets
        self.preview_container = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.preview_container)
        
        # Current active preview widget
        self.current_preview = None
        
        # Supported extensions
        self.image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
        self.sound_extensions = ['.wav', '.ogg', '.mp3']
        self.anim_extensions = ['.anim']

    def set_file(self, file_path):
        self.clear()
        
        if not file_path or not os.path.isfile(file_path):
            self.header_label.setText("No Selection")
            return
            
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        self.header_label.setText(os.path.basename(file_path))
        
        if ext in self.image_extensions:
            self.current_preview = ImagePreview(self)
            self.current_preview.load(file_path)
            self.preview_layout.addWidget(self.current_preview)
        elif ext in self.sound_extensions:
            self.current_preview = SoundPreview(self)
            self.current_preview.load(file_path)
            self.preview_layout.addWidget(self.current_preview)
        elif ext in self.anim_extensions:
            self.current_preview = AnimationClipPreview(self)
            self.current_preview.load(file_path)
            self.preview_layout.addWidget(self.current_preview)
        else:
            label = QLabel("No preview available")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_layout.addWidget(label)
            self.current_preview = label

    def clear(self):
        # Remove current preview widget
        if self.current_preview:
            # If it has a cleanup method (like stopping sound), call it
            if hasattr(self.current_preview, 'cleanup'):
                self.current_preview.cleanup()
            
            self.preview_layout.removeWidget(self.current_preview)
            self.current_preview.deleteLater()
            self.current_preview = None
        
        self.header_label.setText("Preview")

class ImagePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Use Ignored policy to prevent the image from forcing the widget size
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.layout.addWidget(self.image_label, 1) # Give it all available space
        
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.info_label, 0) # No stretch
        
        self.original_pixmap = None

    def load(self, path):
        self.original_pixmap = QPixmap(path)
        if not self.original_pixmap.isNull():
            self.update_preview()
            self.info_label.setText(f"{self.original_pixmap.width()}x{self.original_pixmap.height()}")
        else:
            self.image_label.setText("Failed to load image")
            self.image_label.setPixmap(QPixmap())
            self.info_label.setText("")

    def resizeEvent(self, event):
        self.update_preview()
        super().resizeEvent(event)

    def update_preview(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            # Scale to available size
            size = self.image_label.size()
            if size.width() > 1 and size.height() > 1:
                scaled = self.original_pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled)

    def cleanup(self):
        pass

class SoundPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)
        
        controls = QHBoxLayout()
        
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.play)
        controls.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop)
        controls.addWidget(self.stop_btn)
        
        self.layout.addLayout(controls)
        
        self.sound = None
        self.channel = None

    def load(self, path):
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as e:
                self.status_label.setText(f"Audio Error: {e}")
                self.play_btn.setEnabled(False)
                return

        try:
            self.sound = pygame.mixer.Sound(path)
            self.status_label.setText("Loaded")
        except Exception as e:
            self.status_label.setText("Error loading sound")
            print(f"Error loading sound {path}: {e}")
            self.play_btn.setEnabled(False)

    def play(self):
        if self.sound:
            self.channel = self.sound.play()
            self.status_label.setText("Playing...")

    def stop(self):
        if self.channel:
            self.channel.stop()
            self.status_label.setText("Stopped")

    def cleanup(self):
        self.stop()

class AnimationClipPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.preview_label = QLabel("No Preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(220, 180)
        self.layout.addWidget(self.preview_label)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.play_btn.clicked.connect(self.play)
        self.pause_btn.clicked.connect(self.pause)
        self.stop_btn.clicked.connect(self.stop)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.stop_btn)
        self.layout.addLayout(controls)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_frame)
        self.frames = []
        self.index = 0
        self.loop = True
        self.fps = 12.0
        self.anim_path = ""

    def load(self, path):
        self.stop()
        self.frames = []
        self.index = 0
        self.anim_path = path
        self.preview_label.setText("No Preview")
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception:
            self.preview_label.setText("Invalid .anim file")
            return

        clip_type = data.get("type", "spritesheet")
        self.loop = bool(data.get("loop", True))
        self.fps = max(0.1, float(data.get("fps", 12.0)))
        base_dir = os.path.dirname(path)

        if clip_type == "spritesheet":
            sheet_path = self._resolve_path(base_dir, data.get("sheet_path", ""))
            if sheet_path:
                sheet = QPixmap(sheet_path)
                if not sheet.isNull():
                    frame_w = int(max(1, data.get("frame_width", 32)))
                    frame_h = int(max(1, data.get("frame_height", 32)))
                    margin = int(max(0, data.get("margin", 0)))
                    spacing = int(max(0, data.get("spacing", 0)))
                    all_frames = []
                    y = margin
                    while y + frame_h <= sheet.height():
                        x = margin
                        while x + frame_w <= sheet.width():
                            all_frames.append(sheet.copy(x, y, frame_w, frame_h))
                            x += frame_w + spacing
                        y += frame_h + spacing
                    start = int(max(0, data.get("start_frame", 0)))
                    count = int(max(0, data.get("frame_count", 0)))
                    if count > 0:
                        self.frames = all_frames[start:start + count]
                    else:
                        self.frames = all_frames[start:]
        elif clip_type == "images":
            for image_path in data.get("image_paths", []):
                resolved = self._resolve_path(base_dir, image_path)
                if not resolved:
                    continue
                frame = QPixmap(resolved)
                if not frame.isNull():
                    self.frames.append(frame)

        if not self.frames:
            self.preview_label.setText("No Preview")
            return
        self.show_frame()
        self.play()

    def _resolve_path(self, base_dir, asset_path):
        if not asset_path:
            return ""
        normalized = ResourceManager.to_os_path(asset_path)
        if os.path.isabs(normalized) and os.path.exists(normalized):
            return normalized
        candidate = os.path.normpath(os.path.join(base_dir, normalized))
        if os.path.exists(candidate):
            return candidate
        project_root = os.environ.get("AXISPY_PROJECT_PATH", "")
        if project_root:
            candidate = os.path.normpath(os.path.join(project_root, normalized))
            if os.path.exists(candidate):
                return candidate
        candidate = os.path.normpath(os.path.join(os.getcwd(), normalized))
        if os.path.exists(candidate):
            return candidate
        return ""

    def resizeEvent(self, event):
        self.show_frame()
        super().resizeEvent(event)

    def show_frame(self):
        if not self.frames:
            self.preview_label.setText("No Preview")
            return
        if self.index >= len(self.frames):
            self.index = 0
        frame = self.frames[self.index]
        scaled = frame.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled)

    def advance_frame(self):
        if not self.frames:
            self.stop()
            return
        self.index += 1
        if self.index >= len(self.frames):
            if self.loop:
                self.index = 0
            else:
                self.index = len(self.frames) - 1
                self.timer.stop()
        self.show_frame()

    def play(self):
        if not self.frames:
            return
        if not self.loop and self.index >= len(self.frames) - 1:
            self.index = 0
            self.show_frame()
        self.timer.start(int(1000.0 / self.fps))

    def pause(self):
        self.timer.stop()

    def stop(self):
        self.timer.stop()
        self.index = 0
        self.show_frame()

    def cleanup(self):
        self.timer.stop()
