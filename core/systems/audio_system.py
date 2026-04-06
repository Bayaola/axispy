
import pygame
import math
from core.ecs import System, Entity
from core.components import Transform, CameraComponent
from core.components.sound import SoundComponent
from core.logger import get_logger

_audio_logger = get_logger("audio")

class AudioSystem(System):
    required_components = (SoundComponent,)

    def __init__(self):
        super().__init__()
        # Initialize mixer if not already done
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as e:
                _audio_logger.error("Failed to initialize pygame mixer", error=str(e))
                
    def update(self, dt: float, entities: list[Entity]):
        # Handle autoplay for sounds that haven't played yet
        # Use cached entities if possible
        if self.world:
            target_entities = self.world.get_entities_with(SoundComponent)
        else:
            target_entities = entities

        for entity in target_entities:
            sound = entity.get_component(SoundComponent)
            if sound and sound.autoplay:
                if not getattr(sound, "_autoplay_handled", False):
                    # Only try to play if we have a file path
                    if sound.file_path:
                        sound.play()
                        # Mark as handled so we don't restart it every frame
                        sound._autoplay_handled = True

        camera_transform = self._get_active_camera_transform(entities)

        for entity in target_entities:
            sound = entity.get_component(SoundComponent)
            if not sound:
                continue

            if camera_transform is None or not sound.spatialize:
                sound.set_spatial(1.0, 0.0)
                continue

            source_transform = entity.get_component(Transform)
            if not source_transform:
                sound.set_spatial(1.0, 0.0)
                continue

            dx = float(source_transform.x) - float(camera_transform.x)
            dy = float(source_transform.y) - float(camera_transform.y)
            distance = math.hypot(dx, dy)

            min_distance = max(0.0, float(sound.min_distance))
            max_distance = max(min_distance, float(sound.max_distance))

            if max_distance <= min_distance:
                attenuation = 1.0 if distance <= min_distance else 0.0
            elif distance <= min_distance:
                attenuation = 1.0
            elif distance >= max_distance:
                attenuation = 0.0
            else:
                attenuation = 1.0 - ((distance - min_distance) / (max_distance - min_distance))

            pan_distance = max(0.0001, float(sound.pan_distance))
            pan = max(-1.0, min(1.0, dx / pan_distance))

            sound.set_spatial(attenuation, pan)

    def _get_active_camera_transform(self, entities: list[Entity]):
        if self.world:
            camera_entities = self.world.get_entities_with(Transform, CameraComponent)
        else:
            camera_entities = entities

        active_cameras = []
        for entity in camera_entities:
            transform = entity.get_component(Transform)
            camera = entity.get_component(CameraComponent)
            if not transform or not camera or not camera.active:
                continue
            active_cameras.append((camera.priority, transform))

        if not active_cameras:
            return None

        active_cameras.sort(key=lambda entry: entry[0])
        return active_cameras[0][1]
