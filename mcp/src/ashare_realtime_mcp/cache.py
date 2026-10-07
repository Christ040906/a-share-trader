from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class _Entry:
    value: object
    created: float


class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl = max(0, int(ttl_seconds))
        self._data: dict[str, _Entry] = {}

    def get(self, key: str):
        entry = self._data.get(key)
        if entry is None:
            return None
        if self.ttl and monotonic() - entry.created > self.ttl:
            self._data.pop(key, None)
            return None
        return entry.value

    def put(self, key: str, value):
        self._data[key] = _Entry(value=value, created=monotonic())
