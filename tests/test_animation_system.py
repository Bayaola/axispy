import pytest
from unittest.mock import MagicMock, PropertyMock, patch
from core.ecs import World, Entity
from core.components.transform import Transform
from core.components.animator import AnimatorComponent
from core.components.sprite_renderer import SpriteRenderer
from core.systems.animation_system import AnimationSystem
from core.animation import AnimationClip, AnimationController


@pytest.fixture
def anim_world():
    world = World()
    world.add_system(AnimationSystem())
    return world


def _make_mock_frame(w=32, h=32):
    frame = MagicMock()
    frame.get_width.return_value = w
    frame.get_height.return_value = h
    return frame


def _make_clip(frames=None, fps=10, loop=True, name="clip"):
    clip = MagicMock(spec=AnimationClip)
    clip.name = name
    clip.fps = fps
    clip.loop = loop
    clip.frames = frames or [_make_mock_frame() for _ in range(4)]
    return clip


def _make_animator_entity(world, clip=None, playing=True, speed=1.0):
    entity = world.create_entity("AnimEntity")
    entity.add_component(Transform(x=0, y=0))
    animator = AnimatorComponent.__new__(AnimatorComponent)
    animator.entity = None
    animator.controller_path = None
    animator.play_on_start = True
    animator.speed = speed
    animator.controller = None
    animator.current_state = None
    animator.current_clip = clip
    animator.current_frame_index = 0
    animator._frame_timer = 0.0
    animator.is_playing = playing
    animator.is_paused = False
    animator._trigger_events = set()
    animator._controller_file_path = ""
    animator._controller_mtime = None
    entity.add_component(animator)
    sprite = MagicMock(spec=SpriteRenderer)
    sprite.image = None
    sprite._local_width = 50
    sprite._local_height = 50
    entity.components[SpriteRenderer] = sprite
    sprite.entity = entity
    return entity, animator, sprite


# ---------------------------------------------------------------------------
# AnimatorComponent unit tests
# ---------------------------------------------------------------------------

class TestAnimatorComponent:
    def test_default_values(self):
        a = AnimatorComponent.__new__(AnimatorComponent)
        a.entity = None
        a.controller_path = None
        a.play_on_start = True
        a.speed = 1.0
        a.controller = None
        a.current_state = None
        a.current_clip = None
        a.current_frame_index = 0
        a._frame_timer = 0.0
        a.is_playing = False
        a.is_paused = False
        a._trigger_events = set()
        a._controller_file_path = ""
        a._controller_mtime = None
        assert a.is_playing is False
        assert a.current_frame_index == 0

    def test_get_current_frame_no_clip(self):
        a = AnimatorComponent.__new__(AnimatorComponent)
        a.current_clip = None
        assert a.get_current_frame() is None

    def test_get_current_frame_with_frames(self):
        a = AnimatorComponent.__new__(AnimatorComponent)
        frame = _make_mock_frame()
        clip = _make_clip(frames=[frame])
        a.current_clip = clip
        a.current_frame_index = 0
        assert a.get_current_frame() is frame

    def test_get_current_frame_index_clamped(self):
        a = AnimatorComponent.__new__(AnimatorComponent)
        frames = [_make_mock_frame(), _make_mock_frame()]
        a.current_clip = _make_clip(frames=frames)
        a.current_frame_index = 999
        result = a.get_current_frame()
        assert result is frames[-1]

    def test_trigger_system(self):
        a = AnimatorComponent.__new__(AnimatorComponent)
        a._trigger_events = set()
        a.set_trigger("jump")
        assert "jump" in a._trigger_events
        assert a.consume_trigger("jump") is True
        assert a.consume_trigger("jump") is False

    def test_keep_only_triggers(self):
        a = AnimatorComponent.__new__(AnimatorComponent)
        a._trigger_events = {"a", "b", "c"}
        a.keep_only_triggers({"a", "c"})
        assert a._trigger_events == {"a", "c"}

    def test_pause_resume(self):
        a = AnimatorComponent.__new__(AnimatorComponent)
        a.is_playing = True
        a.is_paused = False
        a.pause()
        assert a.is_paused is True
        a.resume()
        assert a.is_paused is False

    def test_stop_resets(self):
        a = AnimatorComponent.__new__(AnimatorComponent)
        a.is_playing = True
        a.is_paused = True
        a.current_frame_index = 5
        a._frame_timer = 1.0
        a.stop(reset=True)
        assert a.is_playing is False
        assert a.is_paused is False
        assert a.current_frame_index == 0
        assert a._frame_timer == 0.0


