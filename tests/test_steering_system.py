import pytest
import math
from core.ecs import World
from core.vector import Vector2
from core.components.transform import Transform
from core.components.steering import (
    SteeringAgentComponent,
    SeekBehavior,
    FleeBehavior,
    ArriveBehavior,
    WanderBehavior,
    SeparationBehavior,
    CohesionBehavior,
    AlignmentBehavior,
)
from core.systems.steering_system import SteeringSystem


@pytest.fixture
def steering_world():
    world = World()
    world.add_system(SteeringSystem())
    return world


def _make_agent(world, x=0.0, y=0.0, max_speed=150.0, max_force=300.0, mass=1.0):
    entity = world.create_entity("Agent")
    entity.add_component(Transform(x=x, y=y))
    entity.add_component(SteeringAgentComponent(
        max_speed=max_speed, max_force=max_force, mass=mass
    ))
    return entity


# ---------------------------------------------------------------------------
# Component unit tests
# ---------------------------------------------------------------------------

class TestSteeringAgentComponent:
    def test_defaults(self):
        a = SteeringAgentComponent()
        assert a.max_speed == 150.0
        assert a.max_force == 300.0
        assert a.mass == 1.0
        assert a.drag == 0.0
        assert a.velocity == Vector2(0, 0)

    def test_velocity_property(self):
        a = SteeringAgentComponent()
        a.velocity = Vector2(10, 20)
        assert a.velocity.x == 10
        assert a.velocity.y == 20

    def test_negative_values_clamped(self):
        a = SteeringAgentComponent(max_speed=-5, max_force=-5, mass=-5, drag=-1)
        assert a.max_speed == 0.0
        assert a.max_force == 0.0
        assert a.mass == 0.01
        assert a.drag == 0.0


class TestSeekBehavior:
    def test_target_property(self):
        s = SeekBehavior(target_x=100, target_y=200)
        assert s.target == Vector2(100, 200)

    def test_target_setter(self):
        s = SeekBehavior()
        s.target = Vector2(50, 75)
        assert s.target_x == 50.0
        assert s.target_y == 75.0


class TestFleeBehavior:
    def test_panic_distance(self):
        f = FleeBehavior(panic_distance=300)
        assert f.panic_distance == 300.0

    def test_defaults(self):
        f = FleeBehavior()
        assert f.enabled is True
        assert f.weight == 1.0


class TestArriveBehavior:
    def test_slow_radius(self):
        a = ArriveBehavior(slow_radius=50)
        assert a.slow_radius == 50.0

    def test_slow_radius_min(self):
        a = ArriveBehavior(slow_radius=0)
        assert a.slow_radius == 1.0


# ---------------------------------------------------------------------------
# Static helper tests
# ---------------------------------------------------------------------------

