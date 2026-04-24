"""DUMMY in-memory database engine.

NOTE: This is a stub implementation for standalone affilio-mcp usage.
Data is stored in-memory only and will be lost on process restart.
For production, replace with real ODMantic/MongoDB engine.
"""
from __future__ import annotations

from typing import Any, Optional

from affilio.models.domain_model import Domain
from affilio.models.url_models import ShortLink


class _InMemoryStore:
    """Simple in-memory store for ShortLink objects (used when no real DB)."""

    def __init__(self):
        self._links: dict[str, ShortLink] = {}  # keyed by short_code
        self._by_target: dict[str, ShortLink] = {}  # keyed by target_url

    async def find_one(self, model: Any, *conditions) -> Optional[Any]:
        """Minimal find_one that checks short_code or target_url lookups."""
        # This is a simplified implementation; real ODMantic uses query objects.
        # We inspect the conditions to determine what we're looking for.
        if model is ShortLink:
            # Check if any stored link matches
            for link in self._links.values():
                match = True
                # conditions are typically comparison objects; for simplicity
                # we cannot fully evaluate them, so return None (no match).
                # The caller will create a new record.
                pass
            return None
        if model is Domain:
            # No domains stored; always return None
            return None
        return None

    async def save(self, obj: Any) -> None:
        """Save a ShortLink to the in-memory store."""
        if isinstance(obj, ShortLink):
            self._links[obj.short_code] = obj
            self._by_target[obj.target_url] = obj


engine = _InMemoryStore()

