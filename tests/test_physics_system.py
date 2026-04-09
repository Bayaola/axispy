import pytest
import math
from core.ecs import World, Entity
from core.vector import Vector2
from core.components.transform import Transform
from core.components.rigidbody import Rigidbody2D
from core.components.colliders import BoxCollider2D, CircleCollider2D, PolygonCollider2D
from core.systems.physics_system import PhysicsSystem, SpatialHashGrid, _Body, CollisionInfo


@pytest.fixture
def physics_world():
    world = World()
    world.add_system(PhysicsSystem(gravity_x=0.0, gravity_y=0.0))
    return world


@pytest.fixture
def gravity_world():
    world = World()
    world.add_system(PhysicsSystem(gravity_x=0.0, gravity_y=980.0))
    return world


def _make_body(world, x=0, y=0, body_type="dynamic", collider=None, **rb_kw):
    entity = world.create_entity("Body")
    entity.add_component(Transform(x=x, y=y))
    entity.add_component(Rigidbody2D(body_type=body_type, use_gravity=False, **rb_kw))
    if collider is None:
        collider = BoxCollider2D(width=50, height=50)
    entity.add_component(collider)
    return entity


# ---------------------------------------------------------------------------
# Rigidbody2D component tests
# ---------------------------------------------------------------------------

class TestRigidbody2D:
    def test_defaults(self):
        rb = Rigidbody2D()
        assert rb.is_dynamic is True
        assert rb.mass == 1.0
        assert rb.use_gravity is True
        assert rb.velocity == Vector2(0, 0)

    def test_body_type_static(self):
        rb = Rigidbody2D(body_type="static")
        assert rb.is_static is True
        assert rb.is_dynamic is False

    def test_body_type_kinematic(self):
        rb = Rigidbody2D(is_kinematic=True)
        assert rb.is_kinematic is True

    def test_apply_force(self):
        rb = Rigidbody2D()
        rb.apply_force(10, 20)
        assert rb.force_x == 10
        assert rb.force_y == 20

    def test_apply_impulse(self):
        rb = Rigidbody2D(mass=2.0)
        rb.apply_impulse(10, 0)
        assert rb.velocity.x == pytest.approx(5.0)

    def test_apply_impulse_static_ignored(self):
        rb = Rigidbody2D(body_type="static")
        rb.apply_impulse(10, 0)
        assert rb.velocity.x == 0.0

    def test_clear_forces(self):
        rb = Rigidbody2D()
        rb.apply_force(10, 20)
        rb.apply_torque(5)
        rb.clear_forces()
        assert rb.force_x == 0
        assert rb.force_y == 0
        assert rb.torque == 0

    def test_elasticity_alias(self):
        rb = Rigidbody2D(restitution=0.5)
        assert rb.elasticity == 0.5
        rb.elasticity = 0.8
        assert rb.restitution == 0.8

    def test_freeze_rotation(self):
        rb = Rigidbody2D(freeze_rotation=True)
        assert rb.can_rotate is False


# ---------------------------------------------------------------------------
# Collider component tests
# ---------------------------------------------------------------------------

class TestBoxCollider2D:
    def test_defaults(self):
        c = BoxCollider2D()
        assert c.width is None
        assert c.height is None
        assert c.is_trigger is False

    def test_offset(self):
        c = BoxCollider2D(offset_x=10, offset_y=20)
        assert c.offset.x == 10
        assert c.offset.y == 20


class TestCircleCollider2D:
    def test_defaults(self):
        c = CircleCollider2D()
        assert c.radius is None
        assert c.is_trigger is False

    def test_custom_radius(self):
        c = CircleCollider2D(radius=30)
        assert c.radius == 30


class TestPolygonCollider2D:
    def test_defaults_triangle(self):
        c = PolygonCollider2D()
        assert len(c.points) == 3

    def test_custom_points(self):
        pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
        c = PolygonCollider2D(points=pts)
        assert len(c.points) == 4

    def test_too_few_points_default(self):
        c = PolygonCollider2D(points=[(0, 0)])
        assert len(c.points) == 3  # Defaults to triangle


# ---------------------------------------------------------------------------
# SpatialHashGrid tests
# ---------------------------------------------------------------------------

