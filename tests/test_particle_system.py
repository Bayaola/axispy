import pytest
from core.ecs import World
from core.components.transform import Transform
from core.components.particle_emitter import ParticleEmitterComponent
from core.systems.particle_system import ParticleSystem


@pytest.fixture
def particle_world():
    world = World()
    world.add_system(ParticleSystem())
    return world


def _make_emitter(world, **kwargs):
    entity = world.create_entity("Emitter")
    entity.add_component(Transform(x=0, y=0))
    emitter = ParticleEmitterComponent(**kwargs)
    entity.add_component(emitter)
    return entity, emitter


# ---------------------------------------------------------------------------
# ParticleEmitterComponent unit tests
# ---------------------------------------------------------------------------

class TestParticleEmitterComponent:
    def test_defaults(self):
        e = ParticleEmitterComponent()
        assert e.emitting is True
        assert e.one_shot is False
        assert e.max_particles == 512
        assert e.shape == ParticleEmitterComponent.SHAPE_CIRCLE

    def test_invalid_shape_defaults_to_circle(self):
        e = ParticleEmitterComponent(shape="invalid")
        assert e.shape == ParticleEmitterComponent.SHAPE_CIRCLE

    def test_render_layer_validation(self):
        e = ParticleEmitterComponent(render_layer="invalid")
        assert e.render_layer == ParticleEmitterComponent.LAYER_FRONT

    def test_start_and_stop(self):
        e = ParticleEmitterComponent(emitting=False)
        e.start()
        assert e.emitting is True
        e.stop()
        assert e.emitting is False

    def test_stop_clears_particles(self):
        e = ParticleEmitterComponent()
        e._particle_state = {"alive": 10}
        e.stop(clear_particles=True)
        assert e._particle_state["alive"] == 0

    def test_trigger_burst(self):
        e = ParticleEmitterComponent()
        e.trigger_burst(3)
        assert e._pending_bursts >= 3

    def test_explosion_preset(self):
        e = ParticleEmitterComponent.explosion()
        assert e.one_shot is True
        assert e.blend_additive is True
        assert e.burst_count > 0

    def test_smoke_preset(self):
        e = ParticleEmitterComponent.smoke()
        assert e.one_shot is False
        assert e.emission_rate > 0

    def test_magic_preset(self):
        e = ParticleEmitterComponent.magic()
        assert e.blend_additive is True

    def test_color_channels_clamped(self):
        e = ParticleEmitterComponent(start_color=(300, -10, 128, 255))
        assert e.start_color[0] == 255
        assert e.start_color[1] == 0


# ---------------------------------------------------------------------------
# ParticleSystem integration tests
# ---------------------------------------------------------------------------

class TestParticleSystem:
    def test_emission_rate_spawns_particles(self, particle_world):
        entity, emitter = _make_emitter(
            particle_world, emission_rate=100.0, max_particles=50
        )
        particle_world.update(0.1)
        assert emitter._particle_state is not None
        assert emitter._particle_state["alive"] > 0

    def test_one_shot_burst(self, particle_world):
        entity, emitter = _make_emitter(
            particle_world, one_shot=True, burst_count=10,
            emission_rate=0.0, max_particles=50
        )
        particle_world.update(0.016)
        assert emitter._particle_state is not None
        alive = emitter._particle_state["alive"]
        assert alive == 10
        # After burst, emitting should be False
        assert emitter.emitting is False

    def test_particles_age_and_die(self, particle_world):
        entity, emitter = _make_emitter(
            particle_world, emission_rate=1000.0, max_particles=50,
            lifetime_min=0.05, lifetime_max=0.05
        )
        particle_world.update(0.02)
        alive_after_spawn = emitter._particle_state["alive"]
        assert alive_after_spawn > 0
        # Now age them past lifetime
        particle_world.update(0.1)
        assert emitter._particle_state["alive"] < alive_after_spawn

    def test_max_particles_respected(self, particle_world):
        entity, emitter = _make_emitter(
            particle_world, emission_rate=10000.0, max_particles=5
        )
        particle_world.update(0.1)
        assert emitter._particle_state["alive"] <= 5

    def test_gravity_affects_velocity(self, particle_world):
        entity, emitter = _make_emitter(
            particle_world, emission_rate=1.0, max_particles=10,
            gravity_y=1000.0, lifetime_min=10.0, lifetime_max=10.0,
            speed_min=0.0, speed_max=0.0
        )
        particle_world.update(0.01)
        if emitter._particle_state and emitter._particle_state["alive"] > 0:
            particle_world.update(0.1)
            # vy should have increased due to gravity
            vy = emitter._particle_state["vy"][0]
            assert vy > 0

    def test_emitter_lifetime_stops_emission(self, particle_world):
        entity, emitter = _make_emitter(
            particle_world, emission_rate=100.0, max_particles=50,
            emitter_lifetime=0.05
        )
        particle_world.update(0.1)
        assert emitter.emitting is False

    def test_damping_slows_particles(self, particle_world):
        entity, emitter = _make_emitter(
            particle_world, emission_rate=1.0, max_particles=5,
            damping=10.0, lifetime_min=10.0, lifetime_max=10.0,
            speed_min=100.0, speed_max=100.0
        )
        particle_world.update(0.01)
        if emitter._particle_state and emitter._particle_state["alive"] > 0:
            vx0 = abs(emitter._particle_state["vx"][0])
            vy0 = abs(emitter._particle_state["vy"][0])
            speed_before = (vx0**2 + vy0**2)**0.5
            particle_world.update(0.5)
            vx1 = abs(emitter._particle_state["vx"][0])
            vy1 = abs(emitter._particle_state["vy"][0])
            speed_after = (vx1**2 + vy1**2)**0.5
            assert speed_after < speed_before

    def test_entity_without_transform_skipped(self, particle_world):
        entity = particle_world.create_entity("NoTransform")
        entity.add_component(ParticleEmitterComponent(emission_rate=100.0))
        particle_world.update(0.1)  # Should not crash

    def test_max_particles_change_resets_state(self, particle_world):
        entity, emitter = _make_emitter(
            particle_world, emission_rate=100.0, max_particles=10
        )
        particle_world.update(0.05)
        assert emitter._particle_state is not None
        old_max = emitter._particle_state["max"]
        emitter.max_particles = 20
        particle_world.update(0.05)
        assert emitter._particle_state["max"] == 20
