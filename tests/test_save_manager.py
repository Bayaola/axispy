import pytest
import os
import tempfile
import json
from core.save_manager import SaveManager
from core.ecs import World
from core.scene import Scene

@pytest.fixture
def temp_project_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir

def mock_world_factory():
    world = World()
    world.create_entity("Hero")
    return world

def test_save_manager_ensure_dir(temp_project_dir):
    save_dir = SaveManager._ensure_dir(temp_project_dir)
    assert os.path.exists(save_dir)
    assert os.path.isdir(save_dir)

def test_save_manager_save(temp_project_dir):
    world = mock_world_factory()
    result = SaveManager.save(world, "test_slot", project_dir=temp_project_dir, extra_data={"score": 100})
    
    assert result == True
    
    save_path = os.path.join(temp_project_dir, SaveManager.save_directory, "test_slot.sav")
    assert os.path.exists(save_path)
    
    with open(save_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["slot"] == "test_slot"
    assert data["extra"]["score"] == 100
    assert "scene" in data

def test_save_manager_load(temp_project_dir):
    world = mock_world_factory()
    SaveManager.save(world, "load_slot", project_dir=temp_project_dir)
    
    loaded_scene = SaveManager.load("load_slot", project_dir=temp_project_dir)
    assert loaded_scene is not None
    assert type(loaded_scene) == Scene
    
    # Needs to match at least something!
    hero_found = any(e.name == "Hero" for e in loaded_scene.world.entities)
    assert hero_found

def test_save_manager_load_non_existent(temp_project_dir):
    loaded_scene = SaveManager.load("nonexistent_slot", project_dir=temp_project_dir)
    assert loaded_scene is None

def test_save_manager_load_extra(temp_project_dir):
    world = mock_world_factory()
    SaveManager.save(world, "extra_slot", project_dir=temp_project_dir, extra_data={"level": 5})
    
    extra = SaveManager.load_extra("extra_slot", project_dir=temp_project_dir)
    assert extra is not None
    assert extra["level"] == 5

def test_save_manager_exists_and_delete(temp_project_dir):
    world = mock_world_factory()
    
    assert SaveManager.exists("del_slot", project_dir=temp_project_dir) == False
    SaveManager.save(world, "del_slot", project_dir=temp_project_dir)
    assert SaveManager.exists("del_slot", project_dir=temp_project_dir) == True
    
    # Test delete
    assert SaveManager.delete("del_slot", project_dir=temp_project_dir) == True
    assert SaveManager.exists("del_slot", project_dir=temp_project_dir) == False
    assert SaveManager.delete("del_slot", project_dir=temp_project_dir) == False

def test_save_manager_list_saves(temp_project_dir):
    world = mock_world_factory()
    SaveManager.save(world, "slot_1", project_dir=temp_project_dir)
    SaveManager.save(world, "slot_2", project_dir=temp_project_dir)
    
    saves = SaveManager.list_saves(project_dir=temp_project_dir)
    assert len(saves) == 2
    
    slots = [s["slot"] for s in saves]
    assert "slot_1" in slots
    assert "slot_2" in slots
