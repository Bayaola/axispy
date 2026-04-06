import pygame
from core.ecs import Component
from core.resources import ResourceManager
from core.logger import get_logger

_sprite_logger = get_logger("components")

_transform_type = None

def _get_transform_type():
    global _transform_type
    if _transform_type is None:
        from core.components.transform import Transform
        _transform_type = Transform
    return _transform_type


class SpriteRenderer(Component):
    def __init__(self, color=(255, 255, 255), width=50, height=50, image_path=None):
        self.entity = None
        self.color = color
        self._local_width = width
        self._local_height = height
        self.image_path = image_path
        
        if self.image_path:
            self.load_image(self.image_path)
        elif not ResourceManager._headless:
            self.image = pygame.Surface((width, height), pygame.SRCALPHA)
            self.image.fill(color)

    @property
    def width(self):
        scale = 1.0
        if self.entity:
            t = self.entity.get_component(_get_transform_type())
            if t:
                scale = t.scale_x
        return abs(self._local_width * scale)

    @width.setter
    def width(self, value):
        if self.entity:
            t = self.entity.get_component(_get_transform_type())
            if t and self._local_width != 0:
                current_sign = 1.0 if t.scale_x >= 0 else -1.0
                t.scale_x = (value / self._local_width) * current_sign
                return
        # Fallback: update local size if no entity or 0 width
        self._local_width = value
        if not self.image_path and not ResourceManager._headless:
             self.image = pygame.Surface((int(self._local_width), int(self._local_height)), pygame.SRCALPHA)
             self.image.fill(self.color)

    @property
    def height(self):
        scale = 1.0
        if self.entity:
            t = self.entity.get_component(_get_transform_type())
            if t:
                scale = t.scale_y
        return abs(self._local_height * scale)

    @height.setter
    def height(self, value):
        if self.entity:
            t = self.entity.get_component(_get_transform_type())
            if t and self._local_height != 0:
                current_sign = 1.0 if t.scale_y >= 0 else -1.0
                t.scale_y = (value / self._local_height) * current_sign
                return
        # Fallback
        self._local_height = value
        if not self.image_path and not ResourceManager._headless:
             self.image = pygame.Surface((int(self._local_width), int(self._local_height)), pygame.SRCALPHA)
             self.image.fill(self.color)

    def load_image(self, path):
        img = ResourceManager.load_image(path)
        if img:
            self.image = img
            self._local_width = img.get_width()
            self._local_height = img.get_height()
            self.image_path = path
        elif not ResourceManager._headless:
            _sprite_logger.warning("Failed to load image", path=path)
            # Fallback to colored rect if not already set?
            # Or keep existing image if valid?
            # For now, let's recreate the default surface if loading fails
            self.image = pygame.Surface((self._local_width, self._local_height), pygame.SRCALPHA)
            self.image.fill(self.color)
