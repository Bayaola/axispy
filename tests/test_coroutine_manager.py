import pytest
from core.coroutine_manager import CoroutineManager, Wait, WaitFrames, _RunningCoroutine

def mock_coroutine_wait():
    yield Wait(0.5)
    yield Wait(0.2)

def mock_coroutine_frames():
    yield WaitFrames(2)

def mock_coroutine_mixed():
    yield "unknown" # Should default to 1 frame wait
    yield Wait(0.1)

def mock_coroutine_error():
    yield WaitFrames(1)
    raise ValueError("Test error")

def test_wait_instruction():
    w = Wait(1.5)
    assert w.seconds == 1.5
    w2 = Wait(-5.0)
    assert w2.seconds == 0.0

def test_waitframes_instruction():
    wf = WaitFrames(5)
    assert wf.frames == 5
    wf2 = WaitFrames(0)
    assert wf2.frames == 1

def test_coroutine_manager_start():
    cm = CoroutineManager()
    cm.start(mock_coroutine_wait())
    
    assert cm.count == 1
    # The first advance happens on start
    assert cm._coroutines[0].wait_time == 0.5

def test_coroutine_manager_stop_all():
    cm = CoroutineManager()
    cm.start(mock_coroutine_wait())
    cm.start(mock_coroutine_frames())
    
    assert cm.count == 2
    cm.stop_all()
    assert cm.count == 0

def test_coroutine_manager_tick_wait_time():
    cm = CoroutineManager()
    cm.start(mock_coroutine_wait())
    
    # Needs wait_time to go from 0.5 to 0
    cm.tick(0.4)
    assert cm.count == 1
    import math
    assert math.isclose(cm._coroutines[0].wait_time, 0.1)
    
    # This tick will expire the wait, advance, and hit the next Wait(0.2)
    cm.tick(0.2)
    assert cm.count == 1
    assert cm._coroutines[0].wait_time == 0.2
    
    cm.tick(0.3)
    # Coroutine finished
    assert cm.count == 0

def test_coroutine_manager_tick_wait_frames():
    cm = CoroutineManager()
    cm.start(mock_coroutine_frames())
    
    assert cm._coroutines[0].wait_frames == 2
    cm.tick(0.1) # removes 1 frame
    assert cm._coroutines[0].wait_frames == 1
    assert cm.count == 1
    
    cm.tick(0.1) # expires the last frame, advances, finishes
    assert cm.count == 0

def test_coroutine_manager_tick_mixed_and_unknown():
    cm = CoroutineManager()
    cm.start(mock_coroutine_mixed())
    
    # First yield was "unknown", so it's a 1 frame wait
    assert cm._coroutines[0].wait_frames == 1
    cm.tick(0.0) # removes 1 frame, then hits Wait(0.1)
    
    assert cm._coroutines[0].wait_frames == 0
    assert cm._coroutines[0].wait_time == 0.1
    assert cm.count == 1
    
    cm.tick(0.2)
    assert cm.count == 0

def test_coroutine_manager_error_handling():
    cm = CoroutineManager()
    cm.start(mock_coroutine_error())
    
    # WaitFrames(1) is active
    assert cm.count == 1
    cm.tick(0.1)
    
    # Hits exception, should be caught and logged (or ignored in count)
    assert cm.count == 0
