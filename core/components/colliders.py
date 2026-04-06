from core.ecs import Component
from core.vector import Vector2


class BoxCollider2D(Component):
    def __init__(
        self,
        width: float = None,
        height: float = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        is_trigger: bool = False,
        category_mask: int = 1,
        collision_mask: int = 0xFFFFFFFF,
        rotation: float = 0.0
    ):
        self.entity = None
        self.width = width
        self.height = height
        self.offset = Vector2(offset_x, offset_y)
        self.is_trigger = is_trigger
        self.category_mask = category_mask
        self.collision_mask = collision_mask
        self.rotation = float(rotation)

    @property
    def offset_x(self):
        return self.offset.x

    @offset_x.setter
    def offset_x(self, value):
        self.offset.x = value

    @property
    def offset_y(self):
        return self.offset.y

    @offset_y.setter
    def offset_y(self, value):
        self.offset.y = value


class CircleCollider2D(Component):
    def __init__(
        self,
        radius: float = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        is_trigger: bool = False,
        category_mask: int = 1,
        collision_mask: int = 0xFFFFFFFF,
        rotation: float = 0.0
    ):
        self.entity = None
        self.radius = radius
        self.offset = Vector2(offset_x, offset_y)
        self.is_trigger = is_trigger
        self.category_mask = category_mask
        self.collision_mask = collision_mask
        self.rotation = float(rotation)

    @property
    def offset_x(self):
        return self.offset.x

    @offset_x.setter
    def offset_x(self, value):
        self.offset.x = value

    @property
    def offset_y(self):
        return self.offset.y

    @offset_y.setter
    def offset_y(self, value):
        self.offset.y = value


class PolygonCollider2D(Component):
    def __init__(
        self,
        points: list | None = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        rotation: float = 0.0,
        is_trigger: bool = False,
        category_mask: int = 1,
        collision_mask: int = 0xFFFFFFFF
    ):
        self.entity = None
        if points is None or len(points) < 3:
            points = [(-25.0, -25.0), (25.0, -25.0), (0.0, 25.0)]
        self.points = points
        self.offset = Vector2(offset_x, offset_y)
        self.is_trigger = is_trigger
        self.category_mask = category_mask
        self.collision_mask = collision_mask
        self.rotation = float(rotation)

    @property
    def points(self):
        return self._points

    @points.setter
    def points(self, value):
        raw_points = value or []
        converted = []
        for point in raw_points:
            if isinstance(point, Vector2):
                converted.append(Vector2(float(point.x), float(point.y)))
            else:
                converted.append(Vector2(float(point[0]), float(point[1])))
        if len(converted) < 3:
            converted = [Vector2(-25.0, -25.0), Vector2(25.0, -25.0), Vector2(0.0, 25.0)]
        self._points = converted

    @property
    def offset_x(self):
        return self.offset.x

    @offset_x.setter
    def offset_x(self, value):
        self.offset.x = value

    @property
    def offset_y(self):
        return self.offset.y

    @offset_y.setter
    def offset_y(self, value):
        self.offset.y = value
