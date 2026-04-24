"""DUMMY utility functions for standalone affilio-mcp usage.

NOTE: These are simplified implementations that work without the full
affilio codebase. tldextract is used if available, otherwise falls back
to basic URL parsing.
"""
from __future__ import annotations

import random
import string
from urllib.parse import urlparse

from fastapi import Request

BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase


def _base62_encode(num: int) -> str:
    if num == 0:
        return BASE62_ALPHABET[0]
    result = ""
    while num > 0:
        num, rem = divmod(num, 62)
        result = BASE62_ALPHABET[rem] + result
    return result


def generate_short_code(length: int = 7) -> str:
    """Generate a random base62 short code."""
    max_value = 62 ** length
    rand_num = random.randint(0, max_value - 1)
    return _base62_encode(rand_num).rjust(length, "0")


def extract_domain(url: str) -> str:
    """Extract the registrable domain from a URL."""
    try:
        import tldextract
        ext = tldextract.extract(url)
        return f"{ext.domain}.{ext.suffix}"
    except ImportError:
        # Fallback if tldextract not installed
        parsed = urlparse(url)
        host = parsed.hostname or url
        if host.startswith("www."):
            host = host[4:]
        return host


def resolve_client_ip(request: Request) -> str:
    """Extract the real client IP from request headers."""
    return request.client.host


def validate_color_hex(value: str, default: str = "#000000") -> str:
    """Validate hex color and return it, or return default if invalid."""
    if value is None:
        return default
    if (
        not value.startswith("#")
        or len(value) != 7
        or not all(c in "0123456789abcdefABCDEF" for c in value[1:])
    ):
        return default
    return value
