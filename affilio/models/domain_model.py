"""DUMMY Domain model.

NOTE: This is a stub class for standalone affilio-mcp usage.
Not backed by real ODMantic/MongoDB. Used for type hints only.
"""
from __future__ import annotations

from typing import Optional


class Domain:
    """Placeholder Domain model for type hints and attribute access."""
    domain: str = ""
    malware_status: Optional[str] = None
    safe_to_use: Optional[bool] = None

