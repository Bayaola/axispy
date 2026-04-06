from core.ecs import Component


class ParticleEmitterComponent(Component):
    LAYER_BEHIND = "behind"
    LAYER_FRONT = "front"
    SHAPE_CIRCLE = "circle"
    SHAPE_SQUARE = "square"
    SHAPE_PIXEL = "pixel"

    def __init__(
        self,
        emitting: bool = True,
        one_shot: bool = False,
        local_space: bool = False,
        render_layer: str = LAYER_FRONT,
        blend_additive: bool = False,
        max_particles: int = 512,
        emission_rate: float = 0.0,
        burst_count: int = 0,
        burst_interval: float = 1.0,
        lifetime_min: float = 0.25,
        lifetime_max: float = 0.75,
        speed_min: float = 30.0,
        speed_max: float = 90.0,
        direction_degrees: float = 270.0,
        spread_degrees: float = 360.0,
        gravity_x: float = 0.0,
        gravity_y: float = 0.0,
        damping: float = 0.0,
        radial_offset_min: float = 0.0,
        radial_offset_max: float = 0.0,
        angular_velocity_min: float = 0.0,
        angular_velocity_max: float = 0.0,
        start_size_min: float = 4.0,
        start_size_max: float = 10.0,
        end_size_min: float = 0.0,
        end_size_max: float = 2.0,
        start_color: tuple[int, int, int, int] = (255, 180, 80, 255),
        end_color: tuple[int, int, int, int] = (200, 60, 10, 0),
        emitter_lifetime: float = -1.0,
        shape: str = SHAPE_CIRCLE
    ):
        self.entity = None
        self.emitting = bool(emitting)
        self.one_shot = bool(one_shot)
        self.local_space = bool(local_space)
        layer = str(render_layer).lower()
        self.render_layer = layer if layer in (self.LAYER_BEHIND, self.LAYER_FRONT) else self.LAYER_FRONT
        self.blend_additive = bool(blend_additive)
        self.max_particles = max(1, int(max_particles))
        self.emission_rate = max(0.0, float(emission_rate))
        self.burst_count = max(0, int(burst_count))
        self.burst_interval = max(0.01, float(burst_interval))
        self.lifetime_min = max(0.01, float(lifetime_min))
        self.lifetime_max = max(self.lifetime_min, float(lifetime_max))
        self.speed_min = float(speed_min)
        self.speed_max = max(self.speed_min, float(speed_max))
        self.direction_degrees = float(direction_degrees)
        self.spread_degrees = max(0.0, float(spread_degrees))
        self.gravity_x = float(gravity_x)
        self.gravity_y = float(gravity_y)
        self.damping = max(0.0, float(damping))
        self.radial_offset_min = max(0.0, float(radial_offset_min))
        self.radial_offset_max = max(self.radial_offset_min, float(radial_offset_max))
        self.angular_velocity_min = float(angular_velocity_min)
        self.angular_velocity_max = max(self.angular_velocity_min, float(angular_velocity_max))
        self.start_size_min = max(0.1, float(start_size_min))
        self.start_size_max = max(self.start_size_min, float(start_size_max))
        self.end_size_min = max(0.0, float(end_size_min))
        self.end_size_max = max(self.end_size_min, float(end_size_max))
        self.start_color = tuple(int(max(0, min(255, channel))) for channel in start_color[:4])
        self.end_color = tuple(int(max(0, min(255, channel))) for channel in end_color[:4])
        while len(self.start_color) < 4:
            self.start_color += (255,)
        while len(self.end_color) < 4:
            self.end_color += (0,)
        self.emitter_lifetime = float(emitter_lifetime)
        normalized_shape = str(shape).lower()
        self.shape = normalized_shape if normalized_shape in (self.SHAPE_CIRCLE, self.SHAPE_SQUARE, self.SHAPE_PIXEL) else self.SHAPE_CIRCLE
        self._particle_state = None
        self._pending_bursts = 1 if self.one_shot and self.burst_count > 0 and self.emitting else 0

    def start(self, reset: bool = False):
        self.emitting = True
        if reset and self._particle_state:
            self._particle_state["alive"] = 0
            self._particle_state["rate_carry"] = 0.0
            self._particle_state["burst_timer"] = 0.0
            self._particle_state["elapsed"] = 0.0
        if self.one_shot and self.burst_count > 0:
            self._pending_bursts += 1

    def stop(self, clear_particles: bool = False):
        self.emitting = False
        if clear_particles and self._particle_state:
            self._particle_state["alive"] = 0

    def trigger_burst(self, count: int = 1):
        self._pending_bursts += max(1, int(count))

    @classmethod
    def explosion(cls):
        return cls(
            one_shot=True,
            blend_additive=True,
            max_particles=300,
            emission_rate=0.0,
            burst_count=80,
            burst_interval=1.0,
            lifetime_min=0.2,
            lifetime_max=0.8,
            speed_min=120.0,
            speed_max=420.0,
            direction_degrees=270.0,
            spread_degrees=360.0,
            gravity_y=280.0,
            damping=2.0,
            radial_offset_min=0.0,
            radial_offset_max=12.0,
            angular_velocity_min=-220.0,
            angular_velocity_max=220.0,
            start_size_min=6.0,
            start_size_max=14.0,
            end_size_min=0.0,
            end_size_max=4.0,
            start_color=(255, 225, 120, 255),
            end_color=(255, 60, 20, 0),
            emitter_lifetime=0.15,
            shape=cls.SHAPE_CIRCLE
        )

    @classmethod
    def smoke(cls):
        return cls(
            one_shot=False,
            local_space=False,
            blend_additive=False,
            max_particles=400,
            emission_rate=45.0,
            burst_count=0,
            lifetime_min=0.8,
            lifetime_max=1.9,
            speed_min=10.0,
            speed_max=55.0,
            direction_degrees=270.0,
            spread_degrees=70.0,
            gravity_y=-10.0,
            damping=0.9,
            radial_offset_min=0.0,
            radial_offset_max=5.0,
            angular_velocity_min=-45.0,
            angular_velocity_max=45.0,
            start_size_min=6.0,
            start_size_max=16.0,
            end_size_min=20.0,
            end_size_max=36.0,
            start_color=(120, 120, 120, 160),
            end_color=(70, 70, 70, 0),
            emitter_lifetime=-1.0,
            shape=cls.SHAPE_CIRCLE
        )

    @classmethod
    def magic(cls):
        return cls(
            one_shot=False,
            local_space=False,
            blend_additive=True,
            max_particles=520,
            emission_rate=120.0,
            burst_count=0,
            lifetime_min=0.3,
            lifetime_max=1.2,
            speed_min=35.0,
            speed_max=140.0,
            direction_degrees=270.0,
            spread_degrees=360.0,
            gravity_y=0.0,
            damping=0.45,
            radial_offset_min=0.0,
            radial_offset_max=18.0,
            angular_velocity_min=-180.0,
            angular_velocity_max=180.0,
            start_size_min=2.0,
            start_size_max=8.0,
            end_size_min=0.0,
            end_size_max=3.0,
            start_color=(130, 120, 255, 220),
            end_color=(70, 0, 255, 0),
            emitter_lifetime=-1.0,
            shape=cls.SHAPE_CIRCLE
        )
