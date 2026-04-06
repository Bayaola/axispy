import pygame
import math
import time


# ---------------------------------------------------------------------------
# Touch data classes
# ---------------------------------------------------------------------------

class TouchPoint:
    """Represents a single touch point."""
    __slots__ = ("finger_id", "x", "y", "dx", "dy", "pressure")

    def __init__(self, finger_id: int, x: float, y: float,
                 dx: float = 0.0, dy: float = 0.0, pressure: float = 1.0):
        self.finger_id = finger_id
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.pressure = pressure


class TouchGesture:
    """Holds recognized gesture data for the current frame."""
    __slots__ = ("tap", "double_tap", "long_press", "swipe",
                 "swipe_direction", "swipe_velocity",
                 "pinch", "pinch_scale", "pinch_center",
                 "rotate", "rotate_angle", "rotate_center")

    def __init__(self):
        self.tap = False
        self.double_tap = False
        self.long_press = False
        self.swipe = False
        self.swipe_direction = (0.0, 0.0)   # normalized (dx, dy)
        self.swipe_velocity = 0.0            # pixels / second
        self.pinch = False
        self.pinch_scale = 1.0               # >1 = spread, <1 = pinch
        self.pinch_center = (0.0, 0.0)
        self.rotate = False
        self.rotate_angle = 0.0              # delta radians this frame
        self.rotate_center = (0.0, 0.0)


# ---------------------------------------------------------------------------
# Input manager
# ---------------------------------------------------------------------------

