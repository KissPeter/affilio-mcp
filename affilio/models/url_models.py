"""DUMMY URL models.

NOTE: This is a stub class for standalone affilio-mcp usage.
Not backed by real ODMantic/MongoDB. Accepts kwargs as attributes.
"""
from __future__ import annotations

import datetime
from typing import Optional


class ShortLink:
    """Lightweight ShortLink container that accepts arbitrary kwargs as attributes."""

    short_code: str
    target_url: str
    domain: str
    classification: str
    client_ip: str
    created_at: datetime.datetime
    expires_at: Optional[datetime.datetime]

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
