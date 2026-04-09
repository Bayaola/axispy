import pytest
import pygame
from core.scene_transition import SceneTransition
import os

# Pygame needs to be initialized or have a display setup for surfaces
@pytest.fixture(autouse=True)
def init_pygame():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.display.set_mode((800, 600))
    yield
    pygame.quit()

def test_scene_transition_initialization():
    transition = SceneTransition(duration=1.0, color=(255, 0, 0))
    assert transition.duration == 1.0
    assert transition.color == (255, 0, 0)
    assert transition.is_done() == True
    assert transition.is_active() == False

def test_scene_transition_fade_out():
    transition = SceneTransition(duration=1.0)
    transition.start_out()
    
    assert transition.is_active() == True
    assert transition.is_done() == False
    assert transition._alpha == 0.0
    
    # Halfway
    transition.update(0.5)
    assert 120 < transition._alpha < 135 # Rough center
    assert not transition.is_fade_out_done()
    
    # Completed
    transition.update(0.6)
    assert transition._alpha == 255.0
    assert transition.is_fade_out_done() == True
    assert transition.is_done() == True

def test_scene_transition_fade_in():
    transition = SceneTransition(duration=1.0)
    transition.start_in()
    
    assert transition.is_active() == True
    assert transition.is_done() == False
    assert transition._alpha == 255.0
    
    # Halfway
    transition.update(0.5)
    assert 120 < transition._alpha < 135 # Rough center
    assert not transition.is_fade_in_done()
    
    # Completed
    transition.update(0.6)
    assert transition._alpha == 0.0
    assert transition.is_fade_in_done() == True
    assert transition.is_done() == True

def test_scene_transition_draw():
    transition = SceneTransition(duration=1.0)
    surface = pygame.Surface((100, 100))
    
    # Initially done/alpha 0, so drawing does nothing
    transition.draw(surface)
    assert transition._overlay is None
    
    # Start fade out
    transition.start_out()
    transition.update(0.5) # alpha > 0
    transition.draw(surface)
    
    assert transition._overlay is not None
    assert transition._overlay.get_size() == (100, 100)
    
    # Resize screen test
    surface_large = pygame.Surface((200, 200))
    transition.draw(surface_large)
    assert transition._overlay.get_size() == (200, 200)
