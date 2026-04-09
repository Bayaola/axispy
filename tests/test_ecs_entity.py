import pytest
from core.ecs import Entity, Component
from conftest import SimpleComponent, AnotherComponent, DestroyableComponent


class TestEntityCreation:
    """Tests for entity creation and basic properties."""
    
    def test_entity_has_unique_id(self):
        """Each entity should have a unique ID."""
        entity1 = Entity("Entity1")
        entity2 = Entity("Entity2")
        assert entity1.id != entity2.id
    
    def test_entity_name(self):
        """Entity should store its name."""
        entity = Entity("MyEntity")
        assert entity.name == "MyEntity"
    
    def test_entity_default_name(self):
        """Entity should have default name if not provided."""
        entity = Entity()
        assert entity.name == "GameObject"
    
    def test_entity_repr(self):
        """Entity should have a readable string representation."""
        entity = Entity("TestEntity")
        repr_str = repr(entity)
        assert "TestEntity" in repr_str
        assert "Entity" in repr_str


class TestEntityComponents:
    """Tests for component management on entities."""
    
    def test_add_component(self, entity):
        """Should be able to add a component to an entity."""
        component = SimpleComponent(42)
        entity.add_component(component)
        assert entity.get_component(SimpleComponent) is component
    
    def test_get_component(self, entity):
        """Should retrieve added component by type."""
        component = SimpleComponent(100)
        entity.add_component(component)
        retrieved = entity.get_component(SimpleComponent)
        assert retrieved is component
        assert retrieved.value == 100
    
    def test_get_nonexistent_component(self, entity):
        """Should return None for non-existent component."""
        result = entity.get_component(SimpleComponent)
        assert result is None
    
    def test_remove_component(self, entity):
        """Should be able to remove a component."""
        component = SimpleComponent()
        entity.add_component(component)
        entity.remove_component(SimpleComponent)
        assert entity.get_component(SimpleComponent) is None
    
    def test_remove_nonexistent_component(self, entity):
        """Removing non-existent component should not raise."""
        entity.remove_component(SimpleComponent)
    
    def test_multiple_components(self, entity):
        """Entity should support multiple different component types."""
        comp1 = SimpleComponent(1)
        comp2 = AnotherComponent("test")
        entity.add_component(comp1)
        entity.add_component(comp2)
        
        assert entity.get_component(SimpleComponent) is comp1
        assert entity.get_component(AnotherComponent) is comp2
    
    def test_get_components_by_base_type(self, entity):
        """Should retrieve all components of a type including subclasses."""
        class BaseComp(Component):
            pass
        
        class DerivedComp(BaseComp):
            pass
        
        base = BaseComp()
        derived = DerivedComp()
        entity.add_component(base)
        entity.add_component(derived)
        
        components = entity.get_components(BaseComp)
        assert len(components) == 2
        assert base in components
        assert derived in components


class TestEntityHierarchy:
    """Tests for parent-child entity relationships."""
    
    def test_add_child(self, world):
        """Should be able to add a child entity."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        
        assert child in parent.children
        assert child.parent is parent
    
    def test_remove_child(self, world):
        """Should be able to remove a child entity."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        parent.remove_child(child)
        
        assert child not in parent.children
        assert child.parent is None
    
    def test_get_child_by_name(self, world):
        """Should retrieve child by name."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        
        retrieved = parent.get_child("Child")
        assert retrieved is child
    
    def test_get_nonexistent_child(self, world):
        """Should return None for non-existent child."""
        parent = world.create_entity("Parent")
        result = parent.get_child("NonExistent")
        assert result is None
    
    def test_get_children(self, world):
        """Should return list of children."""
        parent = world.create_entity("Parent")
        child1 = world.create_entity("Child1")
        child2 = world.create_entity("Child2")
        parent.add_child(child1)
        parent.add_child(child2)
        
        children = parent.get_children()
        assert len(children) == 2
        assert child1 in children
        assert child2 in children
    
    def test_get_children_copy(self, world):
        """Should return a copy of children list."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        
        children_copy = parent.get_children_copy()
        children_copy.append(world.create_entity("Fake"))
        
        assert len(parent.children) == 1


