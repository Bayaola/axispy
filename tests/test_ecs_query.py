import pytest
from core.ecs import World, Entity, EntityQuery
from conftest import SimpleComponent, AnotherComponent


class TestWorldCreation:
    """Tests for world creation and basic properties."""
    
    def test_create_world(self):
        """Should be able to create a world."""
        world = World()
        assert world is not None
    
    def test_world_has_default_layer(self):
        """World should have 'Default' layer by default."""
        world = World()
        assert "Default" in world.layers


class TestWorldEntityManagement:
    """Tests for entity management in world."""
    
    def test_create_entity_in_world(self, world):
        """Should be able to create entity in world."""
        entity = world.create_entity("TestEntity")
        assert entity in world.entities
        assert entity.world is world
    
    def test_entity_count(self, world):
        """World should track entity count correctly."""
        assert len(world.entities) == 0
        world.create_entity("Entity1")
        assert len(world.entities) == 1
        world.create_entity("Entity2")
        assert len(world.entities) == 2
    
    def test_destroy_entity_removes_from_world(self, world):
        """Destroying entity should remove it from world."""
        entity = world.create_entity("ToDestroy")
        entity.destroy()
        assert entity not in world.entities
    
    def test_destroy_entity_removes_children(self, world):
        """Destroying parent should destroy children."""
        parent = world.create_entity("Parent")
        child = world.create_entity("Child")
        parent.add_child(child)
        
        parent.destroy()
        assert parent not in world.entities
        assert child not in world.entities
    
    def test_get_entity_by_id(self, world):
        """Should be able to retrieve entity by ID."""
        entity = world.create_entity("Entity")
        retrieved = world.get_entity_by_id(entity.id)
        assert retrieved is entity
    
    def test_get_nonexistent_entity_by_id(self, world):
        """Getting non-existent entity by ID should return None."""
        result = world.get_entity_by_id("nonexistent_id")
        assert result is None
    
    def test_get_entity_by_name(self, world):
        """Should be able to retrieve entity by name."""
        entity = world.create_entity("MyEntity")
        retrieved = world.get_entity_by_name("MyEntity")
        assert retrieved is entity
    
    def test_get_nonexistent_entity_by_name(self, world):
        """Getting non-existent entity by name should return None."""
        result = world.get_entity_by_name("NonExistent")
        assert result is None
    
    def test_get_entities_by_name(self, world):
        """Should be able to retrieve all entities with same name."""
        entity1 = world.create_entity("Duplicate")
        entity2 = world.create_entity("Duplicate")
        
        entities = world.get_entities_by_name("Duplicate")
        assert len(entities) == 2
        assert entity1 in entities
        assert entity2 in entities


class TestWorldComponentCache:
    """Tests for world component caching."""
    
    def test_get_entities_with_component(self, world):
        """Should retrieve entities with specific component."""
        entity1 = world.create_entity("Entity1")
        entity1.add_component(SimpleComponent(1))
        
        entity2 = world.create_entity("Entity2")
        entity2.add_component(SimpleComponent(2))
        
        entity3 = world.create_entity("Entity3")
        
        entities = world.get_entities_with(SimpleComponent)
        assert len(entities) == 2
        assert entity1 in entities
        assert entity2 in entities
        assert entity3 not in entities
    
    def test_get_entities_with_multiple_components(self, world):
        """Should retrieve entities with all specified components."""
        entity1 = world.create_entity("Entity1")
        entity1.add_component(SimpleComponent(1))
        entity1.add_component(AnotherComponent("a"))
        
        entity2 = world.create_entity("Entity2")
        entity2.add_component(SimpleComponent(2))
        
        entity3 = world.create_entity("Entity3")
        entity3.add_component(AnotherComponent("b"))
        
        entities = world.get_entities_with(SimpleComponent, AnotherComponent)
        assert len(entities) == 1
        assert entity1 in entities
    
    def test_get_entities_with_no_components(self, world):
        """Getting entities with no component types should return all."""
        entity1 = world.create_entity("Entity1")
        entity2 = world.create_entity("Entity2")
        
        entities = world.get_entities_with()
        assert len(entities) == 2
        assert entity1 in entities
        assert entity2 in entities
    
    def test_component_cache_updated_on_add(self, world):
        """Component cache should update when component is added."""
        entity = world.create_entity("Entity")
        assert len(world.get_entities_with(SimpleComponent)) == 0
        
        entity.add_component(SimpleComponent())
        assert len(world.get_entities_with(SimpleComponent)) == 1
    
    def test_component_cache_updated_on_remove(self, world):
        """Component cache should update when component is removed."""
        entity = world.create_entity("Entity")
        entity.add_component(SimpleComponent())
        assert len(world.get_entities_with(SimpleComponent)) == 1
        
        entity.remove_component(SimpleComponent)
        assert len(world.get_entities_with(SimpleComponent)) == 0


