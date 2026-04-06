"""2D Light components for point lights, spot lights, and light occluders.

Attach a ``PointLight2D`` or ``SpotLight2D`` to an entity with a Transform
to create a light source. Add ``LightOccluder2D`` to entities that should
block light and cast shadows.

The ``LightingSystem`` renders an ambient + light overlay each frame.

Usage::

    entity = world.create_entity("torch")
    entity.add_component(Transform(x=100, y=200))
    entity.add_component(PointLight2D(color=(255, 200, 100), radius=300, intensity=1.0))

    wall = world.create_entity("wall")
    wall.add_component(Transform(x=300, y=200))
    wall.add_component(LightOccluder2D(shape="box", width=50, height=200))
"""
from __future__ import annotations
from core.ecs import Component


class PointLight2D(Component):
    """Omnidirectional 2D point light."""

    def __init__(self, color: tuple = (255, 255, 255), radius: float = 200.0,
                 intensity: float = 1.0, falloff: float = 2.0):
        self.color = color          # RGB
        self.radius = max(1.0, float(radius))
        self.intensity = max(0.0, float(intensity))
        self.falloff = max(0.1, float(falloff))  # Exponent for attenuation curve


class SpotLight2D(Component):
    """Directional 2D spot light with a cone angle."""

    def __init__(self, color: tuple = (255, 255, 255), radius: float = 300.0,
                 intensity: float = 1.0, falloff: float = 2.0,
                 angle: float = 0.0, cone_angle: float = 45.0,
                 offset_x: float = 0.0, offset_y: float = 0.0):
        self.color = color
        self.radius = max(1.0, float(radius))
        self.intensity = max(0.0, float(intensity))
        self.falloff = max(0.1, float(falloff))
        self.angle = float(angle)            # Direction in degrees (0 = right)
        self.cone_angle = max(1.0, min(180.0, float(cone_angle)))  # Half-angle of cone
        self.offset_x = float(offset_x)
        self.offset_y = float(offset_y)


class LightOccluder2D(Component):
    """Light occluder that blocks light and casts shadows.

    Supports three shape types:
    - ``"box"``     — axis-aligned rectangle (width × height)
    - ``"circle"``  — circle defined by radius
    - ``"polygon"`` — arbitrary convex/concave polygon (list of Vector2 points)

    When added via the inspector with shape ``"box"`` or ``"circle"``, the size
    is automatically derived from the entity's ``SpriteRenderer`` if present.
    """

    SHAPE_BOX = "box"
    SHAPE_CIRCLE = "circle"
    SHAPE_POLYGON = "polygon"

    def __init__(self, shape: str = "box", width: float = 50.0, height: float = 50.0,
                 radius: float = 25.0, points: list | None = None,
                 offset_x: float = 0.0, offset_y: float = 0.0,
                 receive_light: bool = False, receive_shadow: bool = False,
                 rotation: float = 0.0):
        self.shape = shape if shape in ("box", "circle", "polygon") else "box"
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))
        self.radius = max(1.0, float(radius))
        self.offset_x = float(offset_x)
        self.offset_y = float(offset_y)
        self.receive_light = bool(receive_light)
        self.receive_shadow = bool(receive_shadow)
        self.rotation = float(rotation)
        # Polygon points (local space, relative to entity transform + offset)
        self._points: list = []
        self.points = points

    @property
    def points(self):
        return self._points

    @points.setter
    def points(self, value):
        from core.vector import Vector2
        raw = value or []
        converted = []
        for p in raw:
            if isinstance(p, Vector2):
                converted.append(Vector2(float(p.x), float(p.y)))
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                converted.append(Vector2(float(p[0]), float(p[1])))
        if self.shape == "polygon" and len(converted) < 3:
            converted = [
                Vector2(-25.0, -25.0),
                Vector2(25.0, -25.0),
                Vector2(25.0, 25.0),
                Vector2(-25.0, 25.0),
            ]
        self._points = converted