class TestEntityGroups:
    """Tests for entity group management."""
    
    def test_add_group(self, world):
        """Should be able to add entity to a group."""
        entity = world.create_entity("Entity")
        entity.add_group("Enemies")
        assert entity.has_group("Enemies")
    
    def test_remove_group(self, world):
        """Should be able to remove entity from a group."""
        entity = world.create_entity("Entity")
        entity.add_group("Enemies")
        entity.remove_group("Enemies")
        assert not entity.has_group("Enemies")
    
    def test_has_group(self, world):
        """Should check if entity is in a group."""
        entity = world.create_entity("Entity")
        assert not entity.has_group("Enemies")
        entity.add_group("Enemies")
        assert entity.has_group("Enemies")
    
    def test_multiple_groups(self, world):
        """Entity should support multiple groups."""
        entity = world.create_entity("Entity")
        entity.add_group("Enemies")
        entity.add_group("Visible")
        
        assert entity.has_group("Enemies")
        assert entity.has_group("Visible")


class TestEntityTags:
    """Tests for entity tag management."""
    
    def test_add_tag(self, entity):
        """Should be able to add a tag to an entity."""
        entity.add_tag("boss")
        assert entity.has_tag("boss")
    
    def test_remove_tag(self, entity):
        """Should be able to remove a tag from an entity."""
        entity.add_tag("boss")
        entity.remove_tag("boss")
        assert not entity.has_tag("boss")
    
    def test_has_tag(self, entity):
        """Should check if entity has a tag."""
        assert not entity.has_tag("boss")
        entity.add_tag("boss")
        assert entity.has_tag("boss")
    
    def test_multiple_tags(self, entity):
        """Entity should support multiple tags."""
        entity.add_tag("boss")
        entity.add_tag("flying")
        
        assert entity.has_tag("boss")
        assert entity.has_tag("flying")


class TestEntityVisibility:
    """Tests for entity visibility control."""
    
    def test_entity_visible_by_default(self, entity):
        """Entity should be visible by default."""
        assert entity.is_visible()
    
    def test_hide_entity(self, entity):
        """Should be able to hide an entity."""
        entity.hide()
        assert not entity.is_visible()
    
    def test_show_entity(self, entity):
        """Should be able to show a hidden entity."""
        entity.hide()
        entity.show()
        assert entity.is_visible()
    
    def test_hide_propagates_to_children(self, world):
        """Hiding parent should hide children."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        
        parent.hide()
        assert not parent.is_visible()
        assert not child.is_visible()
    
    def test_show_propagates_to_children(self, world):
        """Showing parent should show children."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        parent.hide()
        
        parent.show()
        assert parent.is_visible()
        assert child.is_visible()


class TestEntityPhysicsProcessing:
    """Tests for entity physics processing control."""
    
    def test_physics_processing_enabled_by_default(self, entity):
        """Physics processing should be enabled by default."""
        assert entity.is_physics_processing()
    
    def test_disable_physics_processing(self, entity):
        """Should be able to disable physics processing."""
        entity.process_physics(False)
        assert not entity.is_physics_processing()
    
    def test_enable_physics_processing(self, entity):
        """Should be able to enable physics processing."""
        entity.process_physics(False)
        entity.process_physics(True)
        assert entity.is_physics_processing()
    
    def test_physics_processing_propagates_to_children(self, world):
        """Physics processing change should propagate to children."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        
        parent.process_physics(False)
        assert not parent.is_physics_processing()
        assert not child.is_physics_processing()


class TestEntityLayer:
    """Tests for entity layer management."""
    
    def test_entity_default_layer(self, entity):
        """Entity should have 'Default' layer by default."""
        assert entity.layer == "Default"
    
    def test_set_layer(self, entity):
        """Should be able to set entity layer."""
        entity.set_layer("UI")
        assert entity.layer == "UI"
    
    def test_set_layer_propagates_to_children(self, world):
        """Setting layer should propagate to children."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        
        parent.set_layer("UI")
        assert parent.layer == "UI"
        assert child.layer == "UI"


class TestEntityDestroy:
    """Tests for entity destruction."""
    
    def test_destroy_entity_without_world(self):
        """Destroying entity without world should return False."""
        entity = Entity("Orphan")
        result = entity.destroy()
        assert result is False
    
    def test_destroy_entity_with_world(self, world):
        """Destroying entity with world should return True."""
        entity = world.create_entity("ToDestroy")
        result = entity.destroy()
        assert result is True
        assert entity not in world.entities
