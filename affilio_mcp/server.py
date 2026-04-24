from __future__ import annotations

import datetime
import hashlib
import io
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse

from PIL.PngImagePlugin import PngInfo
from fastapi import FastAPI, HTTPException, Request, Path
from fastapi.responses import JSONResponse, RedirectResponse, Response

from affilio.db import engine
from affilio.models.domain_model import Domain
from affilio.models.url_models import ShortLink
from affilio.qr_code_generator import QRCodeGenerator
from affilio.redis_connection import redis_conn
from affilio.utils import (
    extract_domain,
    generate_short_code, resolve_client_ip,
)
from affilio_mcp.mcp_surface import build_mcp, BRAND_TAGLINE, REDIRECT_DOMAIN
from affilio_mcp.schemas import ShortenRequest, ShortenResponse

logger = logging.getLogger("affilio_mcp.server")

# Security headers to apply to responses (exclude Cache-Control here so
# endpoints can set caching semantics per-resource)
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}
SHORT_CODE_LENGTH = 7  # 62^7 ~= 3.5 trillion possible codes, balancing uniqueness with length

# Default expiry (days) for new short links. Set MCP_DEFAULT_EXPIRES_DAYS=0 to disable.
MCP_DEFAULT_EXPIRES_DAYS = int(os.getenv("MCP_DEFAULT_EXPIRES_DAYS", "30"))


async def _shorten_fn(target_url: str, client_ip: str = "unknown", short_code_length:int = 7) -> dict:
    """Create a ShortLink record and return structured dict for MCP tooling.

    This is intentionally lightweight: it stores a ShortLink document in the
    shared affilio DB and marks its classification based on any existing
    Domain record. If the domain is already known safe it is marked
    'allowlisted' and cached to Redis so the redirect path can be served
    directly from Redis without DB/hit-tracking.
    """
    domain = extract_domain(target_url)

    # quick domain check: known-malicious or explicitly unsafe
    domain_record: Optional[Domain] = await engine.find_one(Domain, Domain.domain == domain)
    if domain_record and (domain_record.malware_status == "malicious" or domain_record.safe_to_use is False):
        # mirror demo endpoint behaviour
        raise HTTPException(status_code=422, detail="Target URL failed security check.")

    # If the target URL already has a short link, return it instead of creating
    # a duplicate. Log the client_ip for audit but do not overwrite original
    # creator metadata.
    existing = await engine.find_one(ShortLink, ShortLink.target_url == target_url)
    if existing:
        logger.info("Short link already exists for %s; new request from %s", target_url, client_ip)
        return {
            "short_code": existing.short_code,
            "short_url": f"/r/{existing.short_code}",
            "qr_url": f"/qr/{existing.short_code}",
            "expires_at": existing.expires_at,
            "classification": existing.classification,
            "powered_by": BRAND_TAGLINE,
            "pending": existing.classification == "pending",
        }
    classification = "pending"
    now = datetime.datetime.now(datetime.timezone.utc)

    if domain_record and domain_record.safe_to_use:
        classification = "allowlisted"

    # Generate a unique short code. Try a few times to avoid collisions.
    code = None
    attempts = 0
    max_attempts = 5
    # Use a while loop for clarity; still enforce a max attempt limit to avoid
    # an infinite loop in the extremely unlikely event of repeated collisions.
    while attempts < max_attempts:
        candidate = generate_short_code(short_code_length)
        existing_code = await engine.find_one(ShortLink, ShortLink.short_code == candidate)
        if existing_code is None:
            code = candidate
            break
        # Extremely unlikely collision — log a warning with details so we can
        # investigate if it ever happens in production.
        logger.warning(
            "Collision detected while generating short code: %s (attempt %d/%d). This should not happen.",
            candidate,
            attempts + 1,
            max_attempts,
        )
        attempts += 1
    if code is None:
        # very unlikely: all attempts collided
        raise HTTPException(status_code=500, detail="Failed to allocate short code")

    # Compute expires_at according to MCP_DEFAULT_EXPIRES_DAYS. If set to 0
    # the link will not expire (expires_at remains None).
    expires_at: Optional[datetime.datetime] = None
    if MCP_DEFAULT_EXPIRES_DAYS and MCP_DEFAULT_EXPIRES_DAYS > 0:
        expires_at = now + datetime.timedelta(days=MCP_DEFAULT_EXPIRES_DAYS)

    short = ShortLink(
        short_code=code,
        target_url=target_url,
        domain=domain,
        classification=classification,
        client_ip=client_ip,
        created_at=now,
        expires_at=expires_at,
    )
    await engine.save(short)

    # If safe, cache mapping in Redis so redirect can avoid DB/hit-tracker.
    if classification != "pending":
        try:
            redis_conn.set(name=f"mcp:short:{code}", value=target_url, ex=60 * 60 * 24 * 7)
        except Exception:
            logger.exception("Failed to set redis cache for short link %s", code)

    # Return minimal structured dict for MCP clients; the mcp_surface wrapper
    # will augment this into text/image/json payloads.
    return {
        "short_code": code,
        "short_url": f"/r/{code}",
        "qr_url": f"/qr/{code}",
        "expires_at": expires_at,
        "classification": classification,
        "powered_by": BRAND_TAGLINE,
        "pending": classification == "pending",
    }


