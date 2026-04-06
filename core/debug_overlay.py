"""On-screen debug overlay for runtime diagnostics.

Toggle with ``DebugOverlay.enabled = True`` or bind to a key in a script.

Displays:
- FPS (smoothed)
- Entity count
- Per-system update timings (if profiling is enabled on the World)

Usage::

    from core.debug_overlay import DebugOverlay

    # In player or script setup:
    DebugOverlay.enabled = True        # show overlay
    DebugOverlay.show_fps = True
    DebugOverlay.show_entity_count = True
    DebugOverlay.show_system_timings = True
"""
from __future__ import annotations
import time
import pygame
from collections import deque


class DebugOverlay:
    """Static debug overlay drawn on top of the game surface."""

    enabled: bool = False
    show_fps: bool = True
    show_entity_count: bool = True
    show_system_timings: bool = True
    font_size: int = 14
    color: tuple = (0, 255, 0)
    bg_color: tuple = (0, 0, 0, 160)
    position: tuple = (8, 8)

    _font: pygame.font.Font | None = None
    _fps_buffer: deque = deque(maxlen=30)
    _system_timings: dict[str, float] = {}
    _entity_count: int = 0
    _last_time: float = 0.0

    @classmethod
    def update(cls, dt: float, world=None):
        """Call once per frame to collect stats."""
        if not cls.enabled:
            return
        # FPS
        if dt > 0:
            cls._fps_buffer.append(1.0 / dt)
        # Entity count
        if world is not None:
            cls._entity_count = len(world.entities) if hasattr(world, "entities") else 0
            # System timings from profiling data if available
            if hasattr(world, "_system_timings"):
                cls._system_timings = dict(world._system_timings)

    @classmethod
    def draw(cls, surface: pygame.Surface):
        """Draw the overlay onto *surface*.  Call after all game rendering."""
        if not cls.enabled:
            return
        if cls._font is None:
            try:
                cls._font = pygame.font.SysFont("consolas,courier,monospace", cls.font_size)
            except Exception:
                cls._font = pygame.font.Font(None, cls.font_size)

        lines: list[str] = []

        if cls.show_fps and cls._fps_buffer:
            avg_fps = sum(cls._fps_buffer) / len(cls._fps_buffer)
            lines.append(f"FPS: {avg_fps:.0f}")

        if cls.show_entity_count:
            lines.append(f"Entities: {cls._entity_count}")

        if cls.show_system_timings and cls._system_timings:
            lines.append("--- Systems ---")
            for name, ms in sorted(cls._system_timings.items()):
                lines.append(f"  {name}: {ms:.2f}ms")

        if not lines:
            return

        x, y = cls.position
        line_h = cls.font_size + 2
        # Compute background rect
        max_w = 0
        rendered: list[pygame.Surface] = []
        for line in lines:
            surf = cls._font.render(line, True, cls.color)
            rendered.append(surf)
            max_w = max(max_w, surf.get_width())

        total_h = line_h * len(lines)
        bg = pygame.Surface((max_w + 12, total_h + 8), pygame.SRCALPHA)
        bg.fill(cls.bg_color)
        surface.blit(bg, (x - 4, y - 2))

        for i, surf in enumerate(rendered):
            surface.blit(surf, (x, y + i * line_h))

    @classmethod
    def reset(cls):
        """Reset all collected stats."""
        cls._fps_buffer.clear()
        cls._system_timings.clear()
        cls._entity_count = 0
        cls._font = None
