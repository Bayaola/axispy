from core.ecs import Component


class TimerComponent(Component):
    """A simple timer component for user scripts.

    Usage from a script::

        timer = self.entity.add_component(TimerComponent(
            duration=2.0,
            one_shot=True,
            autostart=True,
            callback=self.on_timer_done,
        ))

    Or create and start later::

        timer = self.entity.add_component(TimerComponent(duration=1.5))
        timer.start()

    The callback is invoked each time the timer expires.  For repeating
    timers (``one_shot=False``), it fires every ``duration`` seconds.
    """

    def __init__(
        self,
        duration: float = 1.0,
        one_shot: bool = True,
        autostart: bool = False,
        callback=None,
    ):
        self.entity = None
        self.duration = max(0.0, float(duration))
        self.one_shot = bool(one_shot)
        self.callback = callback
        self._elapsed = 0.0
        self._running = bool(autostart)
        self._finished = False

    # -- Public API ----------------------------------------------------------

    def start(self):
        """(Re)start the timer from zero."""
        self._elapsed = 0.0
        self._running = True
        self._finished = False

    def stop(self):
        """Stop the timer without resetting elapsed time."""
        self._running = False

    def reset(self):
        """Reset elapsed time to zero and stop."""
        self._elapsed = 0.0
        self._running = False
        self._finished = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_finished(self) -> bool:
        return self._finished

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def time_left(self) -> float:
        return max(0.0, self.duration - self._elapsed)

    # -- Called by TimerSystem each frame -------------------------------------

    def tick(self, dt: float):
        if not self._running:
            return
        self._elapsed += dt
        while self._elapsed >= self.duration and self._running:
            self._elapsed -= self.duration
            if self.callback:
                self.callback()
            if self.one_shot:
                self._running = False
                self._finished = True
                self._elapsed = self.duration
                break