class TestWorldGroups:
    """Tests for entity groups in world."""
    
    def test_get_entities_in_group(self, world):
        """Should retrieve entities in a group."""
        entity1 = world.create_entity("Entity1")
        entity1.add_group("Enemies")
        
        entity2 = world.create_entity("Entity2")
        entity2.add_group("Enemies")
        
        entity3 = world.create_entity("Entity3")
        
        entities = world.get_entities_in_group("Enemies")
        assert len(entities) == 2
        assert entity1 in entities
        assert entity2 in entities
        assert entity3 not in entities
    
    def test_get_entities_in_nonexistent_group(self, world):
        """Getting non-existent group should return empty list."""
        entities = world.get_entities_in_group("NonExistent")
        assert len(entities) == 0
    
    def test_group_updated_on_add(self, world):
        """Group should update when entity is added to group."""
        entity = world.create_entity("Entity")
        assert len(world.get_entities_in_group("Enemies")) == 0
        
        entity.add_group("Enemies")
        assert len(world.get_entities_in_group("Enemies")) == 1
    
    def test_group_updated_on_remove(self, world):
        """Group should update when entity is removed from group."""
        entity = world.create_entity("Entity")
        entity.add_group("Enemies")
        assert len(world.get_entities_in_group("Enemies")) == 1
        
        entity.remove_group("Enemies")
        assert len(world.get_entities_in_group("Enemies")) == 0


