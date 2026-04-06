import random
from core.ecs import Component


class CameraComponent(Component):
    DECAY_LINEAR = "linear"
    DECAY_EXPONENTIAL = "exponential"

    def __init__(
        self,
        active: bool = True,
        zoom: float = 1.0,
        rotation: float = 0.0,
        viewport_x: float = 0.0,
        viewport_y: float = 0.0,
        viewport_width: float = 1.0,
        viewport_height: float = 1.0,
        priority: int = 0,
        follow_target_id: str = "",
        follow_rotation: bool = True
    ):
        self.entity = None
        self.active = bool(active)
        self.zoom = max(0.01, float(zoom))
        self.rotation = float(rotation)
        self.viewport_x = float(viewport_x)
        self.viewport_y = float(viewport_y)
        self.viewport_width = max(0.0, float(viewport_width))
        self.viewport_height = max(0.0, float(viewport_height))
        self.priority = int(priority)
        self.follow_target_id = str(follow_target_id or "")
        self.follow_rotation = bool(follow_rotation)
        # Shake state
        self._shake_intensity: float = 0.0
        self._shake_duration: float = 0.0
        self._shake_elapsed: float = 0.0
        self._shake_decay: str = self.DECAY_LINEAR
        self._shake_offset_x: float = 0.0
        self._shake_offset_y: float = 0.0

    def shake(self, intensity: float = 5.0, duration: float = 0.3,
              decay: str = "linear"):
        """Start a camera shake effect.

        Args:
            intensity: Maximum pixel offset per axis.
            duration: How long the shake lasts in seconds.
            decay: Decay curve — ``"linear"`` or ``"exponential"``.
        """
        self._shake_intensity = max(0.0, float(intensity))
        self._shake_duration = max(0.0, float(duration))
        self._shake_elapsed = 0.0
        self._shake_decay = decay if decay in (self.DECAY_LINEAR, self.DECAY_EXPONENTIAL) else self.DECAY_LINEAR

    def update_shake(self, dt: float):
        """Advance the shake timer and compute the current offset.
        Called by the render system each frame."""
        if self._shake_duration <= 0.0 or self._shake_elapsed >= self._shake_duration:
            self._shake_offset_x = 0.0
            self._shake_offset_y = 0.0
            return
        self._shake_elapsed += dt
        t = min(self._shake_elapsed / self._shake_duration, 1.0)
        if self._shake_decay == self.DECAY_EXPONENTIAL:
            factor = (1.0 - t) ** 2
        else:
            factor = 1.0 - t
        magnitude = self._shake_intensity * factor
        self._shake_offset_x = random.uniform(-magnitude, magnitude)
        self._shake_offset_y = random.uniform(-magnitude, magnitude)

    @property
    def shake_offset(self) -> tuple[float, float]:
        """Current (x, y) shake offset in pixels."""
        return (self._shake_offset_x, self._shake_offset_y)

    @property
    def is_shaking(self) -> bool:
        return self._shake_elapsed < self._shake_duration and self._shake_duration > 0.0
