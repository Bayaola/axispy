import pytest
import math
from unittest.mock import MagicMock, patch
from core.ecs import World, Entity
from core.components.transform import Transform
from core.components.camera import CameraComponent
from core.components.sound import SoundComponent
from core.systems.audio_system import AudioSystem


def _build_audio_system():
    """Create an AudioSystem without triggering pygame.mixer.init."""
    system = AudioSystem.__new__(AudioSystem)
    system.world = None
    system.update_phase = "simulation"
    system.priority = 0
    system.required_components = (SoundComponent,)
    return system


@pytest.fixture
def audio_world():
    world = World()
    world.add_system(_build_audio_system())
    return world


def _make_sound_entity(world, x=0, y=0, spatialize=True, autoplay=False,
                       min_distance=0.0, max_distance=600.0, pan_distance=300.0):
    entity = world.create_entity("Sound")
    entity.add_component(Transform(x=x, y=y))
    sound = SoundComponent(
        file_path="test.wav",
        spatialize=spatialize,
        autoplay=autoplay,
        min_distance=min_distance,
        max_distance=max_distance,
        pan_distance=pan_distance,
    )
    sound.play = MagicMock()
    sound.apply_output = MagicMock()
    entity.add_component(sound)
    return entity, sound


def _make_camera(world, x=0, y=0, active=True, priority=0):
    entity = world.create_entity("Camera")
    entity.add_component(Transform(x=x, y=y))
    cam = CameraComponent()
    cam.active = active
    cam.priority = priority
    entity.add_component(cam)
    return entity


# ---------------------------------------------------------------------------
# SoundComponent unit tests
# ---------------------------------------------------------------------------

class TestSoundComponent:
    def test_defaults(self):
        s = SoundComponent()
        assert s.file_path == ""
        assert s.volume == 1.0
        assert s.loop is False
        assert s.autoplay is False
        assert s.spatialize is True
        assert s.min_distance == 0.0
        assert s.max_distance == 600.0

    def test_volume_clamped(self):
        s = SoundComponent(volume=2.0)
        assert s.volume == 1.0
        s2 = SoundComponent(volume=-1.0)
        assert s2.volume == 0.0


# ---------------------------------------------------------------------------
# AudioSystem integration tests
# ---------------------------------------------------------------------------

class TestAudioSystem:
    def test_autoplay_triggers_play(self, audio_world):
        entity, sound = _make_sound_entity(audio_world, autoplay=True)
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        sound.play.assert_called_once()

    def test_autoplay_only_once(self, audio_world):
        entity, sound = _make_sound_entity(audio_world, autoplay=True)
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        system.update(0.016, audio_world.entities)
        sound.play.assert_called_once()

    def test_autoplay_no_file_path(self, audio_world):
        entity = audio_world.create_entity("Sound")
        entity.add_component(Transform())
        sound = SoundComponent(autoplay=True, file_path="")
        sound.play = MagicMock()
        sound.apply_output = MagicMock()
        entity.add_component(sound)
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        sound.play.assert_not_called()

    def test_no_camera_sets_default_spatial(self, audio_world):
        entity, sound = _make_sound_entity(audio_world, spatialize=True)
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        assert sound._spatial_attenuation == pytest.approx(1.0)
        assert sound._pan == pytest.approx(0.0)

    def test_spatialization_with_camera(self, audio_world):
        _make_camera(audio_world, x=0, y=0)
        entity, sound = _make_sound_entity(
            audio_world, x=100, y=0, spatialize=True,
            min_distance=0, max_distance=600, pan_distance=300
        )
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        assert 0.0 <= sound._spatial_attenuation <= 1.0
        assert -1.0 <= sound._pan <= 1.0

    def test_sound_beyond_max_distance(self, audio_world):
        _make_camera(audio_world, x=0, y=0)
        entity, sound = _make_sound_entity(
            audio_world, x=1000, y=0, spatialize=True,
            min_distance=0, max_distance=100
        )
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        assert sound._spatial_attenuation == pytest.approx(0.0)

    def test_sound_within_min_distance(self, audio_world):
        _make_camera(audio_world, x=0, y=0)
        entity, sound = _make_sound_entity(
            audio_world, x=5, y=0, spatialize=True,
            min_distance=100, max_distance=600
        )
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        assert sound._spatial_attenuation == pytest.approx(1.0)

    def test_non_spatial_sound(self, audio_world):
        _make_camera(audio_world, x=0, y=0)
        entity, sound = _make_sound_entity(
            audio_world, x=500, y=0, spatialize=False
        )
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        assert sound._spatial_attenuation == pytest.approx(1.0)
        assert sound._pan == pytest.approx(0.0)

    def test_camera_priority_selection(self, audio_world):
        _make_camera(audio_world, x=0, y=0, priority=10)
        _make_camera(audio_world, x=999, y=999, priority=1)
        entity, sound = _make_sound_entity(
            audio_world, x=50, y=0, spatialize=True,
            min_distance=0, max_distance=600
        )
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        # Lower priority camera (1) should be selected — distance ~1363
        # so attenuation should be low
        assert sound._spatial_attenuation < 0.5

    def test_sound_without_transform_no_spatial(self, audio_world):
        _make_camera(audio_world, x=0, y=0)
        entity = audio_world.create_entity("NoTransform")
        sound = SoundComponent(spatialize=True, file_path="x.wav")
        sound.play = MagicMock()
        sound.apply_output = MagicMock()
        entity.add_component(sound)
        system = audio_world.get_system(AudioSystem)
        system.update(0.016, audio_world.entities)
        assert sound._spatial_attenuation == pytest.approx(1.0)
        assert sound._pan == pytest.approx(0.0)
