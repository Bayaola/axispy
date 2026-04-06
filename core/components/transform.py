from __future__ import annotations
import math
from core.ecs import Component
from core.vector import Vector2


class Transform(Component):
    def __init__(self, x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0):
        self._position = Vector2(x, y)
        self._scale = Vector2(scale_x, scale_y)
        self._rotation = rotation
        self.entity = None

    @property
    def x(self): return self._position.x
    
    @x.setter
    def x(self, value):
        dx = value - self._position.x
        old_x = self._position.x
        self._position.x = value
        self._propagate(dx, 0, 0, 1.0, 1.0, old_x, self._position.y)

    @property
    def y(self): return self._position.y
    
    @y.setter
    def y(self, value):
        dy = value - self._position.y
        old_y = self._position.y
        self._position.y = value
        self._propagate(0, dy, 0, 1.0, 1.0, self._position.x, old_y)

    @property
    def rotation(self): return self._rotation
    
    @rotation.setter
    def rotation(self, value):
        d_rot = value - self._rotation
        self._rotation = value % 360
        self._propagate(0, 0, d_rot, 1.0, 1.0, self._position.x, self._position.y)

    @property
    def scale_x(self): return self._scale.x
    
    @scale_x.setter
    def scale_x(self, value):
        old_scale = self._scale.x
        self._scale.x = value
        ratio = value / old_scale if old_scale != 0 else 1.0
        self._propagate(0, 0, 0, ratio, 1.0, self._position.x, self._position.y)

    @property
    def scale_y(self): return self._scale.y
    
    @scale_y.setter
    def scale_y(self, value):
        old_scale = self._scale.y
        self._scale.y = value
        ratio = value / old_scale if old_scale != 0 else 1.0
        self._propagate(0, 0, 0, 1.0, ratio, self._position.x, self._position.y)

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        if isinstance(value, Vector2):
            new_x, new_y = value.x, value.y
        else:
            new_x, new_y = value[0], value[1]
        dx = new_x - self._position.x
        dy = new_y - self._position.y
        old_x, old_y = self._position.x, self._position.y
        self._position.x = new_x
        self._position.y = new_y
        self._propagate(dx, dy, 0, 1.0, 1.0, old_x, old_y)

    @property
    def scale_vec(self):
        return self._scale

    @scale_vec.setter
    def scale_vec(self, value):
        if isinstance(value, Vector2):
            new_sx, new_sy = value.x, value.y
        else:
            new_sx, new_sy = value[0], value[1]
        old_sx, old_sy = self._scale.x, self._scale.y
        self._scale.x = new_sx
        self._scale.y = new_sy
        ratio_x = new_sx / old_sx if old_sx != 0 else 1.0
        ratio_y = new_sy / old_sy if old_sy != 0 else 1.0
        self._propagate(0, 0, 0, ratio_x, ratio_y, self._position.x, self._position.y)

    def translate(self, dx: float, dy: float):
        old_x, old_y = self._position.x, self._position.y
        self._position.x += dx
        self._position.y += dy
        self._propagate(dx, dy, 0, 1.0, 1.0, old_x, old_y)
        
    def translate_vec(self, vec: Vector2):
        old_x, old_y = self._position.x, self._position.y
        self._position.x += vec.x
        self._position.y += vec.y
        self._propagate(vec.x, vec.y, 0, 1.0, 1.0, old_x, old_y)

    def rotate(self, d_rot: float):
        self.rotation += d_rot

    def scale(self, ds_x: float, ds_y: float):
        old_sx, old_sy = self._scale.x, self._scale.y
        self._scale.x += ds_x
        self._scale.y += ds_y
        ratio_x = self._scale.x / old_sx if old_sx != 0 else 1.0
        ratio_y = self._scale.y / old_sy if old_sy != 0 else 1.0
        self._propagate(0, 0, 0, ratio_x, ratio_y, self._position.x, self._position.y)
        
    def scale_by_vec(self, vec: Vector2):
        old_sx, old_sy = self._scale.x, self._scale.y
        self._scale.x *= vec.x
        self._scale.y *= vec.y
        ratio_x = self._scale.x / old_sx if old_sx != 0 else 1.0
        ratio_y = self._scale.y / old_sy if old_sy != 0 else 1.0
        self._propagate(0, 0, 0, ratio_x, ratio_y, self._position.x, self._position.y)

    def __repr__(self):
        return (f"<Transform pos=({self.x:.1f}, {self.y:.1f}) "
                f"rot={self.rotation:.1f} scale=({self.scale_x:.2f}, {self.scale_y:.2f})>")

    def _propagate(self, dx, dy, d_rot, scale_ratio_x, scale_ratio_y, parent_x, parent_y):
        if not self.entity or not hasattr(self.entity, 'children'):
            return
            
        for child in self.entity.children:
            child_transform = child.get_component(Transform)
            if not child_transform:
                continue
            
            old_cx = child_transform._position.x
            old_cy = child_transform._position.y
            
            vx = old_cx - parent_x
            vy = old_cy - parent_y
            
            # 1. Scale relative vector
            vx *= scale_ratio_x
            vy *= scale_ratio_y
            
            # 2. Rotate relative vector
            if d_rot != 0:
                rad = math.radians(d_rot)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)
                nx = vx * cos_a - vy * sin_a
                ny = vx * sin_a + vy * cos_a
                vx, vy = nx, ny
                
            # 3. Compute new child position
            new_parent_x = parent_x + dx
            new_parent_y = parent_y + dy
            new_cx = new_parent_x + vx
            new_cy = new_parent_y + vy
            
            # 4. Compute child deltas for recursive propagation
            child_dx = new_cx - old_cx
            child_dy = new_cy - old_cy
            
            # 5. Write directly to internal fields (bypass setters to avoid re-entrancy)
            child_transform._position.x = new_cx
            child_transform._position.y = new_cy
            
            if d_rot != 0:
                child_transform._rotation = (child_transform._rotation + d_rot) % 360
            if scale_ratio_x != 1.0:
                child_transform._scale.x *= scale_ratio_x
            if scale_ratio_y != 1.0:
                child_transform._scale.y *= scale_ratio_y
            
            # 6. Recursively propagate to grandchildren
            child_transform._propagate(
                child_dx, child_dy, d_rot,
                scale_ratio_x, scale_ratio_y,
                old_cx, old_cy
            )
