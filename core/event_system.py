from typing import Dict, List, Callable, Any

class EventSystem:
    """
    A simple event system that allows subscribing to and emitting events.
    """
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._listener_sets: Dict[str, set] = {}
        self._queue: List[tuple[str, tuple[Any, ...], Dict[str, Any]]] = []

    def subscribe(self, event_name: str, callback: Callable):
        """
        Subscribe to an event.
        :param event_name: Name of the event to listen for.
        :param callback: Function to call when event is emitted.
        """
        if not isinstance(event_name, str):
            raise ValueError("Event name must be a string.")
        if not callable(callback):
            raise ValueError("Callback must be a callable function.")
        if event_name not in self._listeners:
            self._listeners[event_name] = []
            self._listener_sets[event_name] = set()
        if callback not in self._listener_sets[event_name]:
            self._listener_sets[event_name].add(callback)
            self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> bool:
        """
        Unsubscribe from an event.
        :param event_name: Name of the event.
        :param callback: Function to remove.
        :return: True if the callback was removed, False if it was not found.
        """
        if not isinstance(event_name, str):
            return False
        if event_name not in self._listeners:
            return False
        try:
            self._listeners[event_name].remove(callback)
            s = self._listener_sets.get(event_name)
            if s is not None:
                s.discard(callback)
            return True
        except ValueError:
            return False

    def emit(self, event_name: str, *args, **kwargs):
        """
        Queue an event. It will be dispatched by EventDispatchSystem on the
        next simulation tick (1-frame latency).
        :param event_name: Name of the event.
        :param args: Positional arguments to pass to callbacks.
        :param kwargs: Keyword arguments to pass to callbacks.
        """
        if not isinstance(event_name, str):
            raise ValueError("Event name must be a string.")
        self._queue.append((event_name, args, kwargs))

    def emit_immediate(self, event_name: str, *args, **kwargs):
        """
        Emit an event and dispatch it synchronously to all current listeners
        **right now**, bypassing the queue.  Use this when zero-latency
        delivery is required (e.g. damage events that must be processed in
        the same frame they are emitted).
        :param event_name: Name of the event.
        :param args: Positional arguments to pass to callbacks.
        :param kwargs: Keyword arguments to pass to callbacks.
        """
        if not isinstance(event_name, str):
            raise ValueError("Event name must be a string.")
        if event_name in self._listeners:
            for callback in list(self._listeners[event_name]):
                callback(*args, **kwargs)

    def dispatch_pending(self):
        if not self._queue:
            return
        pending = self._queue
        self._queue = []
        for event_name, args, kwargs in pending:
            if event_name in self._listeners:
                for callback in list(self._listeners[event_name]):
                    callback(*args, **kwargs)

    def has_listeners(self, event_name: str) -> bool:
        """Check if an event has any subscribers."""
        return bool(self._listeners.get(event_name))

    def listener_count(self, event_name: str) -> int:
        """Return the number of subscribers for an event."""
        return len(self._listeners.get(event_name, []))

    def clear(self):
        """Removes all listeners."""
        self._listeners.clear()
        self._listener_sets.clear()
        self._queue.clear()
