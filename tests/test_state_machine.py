from core.state_machine import StateMachine, State

class MockState(State):
    def __init__(self):
        super().__init__()
        self.entered = False
        self.exited = False
        self.update_count = 0

    def on_enter(self):
        self.entered = True

    def on_update(self, dt: float):
        self.update_count += 1

    def on_exit(self):
        self.exited = True

def test_state_machine_initialization():
    fsm = StateMachine()
    assert fsm.current_state == ""
    assert fsm.previous_state == ""

def test_state_machine_add_and_start():
    fsm = StateMachine()
    state = MockState()
    fsm.add_state("idle", state)
    
    assert fsm.has_state("idle")
    fsm.start("idle")
    
    assert fsm.current_state == "idle"
    assert state.entered == True
    assert state.exited == False

def test_state_machine_transition():
    fsm = StateMachine()
    state_a = MockState()
    state_b = MockState()
    
    fsm.add_state("A", state_a)
    fsm.add_state("B", state_b)
    
    fsm.start("A")
    fsm.transition_to("B")
    
    assert fsm.current_state == "B"
    assert fsm.previous_state == "A"
    assert state_a.exited == True
    assert state_b.entered == True

def test_state_machine_update():
    fsm = StateMachine()
    state = MockState()
    fsm.add_state("A", state)
    fsm.start("A")
    
    fsm.update(0.16)
    fsm.update(0.16)
    
    assert state.update_count == 2

def test_state_machine_invalid_transition():
    fsm = StateMachine()
    state = MockState()
    fsm.add_state("A", state)
    fsm.start("A")
    
    # Transition to non-existent state should do nothing or just log a warning
    fsm.transition_to("B")
    
    assert fsm.current_state == "A"
    assert state.exited == False

def test_state_machine_remove_current_state():
    fsm = StateMachine()
    state = MockState()
    fsm.add_state("A", state)
    fsm.start("A")
    
    fsm.remove_state("A")
    
    # State should be exited and FSM reset
    assert state.exited == True
    assert not fsm.has_state("A")
    assert fsm.current_state == ""
