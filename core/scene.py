from core.ecs import World
from core.components import Transform, CameraComponent, SpriteRenderer

class Scene:
    def __init__(self, name: str = "SampleScene"):
        self.name = name
        self.world = World()
        self._file_path: str = ""  # Path to the scene file when saved/loaded
        
    def setup_default(self):
        self.ensure_main_camera()
        
        cube = self.world.create_entity("Square")
        cube.add_component(Transform(x=400, y=300))
        cube.add_component(SpriteRenderer(color=(0, 200, 100), width=64, height=64))
        
        # Attach sample script
        from core.components.script import ScriptComponent
        import os
        script_path = os.path.join("projects", "default_project", "player_script.py")
        cube.add_component(ScriptComponent(script_path=script_path, class_name="PlayerController"))

    def ensure_main_camera(self):
        for entity in self.world.entities:
            if entity.name != "Main Camera":
                continue
            camera = entity.get_component(CameraComponent)
            if camera:
                if not entity.get_component(Transform):
                    entity.add_component(Transform(x=400, y=300))
                return entity
        root = self.world.create_entity("Main Camera")
        root.add_component(Transform(x=400, y=300))
        root.add_component(CameraComponent(active=True, priority=0, zoom=1.0))
        return root
        
    def update(self, dt: float):
        self.world.update(dt)
