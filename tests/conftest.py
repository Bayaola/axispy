import pytest
from core.ecs import World, Entity, Component, System


@pytest.fixture
def world():
    """Fixture providing a fresh World instance for each test."""
    return World()


@pytest.fixture
def entity(world):
    """Fixture providing an entity created in a world."""
    return world.create_entity("TestEntity")


class SimpleComponent(Component):
    """A simple test component."""
    def __init__(self, value=0):
        self.value = value


class AnotherComponent(Component):
    """Another test component."""
    def __init__(self, name="test"):
        self.name = name


class DestroyableComponent(Component):
    """A component that tracks if on_destroy was called."""
    def __init__(self):
        self.destroyed = False
    
    def on_destroy(self):
        self.destroyed = True


class SimpleSystem(System):
    """A simple test system."""
    def __init__(self):
        super().__init__()
        self.update_count = 0
        self.last_dt = 0
    
    def update(self, dt: float, entities):
        self.update_count += 1
        self.last_dt = dt


class ComponentRequiringSystem(System):
    """A system that requires specific components."""
    required_components = (SimpleComponent,)
    
    def __init__(self):
        super().__init__()
        self.update_count = 0
    
    def update(self, dt: float, entities):
        self.update_count += 1
