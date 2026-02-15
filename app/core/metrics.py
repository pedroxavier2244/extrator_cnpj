from __future__ import annotations

import threading
import time
from typing import Any


class MetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters = {
            "requests_total": 0,
            "cache_hits_total": 0,
            "cache_misses_total": 0,
            "db_errors_total": 0,
        }

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def snapshot(self, uptime_seconds: float) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
        counters["uptime_seconds"] = uptime_seconds
        return counters


_METRICS: MetricsStore | None = None
_METRICS_LOCK = threading.Lock()
_STARTUP_TIME: float | None = None
_STARTUP_LOCK = threading.Lock()


def set_startup_time(startup_time: float | None = None) -> None:
    global _STARTUP_TIME
    with _STARTUP_LOCK:
        _STARTUP_TIME = startup_time if startup_time is not None else time.monotonic()


def get_uptime_seconds() -> float:
    global _STARTUP_TIME
    if _STARTUP_TIME is None:
        set_startup_time()
    return time.monotonic() - (_STARTUP_TIME or time.monotonic())


def get_metrics_store() -> MetricsStore:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = MetricsStore()
    return _METRICS


def increment_requests_total() -> None:
    get_metrics_store().increment("requests_total")


def increment_cache_hits_total(amount: int = 1) -> None:
    get_metrics_store().increment("cache_hits_total", amount)


def increment_cache_misses_total(amount: int = 1) -> None:
    get_metrics_store().increment("cache_misses_total", amount)


def increment_db_errors_total(amount: int = 1) -> None:
    get_metrics_store().increment("db_errors_total", amount)
