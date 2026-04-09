import pytest
from core.ecs import Component
from conftest import SimpleComponent, AnotherComponent, DestroyableComponent


class TestComponentCreation:
    """Tests for component creation and basic properties."""
    
    def test_create_simple_component(self):
        """Should be able to create a simple component."""
        component = SimpleComponent(42)
        assert component.value == 42
    
    def test_component_repr(self):
        """Component should have a readable string representation."""
        component = SimpleComponent()
        repr_str = repr(component)
        assert "SimpleComponent" in repr_str


class TestComponentInheritance:
    """Tests for component inheritance."""
    
    def test_custom_component_inherits_from_component(self):
        """Custom components should inherit from Component base class."""
        component = SimpleComponent()
        assert isinstance(component, Component)
    
    def test_multiple_component_types(self):
        """Should be able to create multiple component types."""
        comp1 = SimpleComponent(1)
        comp2 = AnotherComponent("test")
        
        assert isinstance(comp1, Component)
        assert isinstance(comp2, Component)
        assert type(comp1) != type(comp2)


class TestComponentLifecycle:
    """Tests for component lifecycle methods."""
    
    def test_on_destroy_called(self, world):
        """on_destroy should be called when component is destroyed."""
        entity = world.create_entity("Entity")
        component = DestroyableComponent()
        entity.add_component(component)
        
        entity.remove_component(DestroyableComponent)
        assert component.destroyed is True
    
    def test_on_destroy_not_called_on_creation(self):
        """on_destroy should not be called on component creation."""
        component = DestroyableComponent()
        assert component.destroyed is False
    
    def test_component_with_no_on_destroy(self, world):
        """Component without on_destroy should not raise error."""
        entity = world.create_entity("Entity")
        component = SimpleComponent()
        entity.add_component(component)
        entity.remove_component(SimpleComponent)


class TestComponentAttributes:
    """Tests for component attributes and data storage."""
    
    def test_component_stores_data(self):
        """Component should store and retrieve data."""
        component = SimpleComponent(100)
        assert component.value == 100
        component.value = 200
        assert component.value == 200
    
    def test_component_custom_attributes(self):
        """Component should support custom attributes."""
        component = SimpleComponent()
        component.custom_attr = "custom_value"
        assert component.custom_attr == "custom_value"
    
    def test_component_multiple_instances_independent(self):
        """Multiple component instances should be independent."""
        comp1 = SimpleComponent(1)
        comp2 = SimpleComponent(2)
        
        comp1.value = 100
        assert comp2.value == 2
