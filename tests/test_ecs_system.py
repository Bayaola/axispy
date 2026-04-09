import pytest
from core.ecs import System, Entity
from conftest import SimpleSystem, ComponentRequiringSystem, SimpleComponent


class TestSystemCreation:
    """Tests for system creation and basic properties."""
    
    def test_create_system(self):
        """Should be able to create a system."""
        system = SimpleSystem()
        assert system is not None
    
    def test_system_has_default_properties(self):
        """System should have default properties."""
        system = SimpleSystem()
        assert system.world is None
        assert system.update_phase == "simulation"
        assert system.priority == 0


class TestSystemUpdate:
    """Tests for system update mechanism."""
    
    def test_system_update_called(self, world):
        """System update should be called during world update."""
        system = SimpleSystem()
        world.add_system(system)
        
        world.update(0.016)
        assert system.update_count == 1
    
    def test_system_update_receives_dt(self, world):
        """System update should receive delta time."""
        system = SimpleSystem()
        world.add_system(system)
        
        dt = 0.016
        world.update(dt)
        assert system.last_dt == dt
    
    def test_system_update_receives_entities(self, world):
        """System update should receive entities list."""
        system = SimpleSystem()
        world.add_system(system)
        entity = world.create_entity("Entity")
        
        world.update(0.016)
        assert system.update_count == 1
    
    def test_system_update_multiple_frames(self, world):
        """System update should be called each frame."""
        system = SimpleSystem()
        world.add_system(system)
        
        world.update(0.016)
        world.update(0.016)
        world.update(0.016)
        
        assert system.update_count == 3


class TestSystemWorldIntegration:
    """Tests for system integration with world."""
    
    def test_add_system_to_world(self, world):
        """Should be able to add system to world."""
        system = SimpleSystem()
        world.add_system(system)
        
        assert system in world.systems
        assert system.world is world
    
    def test_add_duplicate_system(self, world):
        """Adding same system twice should not duplicate it."""
        system = SimpleSystem()
        world.add_system(system)
        world.add_system(system)
        
        assert world.systems.count(system) == 1
    
    def test_remove_system_from_world(self, world):
        """Should be able to remove system from world."""
        system = SimpleSystem()
        world.add_system(system)
        result = world.remove_system(system)
        
        assert result is True
        assert system not in world.systems
        assert system.world is None
    
    def test_remove_nonexistent_system(self, world):
        """Removing non-existent system should return False."""
        system = SimpleSystem()
        result = world.remove_system(system)
        assert result is False
    
    def test_get_system_by_type(self, world):
        """Should be able to retrieve system by type."""
        system = SimpleSystem()
        world.add_system(system)
        
        retrieved = world.get_system(SimpleSystem)
        assert retrieved is system
    
    def test_get_nonexistent_system_type(self, world):
        """Getting non-existent system type should return None."""
        result = world.get_system(SimpleSystem)
        assert result is None


class TestSystemRequiredComponents:
    """Tests for system required components."""
    
    def test_system_with_required_components(self):
        """System should support required_components declaration."""
        system = ComponentRequiringSystem()
        assert SimpleComponent in system.required_components
    
    def test_system_skipped_without_required_components(self, world):
        """System should be skipped if required components don't exist."""
        system = ComponentRequiringSystem()
        world.add_system(system)
        
        world.update(0.016)
        assert system.update_count == 0
    
    def test_system_runs_with_required_components(self, world):
        """System should run when required components exist."""
        system = ComponentRequiringSystem()
        world.add_system(system)
        
        entity = world.create_entity("Entity")
        entity.add_component(SimpleComponent(42))
        
        world.update(0.016)
        assert system.update_count == 1
    
    def test_system_runs_with_multiple_entities_having_required_components(self, world):
        """System should run when any entity has required components."""
        system = ComponentRequiringSystem()
        world.add_system(system)
        
        entity1 = world.create_entity("Entity1")
        entity1.add_component(SimpleComponent(1))
        
        entity2 = world.create_entity("Entity2")
        entity2.add_component(SimpleComponent(2))
        
        world.update(0.016)
        assert system.update_count == 1


class TestSystemPhases:
    """Tests for system update phases."""
    
    def test_system_default_phase_is_simulation(self):
        """System should have 'simulation' as default phase."""
        system = SimpleSystem()
        assert system.update_phase == "simulation"
    
    def test_system_can_set_render_phase(self):
        """System should be able to set 'render' phase."""
        system = SimpleSystem()
        system.update_phase = "render"
        assert system.update_phase == "render"
    
    def test_systems_ordered_by_phase(self, world):
        """Systems should be ordered by phase (simulation before render)."""
        sim_system = SimpleSystem()
        sim_system.update_phase = "simulation"
        
        render_system = SimpleSystem()
        render_system.update_phase = "render"
        
        world.add_system(render_system)
        world.add_system(sim_system)
        
        sim_idx = world.systems.index(sim_system)
        render_idx = world.systems.index(render_system)
        assert sim_idx < render_idx


class TestSystemPriority:
    """Tests for system priority ordering."""
    
    def test_system_default_priority_is_zero(self):
        """System should have priority 0 by default."""
        system = SimpleSystem()
        assert system.priority == 0
    
    def test_systems_ordered_by_priority(self, world):
        """Systems should be ordered by priority (lower first)."""
        high_priority = SimpleSystem()
        high_priority.priority = 10
        
        low_priority = SimpleSystem()
        low_priority.priority = 1
        
        world.add_system(high_priority)
        world.add_system(low_priority)
        
        low_idx = world.systems.index(low_priority)
        high_idx = world.systems.index(high_priority)
        assert low_idx < high_idx


class TestSystemLifecycle:
    """Tests for system lifecycle callbacks."""
    
    def test_on_added_to_world_called(self, world):
        """on_added_to_world should be called when system is added."""
        class LifecycleSystem(System):
            def __init__(self):
                super().__init__()
                self.added_called = False
            
            def on_added_to_world(self):
                self.added_called = True
        
        system = LifecycleSystem()
        world.add_system(system)
        assert system.added_called is True
    
    def test_on_removed_from_world_called(self, world):
        """on_removed_from_world should be called when system is removed."""
        class LifecycleSystem(System):
            def __init__(self):
                super().__init__()
                self.removed_called = False
            
            def on_removed_from_world(self):
                self.removed_called = True
        
        system = LifecycleSystem()
        world.add_system(system)
        world.remove_system(system)
        assert system.removed_called is True
