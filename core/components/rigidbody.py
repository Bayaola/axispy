from core.ecs import Component
from core.vector import Vector2


class Rigidbody2D(Component):
    BODY_TYPE_STATIC = "static"
    BODY_TYPE_KINEMATIC = "kinematic"
    BODY_TYPE_DYNAMIC = "dynamic"
    _VALID_BODY_TYPES = {BODY_TYPE_STATIC, BODY_TYPE_KINEMATIC, BODY_TYPE_DYNAMIC}

    def __init__(
        self,
        velocity_x: float = 0.0,
        velocity_y: float = 0.0,
        mass: float = 1.0,
        angular_velocity: float = 0.0,
        gravity_scale: float = 1.0,
        use_gravity: bool = True,
        body_type: str = BODY_TYPE_DYNAMIC,
        is_kinematic: bool = False,
        restitution: float = 0.0,
        friction: float = 0.0,
        linear_damping: float = 0.0,
        angular_damping: float = 0.0,
        freeze_rotation: bool = False
    ):
        self.entity = None
        self.velocity = Vector2(velocity_x, velocity_y)
        self.mass = max(0.0001, mass)
        self.angular_velocity = angular_velocity
        self.gravity_scale = gravity_scale
        self.use_gravity = use_gravity
        self.body_type = body_type
        if is_kinematic:
            self.body_type = self.BODY_TYPE_KINEMATIC
        self.restitution = max(0.0, min(1.0, restitution))
        self.friction = max(0.0, float(friction))
        self.linear_damping = max(0.0, linear_damping)
        self.angular_damping = max(0.0, angular_damping)
        self.freeze_rotation = freeze_rotation
        self._force = Vector2(0.0, 0.0)
        self._torque = 0.0

    @property
    def velocity_x(self):
        return self.velocity.x

    @velocity_x.setter
    def velocity_x(self, value):
        self.velocity.x = value

    @property
    def velocity_y(self):
        return self.velocity.y

    @velocity_y.setter
    def velocity_y(self, value):
        self.velocity.y = value

    @property
    def elasticity(self):
        return self.restitution

    @elasticity.setter
    def elasticity(self, value):
        self.restitution = max(0.0, min(1.0, value))

    @property
    def force_x(self):
        return self._force.x

    @property
    def force_y(self):
        return self._force.y

    @property
    def can_rotate(self):
        return not self.freeze_rotation

    @can_rotate.setter
    def can_rotate(self, value):
        self.freeze_rotation = not value

    def apply_force(self, force_x: float, force_y: float):
        self._force.x += force_x
        self._force.y += force_y

    def apply_impulse(self, impulse_x: float, impulse_y: float):
        if not self.is_dynamic:
            return
        self.velocity.x += impulse_x / self.mass
        self.velocity.y += impulse_y / self.mass

    def apply_torque(self, torque: float):
        if not self.is_dynamic:
            return
        self._torque += torque

    def apply_angular_impulse(self, angular_impulse: float):
        if not self.is_dynamic or self.freeze_rotation:
            return
        self.angular_velocity += angular_impulse / self.mass

    def clear_forces(self):
        self._force.x = 0.0
        self._force.y = 0.0
        self._torque = 0.0

    @property
    def torque(self):
        return self._torque

    @property
    def body_type(self):
        return self._body_type

    @body_type.setter
    def body_type(self, value):
        normalized = str(value).lower()
        if normalized not in self._VALID_BODY_TYPES:
            normalized = self.BODY_TYPE_DYNAMIC
        self._body_type = normalized

    @property
    def is_static(self):
        return self.body_type == self.BODY_TYPE_STATIC

    @property
    def is_dynamic(self):
        return self.body_type == self.BODY_TYPE_DYNAMIC

    @property
    def is_kinematic(self):
        return self.body_type == self.BODY_TYPE_KINEMATIC

    @is_kinematic.setter
    def is_kinematic(self, value):
        self.body_type = self.BODY_TYPE_KINEMATIC if value else self.BODY_TYPE_DYNAMIC
