"""Per-process quota for Gemini clue extraction.

The backend runs as a single instance while the in-memory store is the source of
truth, so a process-local window is accurate enough. The quota fails closed:
when the window is full, the job is rejected instead of calling Gemini.

The counters reset on restart. That is acceptable for now and will move to
Firestore together with shared state.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from .limits import get_limits

_HOUR = 3600.0
_DAY = 86400.0

_lock = threading.Lock()
_events: deque[float] = deque()


class QuotaExceeded(Exception):
    """Raised when the extraction quota is exhausted."""


def _prune(now: float) -> None:
    while _events and now - _events[0] > _DAY:
        _events.popleft()


def check_and_record() -> None:
    """Reserve one extraction. Raises ``QuotaExceeded`` when the quota is full."""
    limits = get_limits()
    now = time.time()
    with _lock:
        _prune(now)
        last_hour = sum(1 for stamp in _events if now - stamp <= _HOUR)
        if last_hour >= limits.gemini_max_per_hour:
            raise QuotaExceeded(
                f"Gemini hourly limit reached ({limits.gemini_max_per_hour} jobs)"
            )
        if len(_events) >= limits.gemini_max_per_day:
            raise QuotaExceeded(
                f"Gemini daily limit reached ({limits.gemini_max_per_day} jobs)"
            )
        _events.append(now)


def usage() -> dict[str, int]:
    """Return current usage and the active limits for the GOD window."""
    limits = get_limits()
    now = time.time()
    with _lock:
        _prune(now)
        last_hour = sum(1 for stamp in _events if now - stamp <= _HOUR)
        last_day = len(_events)
    return {
        "lastHour": last_hour,
        "lastDay": last_day,
        "maxPerHour": limits.gemini_max_per_hour,
        "maxPerDay": limits.gemini_max_per_day,
    }


def reset_quota() -> None:
    with _lock:
        _events.clear()
