"""In-memory ring buffer for MQTT position debug (development only)."""
from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_MAX = 300
_lock = Lock()
_buffer: deque[dict[str, Any]] = deque(maxlen=_MAX)


def append_event(event: dict[str, Any]) -> None:
    """Append one debug record (thread-safe)."""
    row = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    with _lock:
        _buffer.appendleft(row)


def get_events() -> list[dict[str, Any]]:
    with _lock:
        return list(_buffer)


def clear_events() -> None:
    with _lock:
        _buffer.clear()


def maybe_append_mqtt_debug(event: dict[str, Any]) -> None:
    """Record only when ENABLE_MQTT_DEBUG_PAGE is set (avoids overhead in prod)."""
    from app.config import get_settings

    if get_settings().enable_mqtt_debug_page:
        append_event(event)
