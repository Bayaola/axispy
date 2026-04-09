from core.scene import Scene
from core.components import Transform, CameraComponent

def test_scene_initialization():
    scene = Scene("TestScene")
    assert scene.name == "TestScene"
    assert scene.world is not None
    assert scene._file_path == ""

def test_scene_ensure_main_camera():
    scene = Scene()
    
    main_camera_entity = scene.ensure_main_camera()
    
    # Check that it created a camera
    assert main_camera_entity.name == "Main Camera"
    assert main_camera_entity.get_component(CameraComponent) is not None
    assert main_camera_entity.get_component(Transform) is not None

def test_scene_ensure_main_camera_existing():
    scene = Scene()
    
    # Create main camera manually
    existing_cam = scene.world.create_entity("Main Camera")
    existing_cam.add_component(CameraComponent())
    existing_cam.add_component(Transform())
    
    # ensure_main_camera should find the existing one
    returned_cam = scene.ensure_main_camera()
    
    assert returned_cam == existing_cam
    
    # Check that another camera wasn't created
    camera_count = sum(1 for e in scene.world.entities if e.get_component(CameraComponent) is not None)
    assert camera_count == 1

def test_scene_setup_default():
    scene = Scene()
    scene.setup_default()
    
    # setup_default should create a camera and a square
    has_camera = False
    has_square = False
    
    for entity in scene.world.entities:
        if entity.name == "Main Camera":
            has_camera = True
        elif entity.name == "Square":
            has_square = True
            
    assert has_camera
    assert has_square

def test_scene_update():
    scene = Scene()
    
    # Just checking it doesn't crash to call the world update
    scene.update(0.16)
