import pytest
import os
import tempfile
from core.ecs import World
from core.components.script import ScriptComponent
from core.systems.script_system import ScriptSystem


@pytest.fixture
def script_world():
    world = World()
    world.add_system(ScriptSystem())
    return world


@pytest.fixture
def temp_script():
    """Create a temporary script file and clean it up after the test."""
    content = '''
class TestScript:
    def on_start(self):
        self.started = True
        self.update_count = 0

    def on_update(self, dt):
        self.update_count += 1
        self.last_dt = dt
'''
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def temp_script_with_destroy():
    content = '''
class DestroyScript:
    def on_start(self):
        self.destroyed = False

    def on_destroy(self):
        self.destroyed = True
'''
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def temp_script_error():
    content = '''
class ErrorScript:
    def on_start(self):
        raise RuntimeError("start error")

    def on_update(self, dt):
        raise RuntimeError("update error")
'''
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# ScriptComponent unit tests
# ---------------------------------------------------------------------------

class TestScriptComponent:
    def test_defaults(self):
        sc = ScriptComponent()
        assert sc.script_path == ""
        assert sc.class_name == ""
        assert sc.instance is None
        assert sc.started is False

    def test_find_without_world(self):
        sc = ScriptComponent()
        sc.entity = None
        assert sc.find("something") is None


# ---------------------------------------------------------------------------
# ScriptSystem unit tests
# ---------------------------------------------------------------------------

class TestScriptSystem:
    def test_system_required_components(self):
        s = ScriptSystem()
        assert ScriptComponent in s.required_components

    def test_normalize_script_path(self):
        s = ScriptSystem()
        result = s._normalize_script_path("some/path.py")
        assert os.path.isabs(result)

    def test_build_module_key(self):
        s = ScriptSystem()
        key = s._build_module_key("test_script.py")
        assert key.startswith("axispy_script_test_script_")

    def test_resolve_nonexistent_returns_input(self):
        s = ScriptSystem()
        result = s.resolve_script_path("nonexistent_path_12345.py")
        assert "nonexistent_path_12345.py" in result

    def test_resolve_empty_returns_empty(self):
        s = ScriptSystem()
        assert s.resolve_script_path("") == ""


# ---------------------------------------------------------------------------
# ScriptSystem integration tests
# ---------------------------------------------------------------------------

class TestScriptSystemIntegration:
    def test_loads_and_starts_script(self, script_world, temp_script):
        entity = script_world.create_entity("Scripted")
        entity.add_component(ScriptComponent(
            script_path=temp_script, class_name="TestScript"
        ))
        script_world.update(0.016)
        sc = entity.get_component(ScriptComponent)
        assert sc.instance is not None
        assert sc.started is True
        assert hasattr(sc.instance, "started")
        assert sc.instance.started is True

    def test_calls_on_update(self, script_world, temp_script):
        entity = script_world.create_entity("Scripted")
        entity.add_component(ScriptComponent(
            script_path=temp_script, class_name="TestScript"
        ))
        script_world.update(0.016)
        script_world.update(0.016)
        sc = entity.get_component(ScriptComponent)
        assert sc.instance.update_count == 2

    def test_missing_file_does_not_crash(self, script_world):
        entity = script_world.create_entity("Missing")
        entity.add_component(ScriptComponent(
            script_path="/nonexistent/path.py", class_name="Foo"
        ))
        script_world.update(0.016)
        sc = entity.get_component(ScriptComponent)
        assert sc.instance is None

    def test_missing_class_does_not_crash(self, script_world, temp_script):
        entity = script_world.create_entity("BadClass")
        entity.add_component(ScriptComponent(
            script_path=temp_script, class_name="NonExistentClass"
        ))
        script_world.update(0.016)
        sc = entity.get_component(ScriptComponent)
        assert sc.instance is None

    def test_empty_path_unloads_existing(self, script_world, temp_script):
        entity = script_world.create_entity("Scripted")
        sc = ScriptComponent(script_path=temp_script, class_name="TestScript")
        entity.add_component(sc)
        script_world.update(0.016)
        assert sc.instance is not None
        sc.script_path = ""
        sc.class_name = ""
        script_world.update(0.016)
        assert sc.instance is None

    def test_error_in_on_start_does_not_crash(self, script_world, temp_script_error):
        entity = script_world.create_entity("ErrScript")
        entity.add_component(ScriptComponent(
            script_path=temp_script_error, class_name="ErrorScript"
        ))
        script_world.update(0.016)  # Should not raise

    def test_error_in_on_update_does_not_crash(self, script_world, temp_script_error):
        entity = script_world.create_entity("ErrScript")
        entity.add_component(ScriptComponent(
            script_path=temp_script_error, class_name="ErrorScript"
        ))
        script_world.update(0.016)
        script_world.update(0.016)  # Should not raise

    def test_entity_ref_injected(self, script_world, temp_script):
        entity = script_world.create_entity("Scripted")
        entity.add_component(ScriptComponent(
            script_path=temp_script, class_name="TestScript"
        ))
        script_world.update(0.016)
        sc = entity.get_component(ScriptComponent)
        assert sc.instance.entity is entity

    def test_unload_script(self, script_world, temp_script):
        ss = script_world.get_system(ScriptSystem)
        entity = script_world.create_entity("Scripted")
        sc = ScriptComponent(script_path=temp_script, class_name="TestScript")
        entity.add_component(sc)
        script_world.update(0.016)
        assert sc.instance is not None
        ss.unload_script(sc)
        assert sc.instance is None
        assert sc.started is False
