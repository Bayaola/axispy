import pytest
import math
from unittest.mock import MagicMock, patch
from core.ecs import World, Entity
from core.vector import Vector2
from core.components.transform import Transform
from core.components.light import PointLight2D, SpotLight2D, LightOccluder2D


@pytest.fixture(autouse=True)
def _init_pygame():
    import pygame
    if not pygame.get_init():
        pygame.init()
    yield


@pytest.fixture
def surface():
    import pygame
    return pygame.Surface((800, 600))


@pytest.fixture
def lighting_world(surface):
    from core.systems.lighting_system import LightingSystem
    world = World()
    ls = LightingSystem(surface)
    world.add_system(ls)
    return world, ls


# ---------------------------------------------------------------------------
# Light component unit tests
# ---------------------------------------------------------------------------

class TestPointLight2D:
    def test_defaults(self):
        p = PointLight2D()
        assert p.color == (255, 255, 255)
        assert p.radius == 200.0
        assert p.intensity == 1.0
        assert p.falloff == 2.0

    def test_custom_values(self):
        p = PointLight2D(color=(255, 0, 0), radius=500, intensity=2.0, falloff=3.0)
        assert p.color == (255, 0, 0)
        assert p.radius == 500.0
        assert p.intensity == 2.0

    def test_radius_min_clamp(self):
        p = PointLight2D(radius=0)
        assert p.radius == 1.0

    def test_intensity_min_clamp(self):
        p = PointLight2D(intensity=-5)
        assert p.intensity == 0.0


class TestSpotLight2D:
    def test_defaults(self):
        s = SpotLight2D()
        assert s.radius == 300.0
        assert s.cone_angle == 45.0
        assert s.angle == 0.0

    def test_cone_angle_clamped(self):
        s = SpotLight2D(cone_angle=0)
        assert s.cone_angle == 1.0
        s2 = SpotLight2D(cone_angle=999)
        assert s2.cone_angle == 180.0

    def test_offset(self):
        s = SpotLight2D(offset_x=10, offset_y=20)
        assert s.offset_x == 10.0
        assert s.offset_y == 20.0


class TestLightOccluder2D:
    def test_defaults(self):
        o = LightOccluder2D()
        assert o.shape == "box"
        assert o.width == 50.0
        assert o.height == 50.0

    def test_circle_shape(self):
        o = LightOccluder2D(shape="circle", radius=30)
        assert o.shape == "circle"
        assert o.radius == 30.0

    def test_polygon_shape_default_points(self):
        o = LightOccluder2D(shape="polygon")
        assert o.shape == "polygon"
        assert len(o.points) >= 3

    def test_polygon_custom_points(self):
        pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
        o = LightOccluder2D(shape="polygon", points=pts)
        assert len(o.points) == 4

    def test_invalid_shape_defaults_to_box(self):
        o = LightOccluder2D(shape="invalid")
        assert o.shape == "box"

    def test_receive_flags(self):
        o = LightOccluder2D(receive_light=True, receive_shadow=True)
        assert o.receive_light is True
        assert o.receive_shadow is True


# ---------------------------------------------------------------------------
# LightingSystem integration tests
# ---------------------------------------------------------------------------

class TestLightingSystemCreation:
    def test_render_phase(self, lighting_world):
        _, ls = lighting_world
        assert ls.update_phase == "render"

    def test_required_components(self, lighting_world):
        _, ls = lighting_world
        # LightingSystem has no required_components — it always runs
        # and queries lights internally
        assert ls.required_components == ()


class TestLightingSystemUpdate:
    def test_no_crash_empty_world(self, lighting_world):
        world, ls = lighting_world
        world.update(0.016)

    def test_point_light_renders(self, lighting_world):
        world, ls = lighting_world
        entity = world.create_entity("Light")
        entity.add_component(Transform(x=400, y=300))
        entity.add_component(PointLight2D(radius=200, intensity=1.0))
        world.update(0.016)  # Should not crash

    def test_spot_light_renders(self, lighting_world):
        world, ls = lighting_world
        entity = world.create_entity("Spot")
        entity.add_component(Transform(x=400, y=300))
        entity.add_component(SpotLight2D(radius=200, angle=45, cone_angle=30))
        world.update(0.016)

    def test_occluder_renders(self, lighting_world):
        world, ls = lighting_world
        light_entity = world.create_entity("Light")
        light_entity.add_component(Transform(x=100, y=100))
        light_entity.add_component(PointLight2D(radius=300))

        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=200, y=100))
        wall.add_component(LightOccluder2D(shape="box", width=50, height=100))
        world.update(0.016)

    def test_multiple_lights(self, lighting_world):
        world, ls = lighting_world
        for i in range(3):
            e = world.create_entity(f"Light{i}")
            e.add_component(Transform(x=i * 100, y=100))
            e.add_component(PointLight2D(radius=150))
        world.update(0.016)

    def test_light_without_transform_skipped(self, lighting_world):
        world, ls = lighting_world
        entity = world.create_entity("NoTransform")
        entity.add_component(PointLight2D(radius=200))
        world.update(0.016)  # Should not crash

    def test_ambient_color(self, lighting_world):
        _, ls = lighting_world
        ls.ambient_color = (50, 50, 50)
        assert ls.ambient_color == (50, 50, 50)

    def test_occluder_circle_shape(self, lighting_world):
        world, ls = lighting_world
        light = world.create_entity("Light")
        light.add_component(Transform(x=100, y=100))
        light.add_component(PointLight2D(radius=300))

        occ = world.create_entity("CircleOcc")
        occ.add_component(Transform(x=200, y=100))
        occ.add_component(LightOccluder2D(shape="circle", radius=25))
        world.update(0.016)

    def test_occluder_polygon_shape(self, lighting_world):
        world, ls = lighting_world
        light = world.create_entity("Light")
        light.add_component(Transform(x=100, y=100))
        light.add_component(PointLight2D(radius=300))

        occ = world.create_entity("PolyOcc")
        occ.add_component(Transform(x=200, y=100))
        occ.add_component(LightOccluder2D(
            shape="polygon",
            points=[(0, 0), (30, 0), (30, 30), (0, 30)]
        ))
        world.update(0.016)
