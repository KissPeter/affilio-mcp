"""DUMMY in-memory Redis-like store.

NOTE: This is a stub implementation for standalone affilio-mcp usage.
Data is stored in-memory only and will be lost on process restart.
Expiry (ex parameter) is ignored. For production, use real Redis.
"""
from __future__ import annotations

from typing import Any, Optional


class _InMemoryRedis:
    """Simple in-memory Redis-like store."""

    def __init__(self):
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Optional[bytes]:
        val = self._store.get(key)
        if val is None:
            return None
        # Return as bytes if it's a string
        if isinstance(val, str):
            return val.encode("utf-8")
        return val

    def set(self, name: str, value: Any, ex: Optional[int] = None) -> None:
        # Store value as-is (ignoring expiry for simplicity)
        self._store[name] = value


redis_conn = _InMemoryRedis()
