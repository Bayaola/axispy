from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Callable
import sys


@dataclass(frozen=True)
class LogRecord:
    timestamp: str
    level: str
    level_value: int
    subsystem: str
    message: str
    data: dict[str, Any]


class LogLevels:
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40

    _name_to_value = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR
    }
    _value_to_name = {
        DEBUG: "DEBUG",
        INFO: "INFO",
        WARNING: "WARNING",
        ERROR: "ERROR"
    }

    @classmethod
    def parse(cls, level: int | str):
        if isinstance(level, str):
            return cls._name_to_value.get(level.upper(), cls.INFO)
        return int(level)

    @classmethod
    def name(cls, level: int):
        return cls._value_to_name.get(int(level), "INFO")


_lock = RLock()
_sinks: list[Callable[[LogRecord], None]] = []
_min_level = LogLevels.INFO


def _default_sink(record: LogRecord):
    if record.data:
        msg = f"[{record.timestamp}] [{record.level}] [{record.subsystem}] {record.message} | {record.data}"
        print(msg)
        sys.stdout.flush()
        return
    msg = f"[{record.timestamp}] [{record.level}] [{record.subsystem}] {record.message}"
    print(msg)
    sys.stdout.flush()


def add_sink(sink: Callable[[LogRecord], None]):
    with _lock:
        if sink not in _sinks:
            _sinks.append(sink)


def remove_sink(sink: Callable[[LogRecord], None]):
    with _lock:
        if sink in _sinks:
            _sinks.remove(sink)


def set_min_level(level: int | str):
    global _min_level
    _min_level = LogLevels.parse(level)


def get_min_level():
    return _min_level


def emit(level: int | str, subsystem: str, message: str, **data):
    level_value = LogLevels.parse(level)
    if level_value < _min_level:
        return
    record = LogRecord(
        timestamp=datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        level=LogLevels.name(level_value),
        level_value=level_value,
        subsystem=subsystem or "engine",
        message=str(message),
        data=data if data else {}
    )
    with _lock:
        active_sinks = list(_sinks)
    if not active_sinks:
        _default_sink(record)
        return
    for sink in active_sinks:
        try:
            sink(record)
        except Exception:
            _default_sink(record)


class Logger:
    def __init__(self, subsystem: str):
        self.subsystem = subsystem

    def debug(self, message: str, **data):
        emit(LogLevels.DEBUG, self.subsystem, message, **data)

    def info(self, message: str, **data):
        emit(LogLevels.INFO, self.subsystem, message, **data)

    def warning(self, message: str, **data):
        emit(LogLevels.WARNING, self.subsystem, message, **data)

    def error(self, message: str, **data):
        emit(LogLevels.ERROR, self.subsystem, message, **data)


def get_logger(subsystem: str):
    return Logger(subsystem)