class TestSpatialHashGrid:
    def test_insert_and_query(self):
        grid = SpatialHashGrid(cell_size=64)
        e = Entity("E")
        grid.insert(e, 0, 0, 50, 50)
        results = grid.query(0, 0, 50, 50)
        assert e in results

    def test_query_no_overlap(self):
        grid = SpatialHashGrid(cell_size=64)
        e = Entity("E")
        grid.insert(e, 0, 0, 10, 10)
        results = grid.query(1000, 1000, 1100, 1100)
        assert e not in results

    def test_remove(self):
        grid = SpatialHashGrid(cell_size=64)
        e = Entity("E")
        grid.insert(e, 0, 0, 50, 50)
        grid.remove(e)
        results = grid.query(0, 0, 50, 50)
        assert e not in results

    def test_move(self):
        grid = SpatialHashGrid(cell_size=64)
        e = Entity("E")
        grid.insert(e, 0, 0, 50, 50)
        grid.move(e, 500, 500, 550, 550)
        assert e not in grid.query(0, 0, 50, 50)
        assert e in grid.query(500, 500, 550, 550)

    def test_clear(self):
        grid = SpatialHashGrid(cell_size=64)
        e = Entity("E")
        grid.insert(e, 0, 0, 50, 50)
        grid.clear()
        assert len(grid.cells) == 0


# ---------------------------------------------------------------------------
# PhysicsSystem integration tests
# ---------------------------------------------------------------------------

class TestPhysicsIntegration:
    def test_gravity_moves_dynamic_body(self, gravity_world):
        entity = gravity_world.create_entity("Ball")
        entity.add_component(Transform(x=0, y=0))
        entity.add_component(Rigidbody2D(body_type="dynamic", use_gravity=True))
        entity.add_component(CircleCollider2D(radius=10))
        gravity_world.update(0.1)
        t = entity.get_component(Transform)
        assert t.y > 0

    def test_static_body_does_not_move(self, gravity_world):
        entity = gravity_world.create_entity("Wall")
        entity.add_component(Transform(x=100, y=100))
        entity.add_component(Rigidbody2D(body_type="static"))
        entity.add_component(BoxCollider2D(width=50, height=50))
        gravity_world.update(0.1)
        t = entity.get_component(Transform)
        assert t.x == pytest.approx(100.0)
        assert t.y == pytest.approx(100.0)

    def test_kinematic_body_uses_velocity(self, physics_world):
        entity = _make_body(physics_world, x=0, y=0, body_type="kinematic",
                            velocity_x=100, velocity_y=0)
        physics_world.update(0.1)
        t = entity.get_component(Transform)
        assert t.x == pytest.approx(10.0, abs=0.5)

    def test_linear_damping(self, physics_world):
        entity = _make_body(physics_world, x=0, y=0,
                            velocity_x=100, linear_damping=5.0)
        rb = entity.get_component(Rigidbody2D)
        physics_world.update(0.1)
        assert abs(rb.velocity.x) < 100

    def test_zero_dt_no_update(self, physics_world):
        entity = _make_body(physics_world, x=0, y=0, velocity_x=100)
        physics_world.update(0.0)
        t = entity.get_component(Transform)
        assert t.x == pytest.approx(0.0)


class TestCollisionDetection:
    def test_box_box_overlap(self, physics_world):
        e1 = _make_body(physics_world, x=0, y=0,
                        collider=BoxCollider2D(width=50, height=50))
        e2 = _make_body(physics_world, x=30, y=0,
                        collider=BoxCollider2D(width=50, height=50))
        physics_world.update(0.016)
        t1 = e1.get_component(Transform)
        t2 = e2.get_component(Transform)
        # After resolution, they should be pushed apart
        assert t2.x - t1.x > 30

    def test_circle_circle_overlap(self, physics_world):
        e1 = _make_body(physics_world, x=0, y=0,
                        collider=CircleCollider2D(radius=25))
        e2 = _make_body(physics_world, x=30, y=0,
                        collider=CircleCollider2D(radius=25))
        physics_world.update(0.016)
        t1 = e1.get_component(Transform)
        t2 = e2.get_component(Transform)
        dist = abs(t2.x - t1.x)
        # Bodies should be pushed apart (distance increases from initial 30)
        assert dist > 30

    def test_no_collision_far_apart(self, physics_world):
        e1 = _make_body(physics_world, x=0, y=0,
                        collider=BoxCollider2D(width=10, height=10))
        e2 = _make_body(physics_world, x=1000, y=0,
                        collider=BoxCollider2D(width=10, height=10))
        physics_world.update(0.016)
        t2 = e2.get_component(Transform)
        assert t2.x == pytest.approx(1000.0, abs=0.1)

    def test_trigger_collider_no_resolution(self, physics_world):
        e1 = _make_body(physics_world, x=0, y=0,
                        collider=BoxCollider2D(width=50, height=50, is_trigger=True))
        e2 = _make_body(physics_world, x=10, y=0,
                        collider=BoxCollider2D(width=50, height=50))
        physics_world.update(0.016)
        t1 = e1.get_component(Transform)
        # Trigger should not push
        assert t1.x == pytest.approx(0.0, abs=0.5)


