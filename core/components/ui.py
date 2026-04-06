
import pygame
from core.ecs import Component
from core.resources import ResourceManager
from core.vector import Vector2

class UIComponent(Component):
    """Base class for all UI components"""
    pass

class TextRenderer(UIComponent):
    def __init__(self, text="Text", font_size=24, color=(255, 255, 255), font_path=None):
        self.entity = None
        self.text = text
        self.font_size = font_size
        self.color = color
        self.font_path = font_path

class ButtonComponent(UIComponent):
    def __init__(self, text="Button", width=100.0, height=40.0, 
                 normal_color=(100, 100, 100), hover_color=(150, 150, 150), 
                 pressed_color=(50, 50, 50), text_color=(255, 255, 255)):
        self.entity = None
        self.text = text
        self.width = width
        self.height = height
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.pressed_color = pressed_color
        self.text_color = text_color
        self.is_hovered = False
        self.is_pressed = False

class TextInputComponent(UIComponent):
    def __init__(self, text="", placeholder="Enter text...", width=200.0, height=30.0,
                 bg_color=(255, 255, 255), text_color=(0, 0, 0)):
        self.entity = None
        self.text = text
        self.placeholder = placeholder
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.text_color = text_color
        self.is_focused = False
        self.cursor_visible = False
        self.cursor_timer = 0.0

class SliderComponent(UIComponent):
    def __init__(self, value=0.0, min_value=0.0, max_value=1.0, width=200.0, height=20.0,
                 track_color=(100, 100, 100), handle_color=(200, 200, 200)):
        self.entity = None
        self.value = value
        self.min_value = min_value
        self.max_value = max_value
        self.width = width
        self.height = height
        self.track_color = track_color
        self.handle_color = handle_color
        self.is_dragging = False

class ProgressBarComponent(UIComponent):
    def __init__(self, value=0.5, min_value=0.0, max_value=1.0, width=200.0, height=20.0,
                 bg_color=(100, 100, 100), fill_color=(0, 200, 0)):
        self.entity = None
        self.value = value
        self.min_value = min_value
        self.max_value = max_value
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.fill_color = fill_color

class CheckBoxComponent(UIComponent):
    def __init__(self, checked=False, size=20.0, 
                 checked_color=(0, 200, 0), unchecked_color=(200, 200, 200)):
        self.entity = None
        self.checked = checked
        self.size = size
        self.checked_color = checked_color
        self.unchecked_color = unchecked_color

class ImageRenderer(UIComponent):
    def __init__(self, image_path=None, color=(255, 255, 255), width=50.0, height=50.0):
        self.entity = None
        self.image_path = image_path
        self.color = color
        self.width = width
        self.height = height
        self.image = None
        
        if self.image_path:
            self.load_image(self.image_path)
        elif not ResourceManager._headless:
            self._create_default_surface()

    def load_image(self, path):
        img = ResourceManager.load_image(path)
        if img:
            self.image = img
            self.width = float(img.get_width())
            self.height = float(img.get_height())
            self.image_path = path
        elif not ResourceManager._headless:
            self._create_default_surface()

    def _create_default_surface(self):
        if ResourceManager._headless:
            return
        self.image = pygame.Surface((int(self.width), int(self.height)), pygame.SRCALPHA)
        self.image.fill(self.color)

class HBoxContainerComponent(UIComponent):
    def __init__(self, spacing=5.0):
        self.entity = None
        self.spacing = spacing
        self.width = 0.0
        self.height = 0.0

class VBoxContainerComponent(UIComponent):
    def __init__(self, spacing=5.0):
        self.entity = None
        self.spacing = spacing
        self.width = 0.0
        self.height = 0.0

class GridBoxContainerComponent(UIComponent):
    def __init__(self, columns=2, spacing_x=5.0, spacing_y=5.0):
        self.entity = None
        self.columns = columns
        self.spacing_x = spacing_x
        self.spacing_y = spacing_y
        self.width = 0.0
        self.height = 0.0
