"""Standalone entry point for the Affilio MCP server.

Usage:
    # stdio transport (default — for Claude Desktop, Cursor, etc.)
    python -m affilio_mcp

    # SSE transport on a custom port
    python -m affilio_mcp --transport sse --port 8010

    # Streamable HTTP
    python -m affilio_mcp --transport streamable-http --port 8010

Environment variables:
    MONGO_URL          — MongoDB connection string  (default: mongodb://localhost:27017)
    MONGO_DATABASE     — database name              (default: test)
    REDIS_URL          — Redis URL (optional, caching disabled without it)
    REDIRECT_DOMAIN    — base URL for short links   (default: https://affilio.link)
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Affilio MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind (SSE/HTTP only)"
    )
    parser.add_argument(
        "--port", type=int, default=8010, help="Port to bind (SSE/HTTP only)"
    )
    args = parser.parse_args()

    # Import here so env vars can be configured before import-time side effects
    from affilio_mcp.mcp_surface import mcp

    transport_kwargs = {}
    if args.transport in ("sse", "streamable-http"):
        transport_kwargs["host"] = args.host
        transport_kwargs["port"] = args.port

    mcp.run(transport=args.transport, **transport_kwargs)


if __name__ == "__main__":
    main()

