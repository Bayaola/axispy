"""Lightweight coroutine scheduler for user scripts.

User scripts yield special instruction objects to pause execution::

    class MyScript:
        def on_start(self):
            self.start_coroutine(self.spawn_loop())

        def spawn_loop(self):
            while True:
                self.logger.info("spawning")
                yield Wait(0.5)          # wait 0.5 seconds
                yield WaitFrames(2)      # wait 2 frames

The ``ScriptSystem`` ticks the coroutine manager each frame via
``CoroutineManager.tick(dt)``.
"""
from __future__ import annotations
from typing import Generator
from core.logger import get_logger

_cr_logger = get_logger("coroutine")


# -- Yield instructions ----------------------------------------------------

class Wait:
    """Pause coroutine for *seconds* seconds."""
    __slots__ = ("seconds",)
    def __init__(self, seconds: float):
        self.seconds = max(0.0, float(seconds))


class WaitFrames:
    """Pause coroutine for *frames* render frames."""
    __slots__ = ("frames",)
    def __init__(self, frames: int = 1):
        self.frames = max(1, int(frames))


# -- Coroutine manager -----------------------------------------------------

class _RunningCoroutine:
    __slots__ = ("gen", "wait_time", "wait_frames")

    def __init__(self, gen: Generator):
        self.gen = gen
        self.wait_time = 0.0
        self.wait_frames = 0


class CoroutineManager:
    """Manages a set of running coroutines.  Typically one per entity."""

    def __init__(self):
        self._coroutines: list[_RunningCoroutine] = []

    def start(self, gen: Generator):
        """Schedule a new coroutine (a generator)."""
        cr = _RunningCoroutine(gen)
        # Immediately advance to the first yield
        self._advance(cr)
        self._coroutines.append(cr)

    def stop_all(self):
        """Cancel every running coroutine."""
        for cr in self._coroutines:
            cr.gen.close()
        self._coroutines.clear()

    @property
    def count(self) -> int:
        return len(self._coroutines)

    def tick(self, dt: float):
        """Advance all coroutines by *dt* seconds.  Call once per frame."""
        still_running: list[_RunningCoroutine] = []
        for cr in self._coroutines:
            if cr.wait_frames > 0:
                cr.wait_frames -= 1
                if cr.wait_frames > 0:
                    still_running.append(cr)
                    continue
                # frames expired — advance
                if self._advance(cr):
                    still_running.append(cr)
                continue

            if cr.wait_time > 0.0:
                cr.wait_time -= dt
                if cr.wait_time > 0.0:
                    still_running.append(cr)
                    continue
                # timer expired — advance
                if self._advance(cr):
                    still_running.append(cr)
                continue

            # No wait — advance
            if self._advance(cr):
                still_running.append(cr)

        self._coroutines = still_running

    # -- internal --

    @staticmethod
    def _advance(cr: _RunningCoroutine) -> bool:
        """Step the generator once.  Returns True if still alive."""
        try:
            instruction = next(cr.gen)
        except StopIteration:
            return False
        except Exception as e:
            _cr_logger.error("Coroutine error", error=str(e))
            return False

        if isinstance(instruction, Wait):
            cr.wait_time = instruction.seconds
        elif isinstance(instruction, WaitFrames):
            cr.wait_frames = instruction.frames
        else:
            # Unknown yield value — treat as single-frame wait
            cr.wait_frames = 1
        return True
