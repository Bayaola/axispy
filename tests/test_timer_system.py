import pytest
from core.ecs import World
from core.components.timer import TimerComponent
from core.systems.timer_system import TimerSystem


@pytest.fixture
def timer_world():
    world = World()
    world.add_system(TimerSystem())
    return world


class TestTimerComponent:
    """Tests for TimerComponent properties and API."""

    def test_default_values(self):
        t = TimerComponent()
        assert t.duration == 1.0
        assert t.one_shot is True
        assert t.is_running is False
        assert t.is_finished is False
        assert t.elapsed == 0.0
        assert t.time_left == 1.0

    def test_autostart(self):
        t = TimerComponent(autostart=True)
        assert t.is_running is True

    def test_start_resets_and_runs(self):
        t = TimerComponent(duration=2.0)
        t._elapsed = 0.5
        t._finished = True
        t.start()
        assert t.is_running is True
        assert t.elapsed == 0.0
        assert t.is_finished is False

    def test_stop(self):
        t = TimerComponent(autostart=True)
        t.stop()
        assert t.is_running is False

    def test_reset(self):
        t = TimerComponent(autostart=True)
        t._elapsed = 0.5
        t._finished = True
        t.reset()
        assert t.is_running is False
        assert t.elapsed == 0.0
        assert t.is_finished is False

    def test_time_left(self):
        t = TimerComponent(duration=3.0)
        t._elapsed = 1.0
        assert t.time_left == pytest.approx(2.0)

    def test_time_left_never_negative(self):
        t = TimerComponent(duration=1.0)
        t._elapsed = 5.0
        assert t.time_left == 0.0

    def test_negative_duration_clamped(self):
        t = TimerComponent(duration=-5.0)
        assert t.duration == 0.0


class TestTimerComponentTick:
    """Tests for TimerComponent.tick() behaviour."""

    def test_tick_advances_elapsed(self):
        t = TimerComponent(duration=2.0, autostart=True)
        t.tick(0.5)
        assert t.elapsed == pytest.approx(0.5)

    def test_tick_does_nothing_when_stopped(self):
        t = TimerComponent(duration=1.0)
        t.tick(0.5)
        assert t.elapsed == 0.0

    def test_one_shot_fires_callback_once(self):
        calls = []
        t = TimerComponent(duration=0.5, one_shot=True, autostart=True,
                           callback=lambda: calls.append(1))
        t.tick(0.6)
        assert len(calls) == 1
        assert t.is_running is False
        assert t.is_finished is True

    def test_repeating_timer_fires_multiple(self):
        calls = []
        t = TimerComponent(duration=0.5, one_shot=False, autostart=True,
                           callback=lambda: calls.append(1))
        t.tick(1.1)
        assert len(calls) == 2
        assert t.is_running is True

    def test_callback_none_does_not_crash(self):
        t = TimerComponent(duration=0.1, autostart=True, callback=None)
        t.tick(0.2)
        assert t.is_finished is True


class TestTimerSystem:
    """Tests for TimerSystem integration with World."""

    def test_system_ticks_timer_components(self, timer_world):
        calls = []
        entity = timer_world.create_entity("Timer")
        entity.add_component(TimerComponent(
            duration=0.5, autostart=True,
            callback=lambda: calls.append(1)
        ))
        timer_world.update(0.6)
        assert len(calls) == 1

    def test_system_skips_entities_without_timer(self, timer_world):
        entity = timer_world.create_entity("NoTimer")
        timer_world.update(0.1)  # Should not crash

    def test_system_handles_multiple_timers(self, timer_world):
        calls_a = []
        calls_b = []
        e1 = timer_world.create_entity("A")
        e1.add_component(TimerComponent(duration=0.1, autostart=True,
                                        callback=lambda: calls_a.append(1)))
        e2 = timer_world.create_entity("B")
        e2.add_component(TimerComponent(duration=0.2, autostart=True,
                                        callback=lambda: calls_b.append(1)))
        timer_world.update(0.25)
        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_system_does_not_tick_stopped_timer(self, timer_world):
        calls = []
        entity = timer_world.create_entity("Stopped")
        tc = TimerComponent(duration=0.1, callback=lambda: calls.append(1))
        entity.add_component(tc)
        timer_world.update(0.5)
        assert len(calls) == 0