class Input:
    # --- Provider override for testing ---
    _provider = None   # When set, delegates update/get_key/get_mouse_button etc.

    # --- Keyboard & Mouse (existing) ---
    _keys = {}
    _mouse_buttons = {}
    _mouse_pos = (0, 0)
    _game_mouse_pos = (0, 0)
    _mouse_mapper = None
    _events = []

    # --- Joystick / Gamepad ---
    _joysticks: dict[int, pygame.joystick.JoystickType] = {}   # instance_id -> Joystick
    _joy_buttons: dict[int, dict[int, bool]] = {}               # instance_id -> {btn: pressed}
    _joy_buttons_prev: dict[int, dict[int, bool]] = {}
    _joy_axes: dict[int, dict[int, float]] = {}                 # instance_id -> {axis: value}
    _joy_hats: dict[int, dict[int, tuple]] = {}                 # instance_id -> {hat: (x,y)}
    _joy_deadzone: float = 0.15

    # --- Touch ---
    _touches: dict[int, TouchPoint] = {}         # finger_id -> TouchPoint (active)
    _touches_started: list[TouchPoint] = []      # began this frame
    _touches_moved: list[TouchPoint] = []        # moved this frame
    _touches_ended: list[TouchPoint] = []        # ended this frame

    # --- Gesture recognition state (internal) ---
    _gesture = TouchGesture()
    _gesture_tap_start: dict[int, tuple] = {}    # finger_id -> (x, y, time)
    _gesture_last_tap_time: float = 0.0
    _gesture_last_tap_pos: tuple = (0.0, 0.0)
    _gesture_prev_pinch_dist: float = 0.0
    _gesture_prev_pinch_angle: float = 0.0
    _gesture_long_press_threshold: float = 0.5   # seconds
    _gesture_tap_radius: float = 20.0            # max movement for a tap (px)
    _gesture_double_tap_time: float = 0.35       # seconds between taps
    _gesture_swipe_min_dist: float = 40.0        # min px for a swipe

    # -----------------------------------------------------------------------
    # Provider injection for testing
    # -----------------------------------------------------------------------
    @classmethod
    def set_provider(cls, provider):
        """Inject a provider object that overrides Input behaviour.

        The provider may implement any subset of:
            update(), get_key(key_code), get_mouse_button(index),
            get_mouse_position(), get_game_mouse_position(),
            get_events(), get_axis(name).
        Missing methods fall through to the default pygame implementation.
        Pass ``None`` to restore the default behaviour.
        """
        cls._provider = provider

    @classmethod
    def clear_provider(cls):
        """Remove any injected provider, restoring default pygame input."""
        cls._provider = None

    # -----------------------------------------------------------------------
    # Core update
    # -----------------------------------------------------------------------
    @classmethod
    def update(cls):
        if cls._provider and hasattr(cls._provider, "update"):
            cls._provider.update()
            return
        # Keyboard & mouse
        cls._keys = pygame.key.get_pressed()
        cls._mouse_buttons = pygame.mouse.get_pressed()
        cls._mouse_pos = pygame.mouse.get_pos()
        cls._events = pygame.event.get()

        # Map window coords to game/design coords
        if cls._mouse_mapper:
            mapped = cls._mouse_mapper(cls._mouse_pos[0], cls._mouse_pos[1])
            cls._game_mouse_pos = mapped if mapped is not None else (-99999, -99999)
        else:
            cls._game_mouse_pos = cls._mouse_pos

        # Reset per-frame touch lists
        cls._touches_started.clear()
        cls._touches_moved.clear()
        cls._touches_ended.clear()

        # Reset gesture
        cls._gesture = TouchGesture()

        # Store previous button states for just-pressed / just-released
        cls._joy_buttons_prev = {
            jid: dict(btns) for jid, btns in cls._joy_buttons.items()
        }

        # Process events
        for event in cls._events:
            cls._process_joystick_event(event)
            cls._process_touch_event(event)

        # Update joystick continuous state
        cls._update_joystick_state()

        # Recognize gestures from touch data
        cls._recognize_gestures()

    # -----------------------------------------------------------------------
    # Mouse mapper
    # -----------------------------------------------------------------------
    @classmethod
    def set_mouse_mapper(cls, mapper_fn):
        """Set a function (window_x, window_y) -> (game_x, game_y) or None."""
        cls._mouse_mapper = mapper_fn

    # -----------------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------------
    @classmethod
    def get_events(cls):
        if cls._provider and hasattr(cls._provider, "get_events"):
            return cls._provider.get_events()
        return cls._events

    # -----------------------------------------------------------------------
    # Keyboard
    # -----------------------------------------------------------------------
    @classmethod
    def get_key(cls, key_code):
        if cls._provider and hasattr(cls._provider, "get_key"):
            return cls._provider.get_key(key_code)
        return cls._keys[key_code] if cls._keys else False

    # -----------------------------------------------------------------------
    # Mouse
    # -----------------------------------------------------------------------
    @classmethod
    def get_mouse_button(cls, button_index):
        if cls._provider and hasattr(cls._provider, "get_mouse_button"):
            return cls._provider.get_mouse_button(button_index)
        # 0: left, 1: middle, 2: right
        return cls._mouse_buttons[button_index] if cls._mouse_buttons else False

    @classmethod
    def get_mouse_position(cls):
        if cls._provider and hasattr(cls._provider, "get_mouse_position"):
            return cls._provider.get_mouse_position()
        return cls._mouse_pos

    @classmethod
    def get_game_mouse_position(cls):
        """Return mouse position mapped to game/design coordinates."""
        if cls._provider and hasattr(cls._provider, "get_game_mouse_position"):
            return cls._provider.get_game_mouse_position()
        return cls._game_mouse_pos

    # -----------------------------------------------------------------------
    # Axes (keyboard + joystick merged)
    # -----------------------------------------------------------------------
    @classmethod
    def get_axis(cls, axis_name: str) -> float:
        if cls._provider and hasattr(cls._provider, "get_axis"):
            return cls._provider.get_axis(axis_name)
        val = 0.0
        if axis_name == "Horizontal":
            if cls.get_key(pygame.K_RIGHT) or cls.get_key(pygame.K_d):
                val += 1.0
            if cls.get_key(pygame.K_LEFT) or cls.get_key(pygame.K_a):
                val -= 1.0
            # Merge first joystick left stick X (axis 0)
            joy_val = cls.get_joy_axis(axis=0)
            if abs(joy_val) > abs(val):
                val = joy_val
        elif axis_name == "Vertical":
            if cls.get_key(pygame.K_UP) or cls.get_key(pygame.K_w):
                val += 1.0
            if cls.get_key(pygame.K_DOWN) or cls.get_key(pygame.K_s):
                val -= 1.0
            # Merge first joystick left stick Y (axis 1), invert so up = +1
            joy_val = -cls.get_joy_axis(axis=1)
            if abs(joy_val) > abs(val):
                val = joy_val
        return max(-1.0, min(1.0, val))

    # -----------------------------------------------------------------------
    # Joystick / Gamepad
    # -----------------------------------------------------------------------
    @classmethod
    def set_joystick_deadzone(cls, deadzone: float):
        """Set the deadzone threshold for joystick axes (default 0.15)."""
        cls._joy_deadzone = max(0.0, min(1.0, deadzone))

    @classmethod
    def get_joystick_count(cls) -> int:
        """Return number of connected joysticks."""
        return len(cls._joysticks)

    @classmethod
    def get_joystick_ids(cls) -> list[int]:
        """Return list of connected joystick instance IDs."""
        return list(cls._joysticks.keys())

    @classmethod
    def get_joystick_name(cls, instance_id: int = -1) -> str:
        """Return joystick name. If instance_id=-1, use first connected."""
        joy = cls._get_joystick(instance_id)
        return joy.get_name() if joy else ""

    @classmethod
    def get_joy_button(cls, button: int, instance_id: int = -1) -> bool:
        """Return True if button is currently pressed."""
        jid = cls._resolve_joy_id(instance_id)
        if jid is None:
            return False
        return cls._joy_buttons.get(jid, {}).get(button, False)

    @classmethod
    def get_joy_button_down(cls, button: int, instance_id: int = -1) -> bool:
        """Return True if button was just pressed this frame."""
        jid = cls._resolve_joy_id(instance_id)
        if jid is None:
            return False
        curr = cls._joy_buttons.get(jid, {}).get(button, False)
        prev = cls._joy_buttons_prev.get(jid, {}).get(button, False)
        return curr and not prev

    @classmethod
    def get_joy_button_up(cls, button: int, instance_id: int = -1) -> bool:
        """Return True if button was just released this frame."""
        jid = cls._resolve_joy_id(instance_id)
        if jid is None:
            return False
        curr = cls._joy_buttons.get(jid, {}).get(button, False)
        prev = cls._joy_buttons_prev.get(jid, {}).get(button, False)
        return not curr and prev

    @classmethod
    def get_joy_axis(cls, axis: int, instance_id: int = -1) -> float:
        """Return axis value (-1..1) with deadzone applied."""
        jid = cls._resolve_joy_id(instance_id)
        if jid is None:
            return 0.0
        raw = cls._joy_axes.get(jid, {}).get(axis, 0.0)
        if abs(raw) < cls._joy_deadzone:
            return 0.0
        # Remap from [deadzone..1] to [0..1] preserving sign
        sign = 1.0 if raw > 0 else -1.0
        return sign * (abs(raw) - cls._joy_deadzone) / (1.0 - cls._joy_deadzone)

    @classmethod
    def get_joy_hat(cls, hat: int = 0, instance_id: int = -1) -> tuple:
        """Return D-pad / hat value as (x, y) where x,y are -1, 0, or 1."""
        jid = cls._resolve_joy_id(instance_id)
        if jid is None:
            return (0, 0)
        return cls._joy_hats.get(jid, {}).get(hat, (0, 0))

    # -- Internal joystick helpers --

    @classmethod
    def _resolve_joy_id(cls, instance_id: int):
        if instance_id == -1:
            if cls._joysticks:
                return next(iter(cls._joysticks))
            return None
        return instance_id if instance_id in cls._joysticks else None

    @classmethod
    def _get_joystick(cls, instance_id: int):
        jid = cls._resolve_joy_id(instance_id)
        return cls._joysticks.get(jid) if jid is not None else None

    @classmethod
    def _process_joystick_event(cls, event):
        if event.type == pygame.JOYDEVICEADDED:
            joy = pygame.joystick.Joystick(event.device_index)
            joy.init()
            jid = joy.get_instance_id()
            cls._joysticks[jid] = joy
            cls._joy_buttons[jid] = {}
            cls._joy_axes[jid] = {}
            cls._joy_hats[jid] = {}
        elif event.type == pygame.JOYDEVICEREMOVED:
            jid = event.instance_id
            cls._joysticks.pop(jid, None)
            cls._joy_buttons.pop(jid, None)
            cls._joy_buttons_prev.pop(jid, None)
            cls._joy_axes.pop(jid, None)
            cls._joy_hats.pop(jid, None)
        elif event.type == pygame.JOYBUTTONDOWN:
            cls._joy_buttons.setdefault(event.instance_id, {})[event.button] = True
        elif event.type == pygame.JOYBUTTONUP:
            cls._joy_buttons.setdefault(event.instance_id, {})[event.button] = False
        elif event.type == pygame.JOYAXISMOTION:
            cls._joy_axes.setdefault(event.instance_id, {})[event.axis] = event.value
        elif event.type == pygame.JOYHATMOTION:
            cls._joy_hats.setdefault(event.instance_id, {})[event.hat] = event.value

    @classmethod
    def _update_joystick_state(cls):
        """Refresh continuous joystick state from SDL."""
        for jid, joy in cls._joysticks.items():
            axes = cls._joy_axes.setdefault(jid, {})
            for i in range(joy.get_numaxes()):
                axes[i] = joy.get_axis(i)
            btns = cls._joy_buttons.setdefault(jid, {})
            for i in range(joy.get_numbuttons()):
                btns[i] = joy.get_button(i)
            hats = cls._joy_hats.setdefault(jid, {})
            for i in range(joy.get_numhats()):
                hats[i] = joy.get_hat(i)

    # -----------------------------------------------------------------------
    # Touch
    # -----------------------------------------------------------------------
    @classmethod
    def get_touches(cls) -> dict[int, TouchPoint]:
        """Return dict of all currently active touch points {finger_id: TouchPoint}."""
        return cls._touches

    @classmethod
    def get_touch_count(cls) -> int:
        """Return number of currently active touch points."""
        return len(cls._touches)

    @classmethod
    def get_touches_started(cls) -> list[TouchPoint]:
        """Return list of touches that began this frame."""
        return cls._touches_started

    @classmethod
    def get_touches_moved(cls) -> list[TouchPoint]:
        """Return list of touches that moved this frame."""
        return cls._touches_moved

    @classmethod
    def get_touches_ended(cls) -> list[TouchPoint]:
        """Return list of touches that ended this frame."""
        return cls._touches_ended

    @classmethod
    def is_touching(cls) -> bool:
        """Return True if any finger is currently touching."""
        return len(cls._touches) > 0

    # -- Internal touch helpers --

    @classmethod
    def _process_touch_event(cls, event):
        if event.type == pygame.FINGERDOWN:
            # SDL touch coords are normalized 0..1, convert to window pixels
            w, h = pygame.display.get_surface().get_size() if pygame.display.get_surface() else (1, 1)
            tp = TouchPoint(
                finger_id=event.finger_id,
                x=event.x * w, y=event.y * h,
                dx=event.dx * w, dy=event.dy * h,
                pressure=getattr(event, "pressure", 1.0)
            )
            cls._touches[event.finger_id] = tp
            cls._touches_started.append(tp)
            # Gesture: record start
            cls._gesture_tap_start[event.finger_id] = (tp.x, tp.y, time.time())

        elif event.type == pygame.FINGERMOTION:
            w, h = pygame.display.get_surface().get_size() if pygame.display.get_surface() else (1, 1)
            tp = TouchPoint(
                finger_id=event.finger_id,
                x=event.x * w, y=event.y * h,
                dx=event.dx * w, dy=event.dy * h,
                pressure=getattr(event, "pressure", 1.0)
            )
            cls._touches[event.finger_id] = tp
            cls._touches_moved.append(tp)

        elif event.type == pygame.FINGERUP:
            w, h = pygame.display.get_surface().get_size() if pygame.display.get_surface() else (1, 1)
            tp = TouchPoint(
                finger_id=event.finger_id,
                x=event.x * w, y=event.y * h,
                dx=event.dx * w, dy=event.dy * h,
                pressure=0.0
            )
            cls._touches.pop(event.finger_id, None)
            cls._touches_ended.append(tp)

    # -----------------------------------------------------------------------
    # Gesture recognition
    # -----------------------------------------------------------------------
    @classmethod
    def get_gesture(cls) -> TouchGesture:
        """Return the recognized gesture data for the current frame."""
        return cls._gesture

    @classmethod
    def _recognize_gestures(cls):
        now = time.time()
        g = cls._gesture

        # --- Tap / Double-tap / Swipe (on finger up) ---
        for tp in cls._touches_ended:
            start = cls._gesture_tap_start.pop(tp.finger_id, None)
            if start is None:
                continue
            sx, sy, st = start
            dist = math.hypot(tp.x - sx, tp.y - sy)
            duration = now - st

            if dist <= cls._gesture_tap_radius:
                if duration < cls._gesture_long_press_threshold:
                    # It's a tap
                    g.tap = True
                    # Check double-tap
                    if (now - cls._gesture_last_tap_time < cls._gesture_double_tap_time
                            and math.hypot(tp.x - cls._gesture_last_tap_pos[0],
                                           tp.y - cls._gesture_last_tap_pos[1]) < cls._gesture_tap_radius * 2):
                        g.double_tap = True
                    cls._gesture_last_tap_time = now
                    cls._gesture_last_tap_pos = (tp.x, tp.y)
            elif dist >= cls._gesture_swipe_min_dist and duration < 0.5:
                # It's a swipe
                g.swipe = True
                dx = tp.x - sx
                dy = tp.y - sy
                length = math.hypot(dx, dy)
                g.swipe_direction = (dx / length, dy / length) if length > 0 else (0.0, 0.0)
                g.swipe_velocity = length / max(duration, 0.001)

        # --- Long press detection (finger still held) ---
        if len(cls._touches) == 1:
            fid = next(iter(cls._touches))
            start = cls._gesture_tap_start.get(fid)
            if start:
                sx, sy, st = start
                tp = cls._touches[fid]
                dist = math.hypot(tp.x - sx, tp.y - sy)
                if dist <= cls._gesture_tap_radius and (now - st) >= cls._gesture_long_press_threshold:
                    g.long_press = True

        # --- Pinch & Rotate (two fingers) ---
        if len(cls._touches) == 2:
            fingers = list(cls._touches.values())
            f1, f2 = fingers[0], fingers[1]
            cx = (f1.x + f2.x) / 2.0
            cy = (f1.y + f2.y) / 2.0
            dist = math.hypot(f2.x - f1.x, f2.y - f1.y)
            angle = math.atan2(f2.y - f1.y, f2.x - f1.x)

            if cls._gesture_prev_pinch_dist > 0:
                # Pinch
                if dist > 0:
                    g.pinch = True
                    g.pinch_scale = dist / cls._gesture_prev_pinch_dist
                    g.pinch_center = (cx, cy)
                # Rotate
                delta_angle = angle - cls._gesture_prev_pinch_angle
                # Normalize to [-pi, pi]
                while delta_angle > math.pi:
                    delta_angle -= 2 * math.pi
                while delta_angle < -math.pi:
                    delta_angle += 2 * math.pi
                if abs(delta_angle) > 0.001:
                    g.rotate = True
                    g.rotate_angle = delta_angle
                    g.rotate_center = (cx, cy)

            cls._gesture_prev_pinch_dist = dist
            cls._gesture_prev_pinch_angle = angle
        else:
            cls._gesture_prev_pinch_dist = 0.0
            cls._gesture_prev_pinch_angle = 0.0

        # Clean up stale gesture starts for fingers no longer present
        active_ids = set(cls._touches.keys())
        stale = [fid for fid in cls._gesture_tap_start if fid not in active_ids]
        for fid in stale:
            cls._gesture_tap_start.pop(fid, None)

    # -----------------------------------------------------------------------
    # Joystick convenience constants (common gamepad mapping)
    # -----------------------------------------------------------------------
    # Buttons (Xbox-style layout, SDL default)
    JOY_A = 0
    JOY_B = 1
    JOY_X = 2
    JOY_Y = 3
    JOY_LB = 4       # Left bumper
    JOY_RB = 5       # Right bumper
    JOY_BACK = 6
    JOY_START = 7
    JOY_L3 = 8       # Left stick press
    JOY_R3 = 9       # Right stick press
    # Axes
    JOY_LEFT_X = 0
    JOY_LEFT_Y = 1
    JOY_RIGHT_X = 2
    JOY_RIGHT_Y = 3
    JOY_LT = 4       # Left trigger
    JOY_RT = 5        # Right trigger
