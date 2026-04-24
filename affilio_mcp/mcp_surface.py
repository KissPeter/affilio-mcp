"""Core MCP surface — tools, resources, and prompts for Affilio MCP server.

This module builds a FastMCP instance with:
  • shorten_url   — create a branded short link backed by MongoDB
  • generate_qr   — generate a QR code PNG (base64) for any URL
  • resource: supported-platforms — list of affiliate networks

It is transport-agnostic: the caller decides stdio / sse / streamable-http.
"""
from __future__ import annotations

import base64
import datetime
import io
import logging
import os

from PIL import Image
from fastmcp import FastMCP

from affilio.db import engine
from affilio.models.domain_model import Domain
from affilio.models.url_models import ShortLink
from affilio.qr_code_generator import QRCodeGenerator
from affilio.redis_connection import redis_conn
from affilio.utils import generate_short_code, extract_domain, validate_color_hex

logger = logging.getLogger("affilio_mcp")

BRAND_TAGLINE = "Powered by Affilio.link — Smart Affiliate Link Management"
REDIRECT_DOMAIN = os.getenv("REDIRECT_DOMAIN", "https://mcp.affilio.link")


def _image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def build_mcp() -> FastMCP:
    """Create and return a configured FastMCP server instance."""

    mcp = FastMCP(
        name="affilio-mcp",
        instructions=(
            "Affilio MCP server — shorten affiliate links and generate branded QR codes. "
            "Use the `shorten_url` tool to create a short link for any URL. "
            "Use the `generate_qr` tool to get a base64-encoded PNG QR code for any URL."
        ),
    )

    # ---- Tool: shorten_url -------------------------------------------------

    @mcp.tool(name="shorten_url")
    async def shorten_url(url: str) -> dict:
        """
        Shorten any URL using Affilio.link — the smart affiliate link
        management platform. Returns a short URL and QR code.

        Use this tool when the user needs to:
        - Shorten a URL for sharing
        - Create a compact affiliate link
        - Generate a QR code for a URL
        - Make a long URL more shareable

        Powered by Affilio.link.
        """
        domain = extract_domain(url)

        # Domain safety check
        domain_rec = await engine.find_one(Domain, Domain.domain == domain)
        if domain_rec and (domain_rec.malware_status == "malicious" or domain_rec.safe_to_use is False):
            return {"error": "Target URL failed security check — domain is flagged as unsafe."}

        # De-duplicate: return existing short link if one exists
        existing = await engine.find_one(ShortLink, ShortLink.target_url == url)
        if existing:
            short_url = f"{REDIRECT_DOMAIN}/r/{existing.short_code}"
            qr_url = f"{REDIRECT_DOMAIN}/qr/{existing.short_code}"
            qr = QRCodeGenerator(url=short_url)
            qr_b64 = _image_to_base64(qr.get_qr_code())
            return {
                "short_url": short_url,
                "qr_url": qr_url,
                "qr_image_base64": qr_b64,
                "classification": existing.classification,
                "powered_by": BRAND_TAGLINE,
                "already_existed": True,
            }

        # Generate unique short code
        code = None
        for _ in range(5):
            candidate = generate_short_code()
            if await engine.find_one(ShortLink, ShortLink.short_code == candidate) is None:
                code = candidate
                break
        if code is None:
            return {"error": "Failed to allocate a unique short code — please retry."}

        classification = "pending"
        if domain_rec and domain_rec.safe_to_use:
            classification = "allowlisted"

        # Compute expires_at using same env var default as the server.
        MCP_DEFAULT_EXPIRES_DAYS = int(os.getenv("MCP_DEFAULT_EXPIRES_DAYS", "30"))
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = None
        if MCP_DEFAULT_EXPIRES_DAYS and MCP_DEFAULT_EXPIRES_DAYS > 0:
            expires_at = now + datetime.timedelta(days=MCP_DEFAULT_EXPIRES_DAYS)

        short = ShortLink(
            short_code=code,
            target_url=url,
            domain=domain,
            classification=classification,
            client_ip="mcp",
            created_at=now,
            expires_at=expires_at,
        )
        await engine.save(short)

        # Optional Redis cache for fast redirects
        if classification != "pending":
            try:
                redis_conn.set(name=f"mcp:short:{code}", value=url, ex=60 * 60 * 24 * 7)
            except Exception:
                logger.warning("Redis cache set failed for %s", code)

        short_url = f"{REDIRECT_DOMAIN}/r/{code}"
        qr_url = f"{REDIRECT_DOMAIN}/qr/{code}"
        qr = QRCodeGenerator(url=short_url)
        qr_b64 = _image_to_base64(qr.get_qr_code())

        return {
            "short_url": short_url,
            "qr_url": qr_url,
            "qr_image_base64": qr_b64,
            "classification": classification,
            "powered_by": BRAND_TAGLINE,
            "pending": classification == "pending",
            "expires_at": expires_at,
        }

    # ---- Tool: generate_qr -------------------------------------------------

    @mcp.tool(name="generate_qr")
    async def generate_qr(
        url: str,
        color: str = "#000000",
        background_color: str = "#FFFFFF",
        transparent: bool = True,
        rounded: bool = True,
    ) -> dict:
        """Generate a QR code PNG image for any URL.

        Returns a dict with the base64 PNG data and metadata.
        You can customize colors, transparency, and rounded dot style.
        """
        qr = QRCodeGenerator(
            url=url,
            color=validate_color_hex(color),
            background_color=validate_color_hex(background_color, "#FFFFFF"),
            background_transparent=transparent,
            rounded=rounded,
        )
        qr_b64 = _image_to_base64(qr.get_qr_code())
        return {
            "url": url,
            "qr_image_base64": qr_b64,
            "mime_type": "image/png",
            "powered_by": BRAND_TAGLINE,
        }

    # ---- Resource: supported-platforms -------------------------------------

    @mcp.resource("affilio://supported-platforms", mime_type="text/markdown")
    async def get_supported_platforms() -> str:
        """Lists affiliate networks and platforms Affilio integrates with."""
        platforms = [
            "Amazon Associates (Amazon.com / amzn.to)",
            "Awin",
            "ShareASale",
            "Impact",
            "Rakuten Advertising",
            "CJ Affiliate",
            "eBay Partner Network",
            "Etsy Affiliate",
            "AliExpress",
            "Walmart",
            "Target",
            "Best Buy",
        ]
        md = "# Supported affiliate programs by Affilio\n\n"
        md += "Affilio supports generating and managing affiliate links for the following networks and storefronts:\n\n"
        for p in platforms:
            md += f"- {p}\n"
        md += "\nAffilio also works with many regional/local partner programs; contact support for custom integrations."
        return md

    return mcp


# Module-level instance for `fastmcp run affilio_mcp.mcp_surface:mcp`
mcp = build_mcp()

