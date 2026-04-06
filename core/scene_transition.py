"""Scene transition effects — fade-out / fade-in overlay.

Usage from the player loop::

    transition = SceneTransition(duration=0.5, color=(0, 0, 0))
    transition.start_out()   # fade to black
    # ... each frame:
    transition.update(frame_dt)
    transition.draw(surface)
    if transition.is_done():
        # swap scene, then:
        transition.start_in()  # fade from black
"""
from __future__ import annotations
import pygame


class SceneTransition:
    """Simple full-screen colour overlay that fades in or out."""

    def __init__(self, duration: float = 0.4, color: tuple = (0, 0, 0)):
        self.duration = max(0.01, float(duration))
        self.color = color
        self._alpha = 0.0        # 0 = transparent, 255 = opaque
        self._direction = 0      # +1 = fading out (to opaque), -1 = fading in, 0 = idle
        self._done = True
        self._overlay: pygame.Surface | None = None

    def start_out(self):
        """Begin fading *to* the overlay colour (screen goes dark)."""
        self._alpha = 0.0
        self._direction = 1
        self._done = False

    def start_in(self):
        """Begin fading *from* the overlay colour (screen appears)."""
        self._alpha = 255.0
        self._direction = -1
        self._done = False

    def is_active(self) -> bool:
        return not self._done

    def is_done(self) -> bool:
        return self._done

    def is_fade_out_done(self) -> bool:
        """True when a fade-out has completed (screen is fully opaque)."""
        return self._done and self._direction == 1

    def is_fade_in_done(self) -> bool:
        """True when a fade-in has completed (screen is fully transparent)."""
        return self._done and self._direction == -1

    def update(self, dt: float):
        if self._done:
            return
        speed = 255.0 / self.duration
        self._alpha += speed * dt * self._direction
        if self._direction > 0 and self._alpha >= 255.0:
            self._alpha = 255.0
            self._done = True
        elif self._direction < 0 and self._alpha <= 0.0:
            self._alpha = 0.0
            self._done = True

    def draw(self, surface: pygame.Surface):
        """Draw the overlay on top of *surface*.  No-op when fully transparent."""
        a = int(max(0, min(255, self._alpha)))
        if a <= 0:
            return
        w, h = surface.get_size()
        if self._overlay is None or self._overlay.get_size() != (w, h):
            self._overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        self._overlay.fill((*self.color[:3], a))
        surface.blit(self._overlay, (0, 0))
