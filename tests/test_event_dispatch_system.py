import pytest
from core.ecs import World
from core.systems.event_dispatch_system import EventDispatchSystem


@pytest.fixture
def event_world():
    world = World()
    world.add_system(EventDispatchSystem())
    return world


class TestEventDispatchSystem:
    """Tests for EventDispatchSystem dispatching world and entity events."""

    def test_dispatches_world_events(self, event_world):
        received = []
        event_world.events.subscribe("test_event", lambda: received.append(1))
        event_world.events.emit("test_event")
        assert len(received) == 0  # Not yet dispatched
        event_world.update(0.016)
        assert len(received) == 1

    def test_dispatches_entity_events(self, event_world):
        received = []
        entity = event_world.create_entity("E")
        entity.events.subscribe("hit", lambda dmg: received.append(dmg))
        entity.events.emit("hit", 10)
        event_world.update(0.016)
        assert received == [10]

    def test_multiple_world_events_dispatched(self, event_world):
        received = []
        event_world.events.subscribe("a", lambda: received.append("a"))
        event_world.events.subscribe("b", lambda: received.append("b"))
        event_world.events.emit("a")
        event_world.events.emit("b")
        event_world.update(0.016)
        assert "a" in received
        assert "b" in received

    def test_no_crash_without_world(self):
        system = EventDispatchSystem()
        system.update(0.016, [])

    def test_entity_without_events_skipped(self, event_world):
        entity = event_world.create_entity("NoEvents")
        # Entity has no _events attribute set — should not crash
        event_world.update(0.016)

    def test_events_cleared_after_dispatch(self, event_world):
        received = []
        event_world.events.subscribe("once", lambda: received.append(1))
        event_world.events.emit("once")
        event_world.update(0.016)
        event_world.update(0.016)
        assert len(received) == 1  # Not dispatched again

    def test_system_required_components_empty(self):
        system = EventDispatchSystem()
        assert system.required_components == ()
