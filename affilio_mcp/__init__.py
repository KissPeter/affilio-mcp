"""affilio_mcp — Standalone MCP server for Affilio link shortening & QR codes.

Run standalone:
    python -m affilio_mcp              # stdio transport (default for MCP clients)
    python -m affilio_mcp --transport sse --port 8010  # SSE transport

Or import the FastMCP instance:
    from affilio_mcp import mcp
"""