# Build the MCP instance and its ASGI app early so we can wire up the lifespan.
_mcp_instance = build_mcp()
_mcp_asgi = _mcp_instance.http_app(transport="streamable-http", path="/", json_response=True)


@asynccontextmanager
async def _lifespan(app):
    """Run the FastMCP lifespan inside the FastAPI lifespan so the
    StreamableHTTPSessionManager task group gets properly initialized."""
    async with _mcp_asgi.lifespan(_mcp_asgi):
        yield


# HTTP app that exposes a small subset of endpoints (shorten, redirect, qr,
# health) and mounts the FastMCP streamable-http transport under /mcp.
app = FastAPI(redirect_slashes=False, lifespan=_lifespan)


@app.middleware("http")
async def _handle_mcp_options(request: Request, call_next):
    # If an OPTIONS preflight targets the mount root /mcp, respond directly
    # so Starlette doesn't issue a trailing-slash 307 redirect.
    if request.method == "OPTIONS" and request.url.path == "/mcp":
        origin = request.headers.get("Origin", "*")
        acr_headers = request.headers.get("Access-Control-Request-Headers", "*")
        return Response(status_code=200, headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": acr_headers,
            "Access-Control-Max-Age": "3600",
        })
    # Rewrite /mcp to /mcp/ so Starlette's Mount matches the sub-app route.
    if request.url.path == "/mcp":
        request.scope["path"] = "/mcp/"
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in _SECURITY_HEADERS.items():
        if k not in response.headers:
            response.headers[k] = v
    return response


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.post("/shorten", response_model=ShortenResponse)
async def http_shorten(payload: ShortenRequest, request: Request):
    # Strict input validation via ShortenRequest (AnyHttpUrl) ensures only
    # http/https URLs are accepted.
    url = str(payload.url)
    client_ip = resolve_client_ip(request)

    data = await _shorten_fn(url, client_ip=client_ip, short_code_length=SHORT_CODE_LENGTH)

    # Build full URLs using the incoming request root so clients receive
    # usable absolute URLs when calling the service directly.
    base = str(request.url.replace(path="/", query=""))
    full_short = base.rstrip("/") + data["short_url"]
    full_qr = base.rstrip("/") + data["qr_url"]

    resp = ShortenResponse(
        short_url=full_short,
        qr_url=full_qr,
        expires_at=data.get("expires_at"),
        classification=data.get("classification"),
        powered_by=data.get("powered_by"),
        pending=data.get("pending"),
    )
    return resp


