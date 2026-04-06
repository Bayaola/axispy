from __future__ import annotations

from core.ecs import Component
from core.vector import Vector2


class SteeringAgentComponent(Component):
    """Core steering agent.  Accumulates forces from behaviour components and
    applies the resulting velocity to the entity's Transform each frame."""

    def __init__(
        self,
        max_speed: float = 150.0,
        max_force: float = 300.0,
        mass: float = 1.0,
        drag: float = 0.0,
    ):
        self.entity = None
        self.max_speed = max(0.0, float(max_speed))
        self.max_force = max(0.0, float(max_force))
        self.mass = max(0.01, float(mass))
        self.drag = max(0.0, float(drag))

        # Runtime (not serialized)
        self._velocity = Vector2.zero()

    @property
    def velocity(self) -> Vector2:
        return self._velocity

    @velocity.setter
    def velocity(self, value: Vector2):
        self._velocity = value


# ---------------------------------------------------------------------------
# Individual behaviour components – all are optional and composable.
# The SteeringSystem iterates over whichever behaviours are present.
# ---------------------------------------------------------------------------

class SeekBehavior(Component):
    """Steer towards a target position."""

    def __init__(self, target_x: float = 0.0, target_y: float = 0.0, weight: float = 1.0):
        self.entity = None
        self.target_x = float(target_x)
        self.target_y = float(target_y)
        self.weight = max(0.0, float(weight))
        self.enabled = True

    @property
    def target(self) -> Vector2:
        return Vector2(self.target_x, self.target_y)

    @target.setter
    def target(self, value: Vector2):
        self.target_x = float(value.x)
        self.target_y = float(value.y)


class FleeBehavior(Component):
    """Steer away from a target position."""

    def __init__(self, target_x: float = 0.0, target_y: float = 0.0,
                 weight: float = 1.0, panic_distance: float = 200.0):
        self.entity = None
        self.target_x = float(target_x)
        self.target_y = float(target_y)
        self.weight = max(0.0, float(weight))
        self.panic_distance = max(0.0, float(panic_distance))
        self.enabled = True

    @property
    def target(self) -> Vector2:
        return Vector2(self.target_x, self.target_y)

    @target.setter
    def target(self, value: Vector2):
        self.target_x = float(value.x)
        self.target_y = float(value.y)


class ArriveBehavior(Component):
    """Steer towards a target, decelerating smoothly within *slow_radius*."""

    def __init__(self, target_x: float = 0.0, target_y: float = 0.0,
                 weight: float = 1.0, slow_radius: float = 100.0):
        self.entity = None
        self.target_x = float(target_x)
        self.target_y = float(target_y)
        self.weight = max(0.0, float(weight))
        self.slow_radius = max(1.0, float(slow_radius))
        self.enabled = True

    @property
    def target(self) -> Vector2:
        return Vector2(self.target_x, self.target_y)

    @target.setter
    def target(self, value: Vector2):
        self.target_x = float(value.x)
        self.target_y = float(value.y)


class WanderBehavior(Component):
    """Produces a gentle, random meandering force."""

    def __init__(self, weight: float = 1.0, circle_distance: float = 60.0,
                 circle_radius: float = 30.0, angle_change: float = 30.0):
        self.entity = None
        self.weight = max(0.0, float(weight))
        self.circle_distance = max(0.0, float(circle_distance))
        self.circle_radius = max(0.0, float(circle_radius))
        self.angle_change = max(0.0, float(angle_change))
        self.enabled = True
        # Runtime
        self._wander_angle = 0.0


class SeparationBehavior(Component):
    """Steer to avoid crowding neighbours within *neighbor_radius*."""

    def __init__(self, weight: float = 1.0, neighbor_radius: float = 50.0):
        self.entity = None
        self.weight = max(0.0, float(weight))
        self.neighbor_radius = max(0.0, float(neighbor_radius))
        self.enabled = True


class CohesionBehavior(Component):
    """Steer towards the average position of neighbours."""

    def __init__(self, weight: float = 1.0, neighbor_radius: float = 100.0):
        self.entity = None
        self.weight = max(0.0, float(weight))
        self.neighbor_radius = max(0.0, float(neighbor_radius))
        self.enabled = True


class AlignmentBehavior(Component):
    """Steer to match the average heading of neighbours."""

    def __init__(self, weight: float = 1.0, neighbor_radius: float = 100.0):
        self.entity = None
        self.weight = max(0.0, float(weight))
        self.neighbor_radius = max(0.0, float(neighbor_radius))
        self.enabled = True