class TestCollisionHelpers:
    def test_box_box_collision_no_overlap(self):
        ps = PhysicsSystem()
        a = _Body()
        a.center = Vector2(0, 0)
        a.half_w = 10
        a.half_h = 10
        b = _Body()
        b.center = Vector2(100, 0)
        b.half_w = 10
        b.half_h = 10
        assert ps._box_box_collision(a, b) is None

    def test_box_box_collision_overlap(self):
        ps = PhysicsSystem()
        a = _Body()
        a.center = Vector2(0, 0)
        a.half_w = 20
        a.half_h = 20
        b = _Body()
        b.center = Vector2(15, 0)
        b.half_w = 20
        b.half_h = 20
        result = ps._box_box_collision(a, b)
        assert result is not None
        assert result["penetration"] > 0

    def test_circle_circle_no_overlap(self):
        ps = PhysicsSystem()
        a = _Body()
        a.center = Vector2(0, 0)
        a.radius = 10
        b = _Body()
        b.center = Vector2(100, 0)
        b.radius = 10
        assert ps._circle_circle_collision(a, b) is None

    def test_circle_circle_overlap(self):
        ps = PhysicsSystem()
        a = _Body()
        a.center = Vector2(0, 0)
        a.radius = 20
        b = _Body()
        b.center = Vector2(15, 0)
        b.radius = 20
        result = ps._circle_circle_collision(a, b)
        assert result is not None
        assert result["penetration"] > 0


class TestCollisionInfo:
    def test_collision_info_fields(self):
        info = CollisionInfo(Vector2(1, 0), 5.0)
        assert info.normal == Vector2(1, 0)
        assert info.penetration == 5.0


class TestPhysicsRaycast:
    def test_raycast_hits_box(self, physics_world):
        _make_body(physics_world, x=100, y=0,
                    collider=BoxCollider2D(width=50, height=50))
        ps = physics_world.get_system(PhysicsSystem)
        hits = ps.raycast(Vector2(0, 0), Vector2(1, 0), max_distance=200)
        assert len(hits) >= 1
        assert hits[0]["distance"] < 200

    def test_raycast_hits_circle(self, physics_world):
        _make_body(physics_world, x=100, y=0,
                    collider=CircleCollider2D(radius=25))
        ps = physics_world.get_system(PhysicsSystem)
        hits = ps.raycast(Vector2(0, 0), Vector2(1, 0), max_distance=200)
        assert len(hits) >= 1

    def test_raycast_misses(self, physics_world):
        _make_body(physics_world, x=100, y=100,
                    collider=BoxCollider2D(width=10, height=10))
        ps = physics_world.get_system(PhysicsSystem)
        hits = ps.raycast(Vector2(0, 0), Vector2(1, 0), max_distance=200)
        assert len(hits) == 0

    def test_raycast_first(self, physics_world):
        _make_body(physics_world, x=100, y=0,
                    collider=BoxCollider2D(width=50, height=50))
        ps = physics_world.get_system(PhysicsSystem)
        hit = ps.raycast_first(Vector2(0, 0), Vector2(1, 0), max_distance=200)
        assert hit is not None

    def test_raycast_zero_direction(self, physics_world):
        ps = physics_world.get_system(PhysicsSystem)
        hits = ps.raycast(Vector2(0, 0), Vector2(0, 0), max_distance=200)
        assert hits == []


class TestPhysicsAreaQuery:
    def test_overlap_box(self, physics_world):
        entity = _make_body(physics_world, x=50, y=50,
                            collider=BoxCollider2D(width=20, height=20))
        # Force a physics step to build bodies
        physics_world.update(0.016)
        ps = physics_world.get_system(PhysicsSystem)
        results = ps.overlap_box(Vector2(50, 50), Vector2(100, 100))
        assert entity in results

    def test_overlap_circle(self, physics_world):
        entity = _make_body(physics_world, x=50, y=50,
                            collider=CircleCollider2D(radius=10))
        physics_world.update(0.016)
        ps = physics_world.get_system(PhysicsSystem)
        results = ps.overlap_circle(Vector2(50, 50), 100)
        assert entity in results
