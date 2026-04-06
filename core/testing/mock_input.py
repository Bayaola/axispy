"""MockInputProvider for unit-testing scripts without pygame.

Usage::

    from core.input import Input
    from core.testing import MockInputProvider

    mock = MockInputProvider()
    Input.set_provider(mock)

    mock.press_key(pygame.K_SPACE)
    assert Input.get_key(pygame.K_SPACE) is True

    mock.release_key(pygame.K_SPACE)
    assert Input.get_key(pygame.K_SPACE) is False

    mock.set_mouse_pos(100, 200)
    assert Input.get_mouse_position() == (100, 200)

    # Restore default input when done
    Input.clear_provider()
"""


class MockInputProvider:
    """Drop-in provider for ``Input.set_provider()`` that fakes keyboard,
    mouse, and axis state without requiring a pygame display."""

    def __init__(self):
        self._keys: dict[int, bool] = {}
        self._mouse_buttons: dict[int, bool] = {}
        self._mouse_pos: tuple[float, float] = (0.0, 0.0)
        self._game_mouse_pos: tuple[float, float] = (0.0, 0.0)
        self._axes: dict[str, float] = {}
        self._events: list = []

    # ------------------------------------------------------------------
    # Simulation helpers (call these in your tests)
    # ------------------------------------------------------------------

    def press_key(self, key_code: int):
        """Simulate pressing a key."""
        self._keys[key_code] = True

    def release_key(self, key_code: int):
        """Simulate releasing a key."""
        self._keys[key_code] = False

    def set_mouse_pos(self, x: float, y: float):
        """Set the current mouse position."""
        self._mouse_pos = (x, y)
        self._game_mouse_pos = (x, y)

    def set_game_mouse_pos(self, x: float, y: float):
        """Set the game-space mouse position independently."""
        self._game_mouse_pos = (x, y)

    def press_mouse_button(self, button: int):
        """Simulate pressing a mouse button (0=left, 1=middle, 2=right)."""
        self._mouse_buttons[button] = True

    def release_mouse_button(self, button: int):
        """Simulate releasing a mouse button."""
        self._mouse_buttons[button] = False

    def set_axis(self, name: str, value: float):
        """Set a named axis value (-1.0 to 1.0)."""
        self._axes[name] = max(-1.0, min(1.0, value))

    def inject_event(self, event):
        """Add a synthetic event to the events list for this frame."""
        self._events.append(event)

    def reset(self):
        """Clear all simulated state."""
        self._keys.clear()
        self._mouse_buttons.clear()
        self._mouse_pos = (0.0, 0.0)
        self._game_mouse_pos = (0.0, 0.0)
        self._axes.clear()
        self._events.clear()

    # ------------------------------------------------------------------
    # Provider interface (called by Input class)
    # ------------------------------------------------------------------

    def update(self):
        """No-op — state is set explicitly by the test."""
        pass

    def get_key(self, key_code: int) -> bool:
        return self._keys.get(key_code, False)

    def get_mouse_button(self, button_index: int) -> bool:
        return self._mouse_buttons.get(button_index, False)

    def get_mouse_position(self) -> tuple[float, float]:
        return self._mouse_pos

    def get_game_mouse_position(self) -> tuple[float, float]:
        return self._game_mouse_pos

    def get_axis(self, axis_name: str) -> float:
        return self._axes.get(axis_name, 0.0)

    def get_events(self) -> list:
        return self._events
