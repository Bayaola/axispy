"""Named input action mapping.

Decouples gameplay logic from specific keys/buttons so rebinding is trivial.

Usage::

    from core.input_map import InputMap
    import pygame

    # Register actions (typically at startup or from config)
    InputMap.register("jump", [pygame.K_SPACE, pygame.K_w])
    InputMap.register("fire", [pygame.K_f])

    # Query in scripts
    if InputMap.is_pressed("jump"):
        ...
    if InputMap.is_just_pressed("jump"):
        ...

Actions can also be loaded from ``project.config`` via
``InputMap.load_from_config(config_dict)`` where the config contains::

    {
        "input_actions": {
            "jump": [32, 119],
            "fire": [102]
        }
    }
"""
from __future__ import annotations
import pygame


class InputMap:
    """Static action-to-key/button mapping registry."""

    _actions: dict[str, list[int]] = {}
    _prev_keys: dict[int, bool] = {}
    _curr_keys: dict[int, bool] = {}

    @classmethod
    def register(cls, action: str, keys: list[int]):
        """Register or overwrite an action with a list of key codes."""
        cls._actions[action] = list(keys)

    @classmethod
    def unregister(cls, action: str):
        """Remove an action."""
        cls._actions.pop(action, None)

    @classmethod
    def get_bindings(cls, action: str) -> list[int]:
        """Return the key codes bound to *action*, or an empty list."""
        return list(cls._actions.get(action, []))

    @classmethod
    def get_all_actions(cls) -> dict[str, list[int]]:
        """Return a copy of all registered actions."""
        return {k: list(v) for k, v in cls._actions.items()}

    @classmethod
    def clear(cls):
        """Remove all registered actions."""
        cls._actions.clear()
        cls._prev_keys.clear()
        cls._curr_keys.clear()

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @classmethod
    def load_from_config(cls, config: dict):
        """Load actions from a config dict containing an ``input_actions`` key.

        Expected format::

            {"input_actions": {"jump": [32, 119], "fire": [102]}}
        """
        actions = config.get("input_actions")
        if not isinstance(actions, dict):
            return
        for action_name, key_list in actions.items():
            if isinstance(key_list, list):
                cls._actions[str(action_name)] = [int(k) for k in key_list]

    # ------------------------------------------------------------------
    # Per-frame update (call once per frame BEFORE queries)
    # ------------------------------------------------------------------

    @classmethod
    def update(cls):
        """Snapshot current keyboard state for just-pressed / just-released detection.
        Should be called once per frame after ``Input.update()``."""
        cls._prev_keys = dict(cls._curr_keys)
        try:
            keys = pygame.key.get_pressed()
            # Store only the keys we care about
            all_keys: set[int] = set()
            for bindings in cls._actions.values():
                all_keys.update(bindings)
            cls._curr_keys = {k: bool(keys[k]) for k in all_keys if k < len(keys)}
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def is_pressed(cls, action: str) -> bool:
        """Return True if any key bound to *action* is currently held down."""
        bindings = cls._actions.get(action)
        if not bindings:
            return False
        for key in bindings:
            if cls._curr_keys.get(key, False):
                return True
        return False

    @classmethod
    def is_just_pressed(cls, action: str) -> bool:
        """Return True if any key bound to *action* was pressed this frame."""
        bindings = cls._actions.get(action)
        if not bindings:
            return False
        for key in bindings:
            if cls._curr_keys.get(key, False) and not cls._prev_keys.get(key, False):
                return True
        return False

    @classmethod
    def is_just_released(cls, action: str) -> bool:
        """Return True if any key bound to *action* was released this frame."""
        bindings = cls._actions.get(action)
        if not bindings:
            return False
        for key in bindings:
            if not cls._curr_keys.get(key, False) and cls._prev_keys.get(key, False):
                return True
        return False

    @classmethod
    def get_action_strength(cls, action: str) -> float:
        """Return 1.0 if any key in *action* is pressed, else 0.0."""
        return 1.0 if cls.is_pressed(action) else 0.0
