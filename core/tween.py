"""Tween/easing system for declarative property animation.

Usage from a user script::

    class MyScript:
        def on_start(self):
            # Animate transform.x to 500 over 1 second with ease_out_cubic
            self.tween(self.entity, "transform.x", target=500, duration=1.0,
                       easing=ease_out_cubic)

            # Animate with explicit start value
            self.tween(self.entity, "transform.rotation", start=0, target=360,
                       duration=2.0, easing=ease_in_out_quad, loops=0)

The ``ScriptSystem`` ticks the tween manager each frame via
``TweenManager.tick(dt)``.
"""
from __future__ import annotations
import math
from core.logger import get_logger

_tw_logger = get_logger("tween")


# ---------------------------------------------------------------------------
# Easing functions  (t: 0..1 -> 0..1)
# ---------------------------------------------------------------------------

def ease_linear(t: float) -> float:
    return t

def ease_in_quad(t: float) -> float:
    return t * t

def ease_out_quad(t: float) -> float:
    return t * (2.0 - t)

def ease_in_out_quad(t: float) -> float:
    if t < 0.5:
        return 2.0 * t * t
    return -1.0 + (4.0 - 2.0 * t) * t

def ease_in_cubic(t: float) -> float:
    return t * t * t

def ease_out_cubic(t: float) -> float:
    t -= 1.0
    return t * t * t + 1.0

def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4.0 * t * t * t
    t -= 1.0
    return 1.0 + 4.0 * t * t * t

def ease_in_elastic(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return -math.pow(2, 10 * (t - 1)) * math.sin((t - 1.1) * 5.0 * math.pi)

def ease_out_elastic(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return math.pow(2, -10 * t) * math.sin((t - 0.1) * 5.0 * math.pi) + 1.0

def ease_in_out_elastic(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    if t < 0.5:
        return -0.5 * math.pow(2, 10 * (2 * t - 1)) * math.sin((2 * t - 1.1) * 5.0 * math.pi)
    return 0.5 * math.pow(2, -10 * (2 * t - 1)) * math.sin((2 * t - 1.1) * 5.0 * math.pi) + 1.0

def ease_in_bounce(t: float) -> float:
    return 1.0 - ease_out_bounce(1.0 - t)

def ease_out_bounce(t: float) -> float:
    if t < 1.0 / 2.75:
        return 7.5625 * t * t
    elif t < 2.0 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    elif t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    else:
        t -= 2.625 / 2.75
        return 7.5625 * t * t + 0.984375

def ease_in_out_bounce(t: float) -> float:
    if t < 0.5:
        return 0.5 * ease_in_bounce(2.0 * t)
    return 0.5 * ease_out_bounce(2.0 * t - 1.0) + 0.5

def ease_in_back(t: float) -> float:
    s = 1.70158
    return t * t * ((s + 1.0) * t - s)

def ease_out_back(t: float) -> float:
    s = 1.70158
    t -= 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0

def ease_in_out_back(t: float) -> float:
    s = 1.70158 * 1.525
    t *= 2.0
    if t < 1.0:
        return 0.5 * (t * t * ((s + 1.0) * t - s))
    t -= 2.0
    return 0.5 * (t * t * ((s + 1.0) * t + s) + 2.0)


# ---------------------------------------------------------------------------
# Tween data
# ---------------------------------------------------------------------------

class _Tween:
    __slots__ = ("entity", "attr_path", "start_val", "end_val",
                 "duration", "elapsed", "easing", "on_complete",
                 "loops", "loop_count", "yoyo", "_forward")

    def __init__(self, entity, attr_path: str, start_val: float, end_val: float,
                 duration: float, easing, on_complete, loops: int, yoyo: bool):
        self.entity = entity
        self.attr_path = attr_path
        self.start_val = start_val
        self.end_val = end_val
        self.duration = max(0.001, duration)
        self.elapsed = 0.0
        self.easing = easing
        self.on_complete = on_complete
        self.loops = loops          # -1 = infinite, 0 = play once, N = repeat N extra times
        self.loop_count = 0
        self.yoyo = yoyo
        self._forward = True


# ---------------------------------------------------------------------------
# Tween manager
# ---------------------------------------------------------------------------

def _resolve_attr(obj, path: str):
    """Resolve a dotted attribute path like 'transform.x' on *obj*.
    Returns (parent_obj, final_attr_name) or (None, None) on failure."""
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        current = getattr(current, part, None)
        if current is None:
            # Try component lookup
            if hasattr(obj, "get_component"):
                from core.components import Transform
                _component_map = {"transform": Transform}
                comp_type = _component_map.get(part.lower())
                if comp_type:
                    current = obj.get_component(comp_type)
            if current is None:
                return None, None
    return current, parts[-1]


class TweenManager:
    """Manages a set of active tweens.  Typically one per entity or global."""

    def __init__(self):
        self._tweens: list[_Tween] = []

    def tween(self, entity, attr_path: str, target: float,
              start: float | None = None, duration: float = 1.0,
              easing=None, on_complete=None, loops: int = 0,
              yoyo: bool = False):
        """Create and register a new tween.

        Args:
            entity: The entity whose property to animate.
            attr_path: Dotted path to the property, e.g. ``"transform.x"``.
            target: Target value.
            start: Start value. If ``None``, the current value is read.
            duration: Animation duration in seconds.
            easing: Easing function ``(t) -> t``. Defaults to ``ease_linear``.
            on_complete: Optional callback invoked when the tween finishes.
            loops: ``0`` = play once, ``-1`` = infinite, ``N`` = repeat N extra times.
            yoyo: If True, alternates direction on each loop.
        """
        if easing is None:
            easing = ease_linear
        if start is None:
            parent, attr = _resolve_attr(entity, attr_path)
            if parent is not None:
                start = float(getattr(parent, attr, 0.0))
            else:
                start = 0.0
        tw = _Tween(entity, attr_path, float(start), float(target),
                     duration, easing, on_complete, loops, yoyo)
        self._tweens.append(tw)
        return tw

    def cancel_all(self, entity=None):
        """Cancel tweens.  If *entity* is given, cancel only that entity's tweens."""
        if entity is None:
            self._tweens.clear()
        else:
            self._tweens = [tw for tw in self._tweens if tw.entity is not entity]

    @property
    def count(self) -> int:
        return len(self._tweens)

    def tick(self, dt: float):
        """Advance all tweens by *dt* seconds.  Call once per frame."""
        still_alive: list[_Tween] = []
        for tw in self._tweens:
            tw.elapsed += dt
            t = min(tw.elapsed / tw.duration, 1.0)
            eased = tw.easing(t)

            if tw.yoyo and not tw._forward:
                value = tw.end_val + (tw.start_val - tw.end_val) * eased
            else:
                value = tw.start_val + (tw.end_val - tw.start_val) * eased

            # Apply value
            parent, attr = _resolve_attr(tw.entity, tw.attr_path)
            if parent is not None:
                try:
                    setattr(parent, attr, value)
                except Exception as e:
                    _tw_logger.error("Tween set failed", path=tw.attr_path, error=str(e))
                    continue  # drop this tween

            if t >= 1.0:
                # Loop handling
                if tw.loops == -1 or tw.loop_count < tw.loops:
                    tw.loop_count += 1
                    tw.elapsed = 0.0
                    if tw.yoyo:
                        tw._forward = not tw._forward
                    still_alive.append(tw)
                else:
                    # Finished
                    if tw.on_complete:
                        try:
                            tw.on_complete()
                        except Exception as e:
                            _tw_logger.error("Tween on_complete error", error=str(e))
            else:
                still_alive.append(tw)

        self._tweens = still_alive
