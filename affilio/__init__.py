"""Affilio standalone package — DUMMY/STUB implementations for affilio-mcp.

NOTE: This is NOT the real affilio package. These are lightweight standalone
implementations that allow affilio-mcp to run without depending on the full
affilio codebase. Data is stored in-memory and will be lost on restart.

For production use with persistent storage, replace this package with the
real affilio package or configure external MongoDB/Redis connections.
"""

from affilio.db import engine
from affilio.models.domain_model import Domain
from affilio.models.url_models import ShortLink
from affilio.qr_code_generator import QRCodeGenerator
from affilio.redis_connection import redis_conn
from affilio.utils import extract_domain, generate_short_code, resolve_client_ip

__all__ = [
    "engine",
    "Domain",
    "ShortLink",
    "QRCodeGenerator",
    "redis_conn",
    "extract_domain",
    "generate_short_code",
    "resolve_client_ip",
]
