
from core.ecs import Component
from core.resources import ResourceManager
import pygame
import os
from core.logger import get_logger

_sound_logger = get_logger("sound")

class SoundComponent(Component):
    def __init__(
        self,
        file_path="",
        volume=1.0,
        loop=False,
        is_music=False,
        autoplay=False,
        spatialize=True,
        min_distance=0.0,
        max_distance=600.0,
        pan_distance=300.0
    ):
        self.file_path = file_path
        self.volume = max(0.0, min(1.0, volume))
        self.loop = loop
        self.is_music = is_music
        self.autoplay = autoplay
        self.spatialize = bool(spatialize)
        self.min_distance = max(0.0, float(min_distance))
        self.max_distance = max(self.min_distance, float(max_distance))
        self.pan_distance = max(0.0001, float(pan_distance))
        
        self._sound = None
        self._loaded_path = None
        self._autoplay_handled = False
        self._is_paused = False
        self._channel = None
        self._spatial_attenuation = 1.0
        self._pan = 0.0

    def load(self) -> bool:
        """Loads the sound resource."""
        if ResourceManager._headless:
            return False
        if not self.file_path:
            return False
            
        if self.is_music:
            # For music, we just verify the path exists. Streaming happens on play.
            path = ResourceManager.resolve_path(self.file_path)
            if os.path.exists(path):
                self._loaded_path = path
                return True
            _sound_logger.warning("Music file not found", path=path, original=self.file_path)
            return False
        else:
            # For sound effects, load into memory via ResourceManager
            self._sound = ResourceManager.load_sound(self.file_path)
            if self._sound:
                self._sound.set_volume(self.volume)
                return True
            return False

    def play(self):
        """Plays the sound or music."""
        if ResourceManager._headless:
            return
        # Ensure loaded
        if self.is_music:
            if not self._loaded_path:
                if not self.load():
                    return
            
            try:
                # Initialize mixer if not already done (safety check)
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                    
                pygame.mixer.music.load(self._loaded_path)
                pygame.mixer.music.set_volume(self._effective_volume())
                loops = -1 if self.loop else 0
                pygame.mixer.music.play(loops)
                self._is_paused = False
            except Exception as e:
                _sound_logger.error("Failed to play music", path=self._loaded_path, error=str(e))
        else:
            if not self._sound:
                if not self.load():
                    return
            
            if self._sound:
                loops = -1 if self.loop else 0
                self._channel = self._sound.play(loops)
                self.apply_output()

    def stop(self):
        """Stops playback."""
        if self.is_music:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        elif self._sound:
            self._sound.stop()
            self._channel = None
            
    def pause(self):
        """Pauses playback."""
        if self.is_music:
            if pygame.mixer.get_init():
                pygame.mixer.music.pause()
                self._is_paused = True
        # Sound effects in pygame don't have individual pause, only stop.
        # But mixer.pause() pauses ALL channels. We probably don't want that for individual sounds.
        # So for SFX, pause is often not supported per-sound without a channel reference.
        # We'll skip SFX pause for now unless we manage channels.
    
    def unpause(self):
        """Resumes playback."""
        if self.is_music:
            if pygame.mixer.get_init() and self._is_paused:
                pygame.mixer.music.unpause()
                self._is_paused = False

    def set_volume(self, volume: float):
        """Sets the volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        self.apply_output()

    def set_spatial(self, attenuation: float, pan: float):
        self._spatial_attenuation = max(0.0, min(1.0, float(attenuation)))
        self._pan = max(-1.0, min(1.0, float(pan)))
        self.apply_output()

    def _effective_volume(self) -> float:
        return max(0.0, min(1.0, self.volume * self._spatial_attenuation))

    def apply_output(self):
        effective_volume = self._effective_volume()

        if self.is_music:
            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(effective_volume)
            return

        # Try to use the channel if we have one and it's still playing
        if self._channel:
            # Check if channel is still active
            if hasattr(self._channel, "get_busy") and self._channel.get_busy():
                pan = self._pan
                left = effective_volume * (1.0 - max(0.0, pan))
                right = effective_volume * (1.0 + min(0.0, pan))
                self._channel.set_volume(max(0.0, min(1.0, left)), max(0.0, min(1.0, right)))
                return
            else:
                # Channel is no longer playing, clear reference
                self._channel = None

        # If no active channel, set volume on the sound object for next play
        if self._sound:
            self._sound.set_volume(effective_volume)

    def on_destroy(self):
        self.stop()