@app.get("/r/{code}")
async def http_redirect(code: str = Path(..., min_length=SHORT_CODE_LENGTH, max_length=SHORT_CODE_LENGTH)):
    # First try Redis cache to avoid DB + hit-tracker for common allowlisted links
    cached = redis_conn.get(f"mcp:short:{code}")
    if cached:
        # Redis returns bytes for get(). Ensure we decode bytes to str and
        # normalize the URL so the Location header contains a valid
        # http(s) URL instead of a Python bytes repr (e.g. "b'telex.hu'").
        if isinstance(cached, (bytes, bytearray)):
            cached_val = cached.decode("utf-8", errors="ignore")
        else:
            cached_val = str(cached)

        # If the cached value has no scheme, prepend https:// as the safe
        # default (the system expects http/https targets).

        parsed_cached = urlparse(cached_val)
        if parsed_cached.scheme not in ("http", "https"):
            cached_val = "https://" + cached_val.lstrip("/")

        # Allow clients to cache allowlisted redirects. Use 302 for
        # compatibility with existing clients/tests (historically 302).
        return RedirectResponse(
            url=cached_val,
            status_code=302,
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )

    short = await engine.find_one(ShortLink, ShortLink.short_code == code)
    if not short:
        raise HTTPException(status_code=404, detail="Short link not found")

    if short.classification == "unsafe":
        raise HTTPException(status_code=451, detail="This link has been disabled for security reasons.")
    if short.classification == "pending":
        raise HTTPException(status_code=202, detail="This link is awaiting security verification. Please try again shortly.")

    # If the link is allowlisted, allow caching and return a 307 preserving
    # client method semantics. Cache the mapping in Redis for subsequent
    # requests.
    if short.classification == "allowlisted":
        try:
            # Ensure we cache a string (not bytes) and store a normalized URL
            _to_cache = short.target_url
            if isinstance(_to_cache, (bytes, bytearray)):
                _to_cache = _to_cache.decode("utf-8", errors="ignore")

            # Normalize scheme for cached value as above
            parsed_to_cache = urlparse(str(_to_cache))
            if parsed_to_cache.scheme not in ("http", "https"):
                _to_cache = "https://" + str(_to_cache).lstrip("/")

            redis_conn.set(name=f"mcp:short:{code}", value=_to_cache, ex=60 * 60 * 24 * 7)
        except Exception:
            logger.exception("Failed to set redis cache for short link %s", code)

        # Normalize short.target_url for the immediate redirect too
        _target = short.target_url
        if isinstance(_target, (bytes, bytearray)):
            _target = _target.decode("utf-8", errors="ignore")
        parsed_target = urlparse(str(_target))
        if parsed_target.scheme not in ("http", "https"):
            _target = "https://" + str(_target).lstrip("/")

        return RedirectResponse(
            url=_target,
            status_code=302,
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )

    # Non-allowlisted links: keep the temporary 302 redirect without caching
    _target = short.target_url
    if isinstance(_target, (bytes, bytearray)):
        _target = _target.decode("utf-8", errors="ignore")
    parsed_target = urlparse(str(_target))
    if parsed_target.scheme not in ("http", "https"):
        _target = "https://" + str(_target).lstrip("/")
    return RedirectResponse(url=_target, status_code=302)


@app.get("/qr/{code}")
async def http_qr( request: Request, code: str = Path(..., min_length=SHORT_CODE_LENGTH, max_length=SHORT_CODE_LENGTH)):
    short = await engine.find_one(ShortLink, ShortLink.short_code == code)
    if not short:
        raise HTTPException(status_code=404, detail="Short link not found")

    # Try Redis cache for QR image bytes first
    cache_key = f"mcp:qr:{code}"
    try:
        cached = redis_conn.get(cache_key)
    except Exception:
        cached = None

    if cached:
        # cached is raw bytes
        img_bytes = cached
        etag = hashlib.sha256(img_bytes).hexdigest()
        content_length = str(len(img_bytes))
        return Response(
            content=img_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "Content-Disposition": f'inline; filename="Affilio-qr-{code}.png"',
                "Content-Length": content_length,
                "ETag": f'"{etag}"',
            },
        )

    qr = QRCodeGenerator(
        url=f"{REDIRECT_DOMAIN}/r/{code}",
        logo="https://affilio.link/favico.png",
        background_color="#FFFFFF",
        background_transparent=True,
        color="#000000",
        rounded=True,
    )
    img = qr.get_qr_code()

    # Add PNG metadata suitable for Content Credentials and platform provenance.
    png_info = PngInfo()
    base = str(request.url.replace(path="/", query=""))
    cc_payload = json.dumps({"provider": "affilio.link", "short_url": f"{base.rstrip('/')}/r/{code}"})
    png_info.add_text("Content-Credential", cc_payload)
    png_info.add_text("Source", "mcp.affilio.link")

    img_io = io.BytesIO()
    img.save(img_io, format="PNG", pnginfo=png_info)
    img_io.seek(0)
    img_bytes = img_io.getvalue()

    # ETag and Content-Length for caching validation
    etag = hashlib.sha256(img_bytes).hexdigest()
    content_length = str(len(img_bytes))

    # Cache the QR bytes in Redis for faster subsequent responses
    try:
        redis_conn.set(name=cache_key, value=img_bytes, ex=60 * 60 * 24 * 7)
    except Exception:
        logger.exception("Failed to cache QR image for %s", code)

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=604800, immutable",
            "Content-Disposition": f'inline; filename="Affilio-qr-{code}.png"',
            "Content-Length": content_length,
            "ETag": f'"{etag}"',
        },
    )


# Mount FastMCP as an ASGI sub-app under /mcp for SSE transport.
# FastMCP v3 uses .http_app() to produce a Starlette/ASGI application.
try:
    app.mount("/mcp", _mcp_asgi)
except Exception:
    logger.exception("Failed to mount FastMCP ASGI app during startup")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010)
