import pytest
import math
from unittest.mock import MagicMock, patch
from core.ecs import World
from core.components.transform import Transform
from core.components.camera import CameraComponent


# We need pygame stubs for RenderSystem
@pytest.fixture(autouse=True)
def _init_pygame():
    import pygame
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    yield


@pytest.fixture
def surface():
    import pygame
    return pygame.Surface((800, 600))


@pytest.fixture
def render_world(surface):
    from core.systems.render_system import RenderSystem
    world = World()
    rs = RenderSystem(surface)
    world.add_system(rs)
    return world, rs


class TestRenderSystemCreation:
    def test_render_phase(self, render_world):
        _, rs = render_world
        assert rs.update_phase == "render"

    def test_default_camera_values(self, render_world):
        _, rs = render_world
        assert rs.camera_x == 0.0
        assert rs.camera_y == 0.0
        assert rs.camera_zoom == 1.0
        assert rs.camera_rotation == 0.0

    def test_surface_size(self, render_world):
        _, rs = render_world
        w, h = rs._surface_size()
        assert w == 800
        assert h == 600


class TestCameraViews:
    def test_fallback_camera_when_no_components(self, render_world):
        world, rs = render_world
        views = rs.get_camera_views([])
        assert len(views) == 1
        assert views[0]["entity"] is None

    def test_camera_component_view(self, render_world):
        world, rs = render_world
        entity = world.create_entity("Cam")
        entity.add_component(Transform(x=100, y=200))
        cam = CameraComponent()
        cam.active = True
        cam.zoom = 2.0
        entity.add_component(cam)
        views = rs.get_camera_views(world.entities)
        assert len(views) >= 1
        assert views[0]["zoom"] == 2.0

    def test_inactive_camera_ignored(self, render_world):
        world, rs = render_world
        entity = world.create_entity("Cam")
        entity.add_component(Transform(x=0, y=0))
        cam = CameraComponent()
        cam.active = False
        entity.add_component(cam)
        views = rs.get_camera_views(world.entities)
        # Should fall back to default
        assert views[0]["entity"] is None

    def test_primary_camera_view(self, render_world):
        world, rs = render_world
        view = rs.get_primary_camera_view([])
        assert view is not None
        assert "x" in view
        assert "zoom" in view


class TestWorldScreenConversion:
    def test_world_to_screen_center(self, render_world):
        world, rs = render_world
        sx, sy = rs.world_to_screen(0, 0, [])
        assert sx == pytest.approx(400.0)
        assert sy == pytest.approx(300.0)

    def test_screen_to_world_center(self, render_world):
        world, rs = render_world
        wx, wy = rs.screen_to_world(400, 300, [])
        assert wx == pytest.approx(0.0, abs=1.0)
        assert wy == pytest.approx(0.0, abs=1.0)

    def test_roundtrip_conversion(self, render_world):
        world, rs = render_world
        wx, wy = 150.0, -75.0
        sx, sy = rs.world_to_screen(wx, wy, [])
        wx2, wy2 = rs.screen_to_world(sx, sy, [])
        assert wx2 == pytest.approx(wx, abs=0.1)
        assert wy2 == pytest.approx(wy, abs=0.1)

    def test_zoom_affects_conversion(self, render_world):
        world, rs = render_world
        rs.camera_zoom = 2.0
        rs.use_camera_components = False
        sx1, _ = rs.world_to_screen(100, 0, [])
        rs.camera_zoom = 1.0
        sx2, _ = rs.world_to_screen(100, 0, [])
        # At higher zoom, same world point is further from center in screen space
        assert abs(sx1 - 400) > abs(sx2 - 400)


class TestRenderSystemUpdate:
    def test_update_does_not_crash_empty_world(self, render_world):
        world, rs = render_world
        world.update(0.016)  # Should not crash

    def test_update_with_entity(self, render_world):
        import pygame
        world, rs = render_world
        entity = world.create_entity("Sprite")
        entity.add_component(Transform(x=0, y=0))
        # Manually add a mock sprite
        from core.components.sprite_renderer import SpriteRenderer
        sprite = MagicMock(spec=SpriteRenderer)
        sprite.image = pygame.Surface((32, 32))
        sprite.width = 32
        sprite.height = 32
        entity.components[SpriteRenderer] = sprite
        sprite.entity = entity
        world._component_cache.setdefault(SpriteRenderer, set()).add(entity)
        world.update(0.016)  # Should render without crash

    def test_skip_ui_render_flag(self, render_world):
        world, rs = render_world
        rs.skip_ui_render = True
        rs.render_ui = MagicMock()
        world.update(0.016)
        rs.render_ui.assert_not_called()