class TestEntityQuery:
    """Tests for EntityQuery fluent interface."""
    
    def test_query_with_component(self, world):
        """Query should filter by component."""
        entity1 = world.create_entity("Entity1")
        entity1.add_component(SimpleComponent(1))
        
        entity2 = world.create_entity("Entity2")
        
        query = world.query().with_component(SimpleComponent)
        results = query.all()
        assert len(results) == 1
        assert entity1 in results
    
    def test_query_with_multiple_components(self, world):
        """Query should filter by multiple components."""
        entity1 = world.create_entity("Entity1")
        entity1.add_component(SimpleComponent(1))
        entity1.add_component(AnotherComponent("a"))
        
        entity2 = world.create_entity("Entity2")
        entity2.add_component(SimpleComponent(2))
        
        query = world.query().with_component(SimpleComponent, AnotherComponent)
        results = query.all()
        assert len(results) == 1
        assert entity1 in results
    
    def test_query_in_group(self, world):
        """Query should filter by group."""
        entity1 = world.create_entity("Entity1")
        entity1.add_group("Enemies")
        
        entity2 = world.create_entity("Entity2")
        
        query = world.query().in_group("Enemies")
        results = query.all()
        assert len(results) == 1
        assert entity1 in results
    
    def test_query_with_tag(self, world):
        """Query should filter by tag."""
        entity1 = world.create_entity("Entity1")
        entity1.add_tag("boss")
        
        entity2 = world.create_entity("Entity2")
        
        query = world.query().with_tag("boss")
        results = query.all()
        assert len(results) == 1
        assert entity1 in results
    
    def test_query_visible(self, world):
        """Query should filter by visibility."""
        entity1 = world.create_entity("Entity1")
        
        entity2 = world.create_entity("Entity2")
        entity2.hide()
        
        query = world.query().visible()
        results = query.all()
        assert len(results) == 1
        assert entity1 in results
    
    def test_query_physics_enabled(self, world):
        """Query should filter by physics processing."""
        entity1 = world.create_entity("Entity1")
        
        entity2 = world.create_entity("Entity2")
        entity2.process_physics(False)
        
        query = world.query().physics_enabled()
        results = query.all()
        assert len(results) == 1
        assert entity1 in results
    
    def test_query_chaining(self, world):
        """Query should support method chaining."""
        entity1 = world.create_entity("Entity1")
        entity1.add_component(SimpleComponent(1))
        entity1.add_group("Enemies")
        
        entity2 = world.create_entity("Entity2")
        entity2.add_component(SimpleComponent(2))
        
        entity3 = world.create_entity("Entity3")
        entity3.add_group("Enemies")
        
        query = world.query().with_component(SimpleComponent).in_group("Enemies")
        results = query.all()
        assert len(results) == 1
        assert entity1 in results
    
    def test_query_first(self, world):
        """Query.first() should return first matching entity."""
        entity1 = world.create_entity("Entity1")
        entity1.add_component(SimpleComponent(1))
        
        entity2 = world.create_entity("Entity2")
        entity2.add_component(SimpleComponent(2))
        
        query = world.query().with_component(SimpleComponent)
        result = query.first()
        assert result is not None
        assert result in [entity1, entity2]
    
    def test_query_first_no_match(self, world):
        """Query.first() should return None if no match."""
        query = world.query().with_component(SimpleComponent)
        result = query.first()
        assert result is None
    
    def test_query_count(self, world):
        """Query.count() should return number of matches."""
        entity1 = world.create_entity("Entity1")
        entity1.add_component(SimpleComponent(1))
        
        entity2 = world.create_entity("Entity2")
        entity2.add_component(SimpleComponent(2))
        
        entity3 = world.create_entity("Entity3")
        
        query = world.query().with_component(SimpleComponent)
        assert query.count() == 2
    
    def test_query_multiple_groups(self, world):
        """Query should filter by multiple groups (AND logic)."""
        entity1 = world.create_entity("Entity1")
        entity1.add_group("Enemies")
        entity1.add_group("Flying")
        
        entity2 = world.create_entity("Entity2")
        entity2.add_group("Enemies")
        
        query = world.query().in_group("Enemies").in_group("Flying")
        results = query.all()
        assert len(results) == 1
        assert entity1 in results
    
    def test_query_multiple_tags(self, world):
        """Query should filter by multiple tags (AND logic)."""
        entity1 = world.create_entity("Entity1")
        entity1.add_tag("boss")
        entity1.add_tag("flying")
        
        entity2 = world.create_entity("Entity2")
        entity2.add_tag("boss")
        
        query = world.query().with_tag("boss").with_tag("flying")
        results = query.all()
        assert len(results) == 1
        assert entity1 in results


class TestWorldUpdate:
    """Tests for world update mechanism."""
    
    def test_world_update(self, world):
        """World should be able to update."""
        world.update(0.016)
    
    def test_world_update_with_zero_dt(self, world):
        """World update with zero dt should be skipped."""
        world.update(0.0)
    
    def test_world_update_with_negative_dt(self, world):
        """World update with negative dt should be skipped."""
        world.update(-0.016)


class TestWorldProfiling:
    """Tests for world profiling."""
    
    def test_enable_profiling(self, world):
        """Should be able to enable profiling."""
        world.enable_profiling()
        assert world._profiling_enabled is True
    
    def test_disable_profiling(self, world):
        """Should be able to disable profiling."""
        world.enable_profiling()
        world.disable_profiling()
        assert world._profiling_enabled is False
    
    def test_get_system_timings(self, world):
        """Should be able to get system timings."""
        world.enable_profiling()
        timings = world.get_system_timings()
        assert isinstance(timings, dict)