# ---------------------------------------------------------------------------
# AnimationSystem integration tests
# ---------------------------------------------------------------------------

class TestAnimationSystem:
    def test_system_required_components(self):
        s = AnimationSystem()
        assert AnimatorComponent in s.required_components

    def test_advances_frame_index(self, anim_world):
        clip = _make_clip(fps=10, loop=True)
        entity, animator, sprite = _make_animator_entity(anim_world, clip=clip)
        # Patch reload to no-op since no file
        animator.reload_controller_if_changed = lambda: None
        anim_world.update(0.15)  # 1.5 frames at 10fps
        assert animator.current_frame_index >= 1

    def test_updates_sprite_image(self, anim_world):
        clip = _make_clip(fps=10, loop=True)
        entity, animator, sprite = _make_animator_entity(anim_world, clip=clip)
        animator.reload_controller_if_changed = lambda: None
        anim_world.update(0.016)
        assert sprite.image is not None

    def test_paused_animator_shows_frame_but_no_advance(self, anim_world):
        clip = _make_clip(fps=10, loop=True)
        entity, animator, sprite = _make_animator_entity(anim_world, clip=clip)
        animator.is_paused = True
        animator.reload_controller_if_changed = lambda: None
        anim_world.update(0.5)
        # Frame index should not have advanced
        assert animator.current_frame_index == 0

    def test_not_playing_shows_current_frame(self, anim_world):
        clip = _make_clip(fps=10, loop=True)
        entity, animator, sprite = _make_animator_entity(
            anim_world, clip=clip, playing=False
        )
        animator.reload_controller_if_changed = lambda: None
        anim_world.update(0.016)
        # Should still set sprite image to current frame
        assert sprite.image is not None

    def test_no_clip_skipped(self, anim_world):
        entity, animator, sprite = _make_animator_entity(anim_world, clip=None)
        animator.reload_controller_if_changed = lambda: None
        anim_world.update(0.016)  # Should not crash

    def test_empty_frames_skipped(self, anim_world):
        clip = _make_clip(frames=[])
        entity, animator, sprite = _make_animator_entity(anim_world, clip=clip)
        animator.reload_controller_if_changed = lambda: None
        anim_world.update(0.016)  # Should not crash

    def test_looping_wraps_frame_index(self, anim_world):
        frames = [_make_mock_frame() for _ in range(2)]
        clip = _make_clip(frames=frames, fps=10, loop=True)
        entity, animator, sprite = _make_animator_entity(anim_world, clip=clip)
        animator.reload_controller_if_changed = lambda: None
        # At 10fps, 2 frames: after 0.25s we should have wrapped
        anim_world.update(0.25)
        assert 0 <= animator.current_frame_index < 2

    def test_non_looping_stops_at_last_frame(self, anim_world):
        frames = [_make_mock_frame() for _ in range(3)]
        clip = _make_clip(frames=frames, fps=10, loop=False)
        entity, animator, sprite = _make_animator_entity(anim_world, clip=clip)
        animator.reload_controller_if_changed = lambda: None
        # Play long enough to reach the end
        anim_world.update(1.0)
        assert animator.current_frame_index == 2

    def test_speed_multiplier(self, anim_world):
        frames = [_make_mock_frame() for _ in range(10)]
        clip = _make_clip(frames=frames, fps=10, loop=True)
        entity, animator, sprite = _make_animator_entity(
            anim_world, clip=clip, speed=2.0
        )
        animator.reload_controller_if_changed = lambda: None
        anim_world.update(0.1)  # At 2x speed, 20fps => 2 frames in 0.1s
        assert animator.current_frame_index >= 1

    def test_entity_without_sprite_skipped(self, anim_world):
        entity = anim_world.create_entity("NoSprite")
        entity.add_component(Transform())
        animator = AnimatorComponent.__new__(AnimatorComponent)
        animator.entity = None
        animator.controller_path = None
        animator.play_on_start = True
        animator.speed = 1.0
        animator.controller = None
        animator.current_state = None
        animator.current_clip = _make_clip()
        animator.current_frame_index = 0
        animator._frame_timer = 0.0
        animator.is_playing = True
        animator.is_paused = False
        animator._trigger_events = set()
        animator._controller_file_path = ""
        animator._controller_mtime = None
        entity.add_component(animator)
        anim_world.update(0.016)  # Should not crash
