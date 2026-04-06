"""Finite State Machine for entity behavior management.

Usage from a user script::

    from core.state_machine import StateMachine, State

    class IdleState(State):
        def on_enter(self):
            print("Entering idle")
        def on_update(self, dt):
            if some_condition:
                self.machine.transition_to("walk")
        def on_exit(self):
            print("Leaving idle")

    class WalkState(State):
        def on_enter(self):
            print("Starting to walk")
        def on_update(self, dt):
            if another_condition:
                self.machine.transition_to("idle")
        def on_exit(self):
            print("Stopped walking")

    class MyScript:
        def on_start(self):
            self.state_machine = StateMachine(self.entity)
            self.state_machine.add_state("idle", IdleState())
            self.state_machine.add_state("walk", WalkState())
            self.state_machine.start("idle")

        def on_update(self, dt):
            self.state_machine.update(dt)
"""
from __future__ import annotations
from core.logger import get_logger

_fsm_logger = get_logger("state_machine")


class State:
    """Base class for FSM states.  Override the lifecycle methods as needed."""

    def __init__(self):
        self.machine: StateMachine | None = None
        self.entity = None

    def on_enter(self):
        """Called when this state becomes active."""
        pass

    def on_update(self, dt: float):
        """Called every frame while this state is active."""
        pass

    def on_exit(self):
        """Called when leaving this state."""
        pass


class StateMachine:
    """Simple finite state machine bound to an entity.

    States are registered by name and transitions are triggered explicitly
    via ``transition_to(name)``.
    """

    def __init__(self, entity=None):
        self.entity = entity
        self._states: dict[str, State] = {}
        self._current_state: State | None = None
        self._current_name: str = ""
        self._previous_name: str = ""

    @property
    def current_state(self) -> str:
        """Name of the currently active state, or empty string."""
        return self._current_name

    @property
    def previous_state(self) -> str:
        """Name of the previously active state."""
        return self._previous_name

    def add_state(self, name: str, state: State) -> None:
        """Register a state under *name*."""
        state.machine = self
        state.entity = self.entity
        self._states[name] = state

    def remove_state(self, name: str) -> None:
        """Remove a registered state.  If it is the current state, exit it first."""
        if name == self._current_name and self._current_state is not None:
            try:
                self._current_state.on_exit()
            except Exception as e:
                _fsm_logger.error("Error in State.on_exit during remove", state=name, error=str(e))
            self._current_state = None
            self._current_name = ""
        self._states.pop(name, None)

    def has_state(self, name: str) -> bool:
        return name in self._states

    def start(self, name: str) -> None:
        """Set the initial state without calling on_exit on any previous state."""
        state = self._states.get(name)
        if state is None:
            _fsm_logger.warning("State not found", state=name)
            return
        self._current_state = state
        self._current_name = name
        try:
            state.on_enter()
        except Exception as e:
            _fsm_logger.error("Error in State.on_enter", state=name, error=str(e))

    def transition_to(self, name: str) -> None:
        """Transition from the current state to *name*."""
        if name == self._current_name:
            return
        new_state = self._states.get(name)
        if new_state is None:
            _fsm_logger.warning("State not found for transition", target=name)
            return
        # Exit current
        if self._current_state is not None:
            try:
                self._current_state.on_exit()
            except Exception as e:
                _fsm_logger.error("Error in State.on_exit", state=self._current_name, error=str(e))
        self._previous_name = self._current_name
        self._current_state = new_state
        self._current_name = name
        # Enter new
        try:
            new_state.on_enter()
        except Exception as e:
            _fsm_logger.error("Error in State.on_enter", state=name, error=str(e))

    def update(self, dt: float) -> None:
        """Tick the current state.  Call once per frame."""
        if self._current_state is not None:
            try:
                self._current_state.on_update(dt)
            except Exception as e:
                _fsm_logger.error("Error in State.on_update", state=self._current_name, error=str(e))