class TestSteeringHelpers:
    def test_seek_towards_target(self):
        pos = Vector2(0, 0)
        target = Vector2(100, 0)
        result = SteeringSystem._seek(pos, target, 150.0)
        assert result.x > 0
        assert result.y == pytest.approx(0.0, abs=1e-4)

    def test_seek_at_target_returns_zero(self):
        pos = Vector2(5, 5)
        result = SteeringSystem._seek(pos, pos, 150.0)
        assert result.x == pytest.approx(0.0)
        assert result.y == pytest.approx(0.0)

    def test_flee_away_from_target(self):
        pos = Vector2(10, 0)
        target = Vector2(0, 0)
        result = SteeringSystem._flee(pos, target, 150.0, panic_dist=200.0)
        assert result.x > 0  # fleeing to the right

    def test_flee_outside_panic_distance(self):
        pos = Vector2(1000, 0)
        target = Vector2(0, 0)
        result = SteeringSystem._flee(pos, target, 150.0, panic_dist=50.0)
        assert result == Vector2(0, 0)

    def test_arrive_decelerates_near_target(self):
        pos = Vector2(10, 0)
        target = Vector2(0, 0)
        vel = Vector2(-50, 0)
        result = SteeringSystem._arrive(pos, target, 150.0, 100.0, vel)
        # Should produce some braking force
        assert isinstance(result, Vector2)

    def test_arrive_stops_at_target(self):
        pos = Vector2(0.1, 0)
        target = Vector2(0, 0)
        vel = Vector2(-10, 0)
        result = SteeringSystem._arrive(pos, target, 150.0, 100.0, vel)
        # Should return -current_vel (braking)
        assert result.x == pytest.approx(10.0, abs=0.5)

    def test_wander_returns_force_and_angle(self):
        force, new_angle = SteeringSystem._wander(
            Vector2(0, 0), Vector2(1, 0), 150.0,
            60.0, 30.0, 0.0, 30.0
        )
        assert isinstance(force, Vector2)
        assert isinstance(new_angle, float)

    def test_separation_no_neighbours(self):
        from core.ecs import Entity
        e = Entity("test")
        result = SteeringSystem._separation(e, Vector2(0, 0), [], 50.0)
        assert result == Vector2(0, 0)

    def test_cohesion_no_neighbours(self):
        from core.ecs import Entity
        e = Entity("test")
        result = SteeringSystem._cohesion(e, Vector2(0, 0), [], 100.0, 150.0)
        assert result == Vector2(0, 0)

    def test_alignment_no_neighbours(self):
        from core.ecs import Entity
        e = Entity("test")
        result = SteeringSystem._alignment(e, [], 100.0)
        assert result == Vector2(0, 0)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestSteeringSystemIntegration:
    def test_seek_moves_entity(self, steering_world):
        entity = _make_agent(steering_world, x=0, y=0)
        entity.add_component(SeekBehavior(target_x=500, target_y=0))
        steering_world.update(0.1)
        t = entity.get_component(Transform)
        assert t.x > 0

    def test_flee_moves_entity_away(self, steering_world):
        entity = _make_agent(steering_world, x=50, y=0)
        entity.add_component(FleeBehavior(target_x=0, target_y=0, panic_distance=200))
        steering_world.update(0.1)
        t = entity.get_component(Transform)
        assert t.x > 50

    def test_no_update_when_dt_zero(self, steering_world):
        entity = _make_agent(steering_world, x=0, y=0)
        entity.add_component(SeekBehavior(target_x=500, target_y=0))
        steering_world.update(0.0)
        t = entity.get_component(Transform)
        assert t.x == pytest.approx(0.0)

    def test_no_update_without_world(self):
        system = SteeringSystem()
        system.update(0.016, [])

    def test_drag_slows_agent(self, steering_world):
        entity = _make_agent(steering_world, x=0, y=0)
        agent = entity.get_component(SteeringAgentComponent)
        agent.drag = 5.0
        agent._velocity = Vector2(100, 0)
        entity.add_component(SeekBehavior(target_x=0, target_y=0))
        steering_world.update(0.1)
        # Velocity should be damped
        assert agent._velocity.magnitude() < 100

    def test_max_force_clamped(self, steering_world):
        entity = _make_agent(steering_world, max_force=10.0)
        entity.add_component(SeekBehavior(target_x=99999, target_y=99999, weight=1000.0))
        steering_world.update(0.1)
        agent = entity.get_component(SteeringAgentComponent)
        # Speed shouldn't be astronomically high due to force clamping
        assert agent._velocity.magnitude() < 200

    def test_disabled_behavior_ignored(self, steering_world):
        entity = _make_agent(steering_world, x=0, y=0)
        seek = SeekBehavior(target_x=500, target_y=0)
        seek.enabled = False
        entity.add_component(seek)
        steering_world.update(0.1)
        t = entity.get_component(Transform)
        assert t.x == pytest.approx(0.0)

    def test_multiple_behaviors_combined(self, steering_world):
        entity = _make_agent(steering_world, x=0, y=0)
        entity.add_component(SeekBehavior(target_x=500, target_y=0, weight=1.0))
        entity.add_component(FleeBehavior(target_x=0, target_y=500, weight=1.0,
                                          panic_distance=1000))
        steering_world.update(0.1)
        t = entity.get_component(Transform)
        # Should have moved in some direction due to combined forces
        assert t.x != 0.0 or t.y != 0.0

    def test_flocking_separation(self, steering_world):
        e1 = _make_agent(steering_world, x=0, y=0)
        e1.add_component(SeparationBehavior(weight=1.0, neighbor_radius=100))
        e2 = _make_agent(steering_world, x=10, y=0)
        e2.add_component(SeparationBehavior(weight=1.0, neighbor_radius=100))
        steering_world.update(0.1)
        t1 = e1.get_component(Transform)
        t2 = e2.get_component(Transform)
        # They should move apart
        assert t2.x - t1.x > 10

    def test_entity_without_transform_skipped(self, steering_world):
        entity = steering_world.create_entity("NoTransform")
        entity.add_component(SteeringAgentComponent())
        steering_world.update(0.1)  # Should not crash
