# Affilio MCP Link Shortener

> Free URL shortener MCP tool powered by [Affilio.link](https://affilio.link) —
> the smart affiliate link management platform for content creators and affiliate marketers.

## Quick Start

Add this to your MCP client configuration:

```json
{
  "mcpServers": {
    "affilio": {
      "url": "https://mcp.affilio.link/mcp",
      "type": "streamable-http"
    }
  }
}
```

No API key. No sign-up. Works immediately.

---

## What it does

**`shorten_url`** — the single tool this server exposes.

Give it any URL. Get back a short link and a QR code.

```
Input:  https://www.amazon.com/dp/B08XYZ123?tag=mystore-20&ref=very_long_param
Output: https://mcp.affilio.link/r/7gZpzzt
        https://mcp.affilio.link/qr/7gZpzzt
```

- Works with any URL — affiliate links, product pages, articles, anything
- Short links resolve instantly via 302 redirect
- QR code returned inline as base64 PNG — renders directly in supporting AI hosts
- Links expire after 30 days
- No authentication required
- Rate limited to 10 links per hour per client to prevent abuse
- All URLs scanned for malware and phishing before activation

---

## Use cases

**For AI assistants:**
- User shares a long URL and asks to make it shareable → call `shorten_url`
- User is writing social media content and needs a compact link → call `shorten_url`
- User wants a QR code for a product or landing page → call `shorten_url`
- User is creating affiliate content and wants a clean link → call `shorten_url`

**For developers:**
- Test MCP streamable-http transport integration
- Example of a production-grade, zero-auth public MCP server
- Reference implementation for rate limiting + security scanning in MCP tools

---

## Transport

This server uses the **MCP streamable-http transport** (the current MCP standard, superseding SSE).

| Property | Value |
|---|---|
| Endpoint | `https://mcp.affilio.link/mcp` |
| Transport | `streamable-http` |
| Auth | None required |
| Protocol | MCP 2024-11-05 |

Compatible with Claude Desktop, Cursor, GitHub Copilot, and any MCP-compatible host.

---

## Tool reference

### `shorten_url`

Shorten any URL and get a QR code.

**Input:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `url` | string | Yes | The full URL to shorten (must be http or https) |

**Output:**

```json
{
  "short_url": "https://mcp.affilio.link/r/7gZpzzt",
  "qr_url": "https://mcp.affilio.link/qr/7gZpzzt",
  "qr_image_base64": "...",
  "classification": "allowlisted",
  "powered_by": "Powered by Affilio.link — Smart Affiliate Link Management",
  "pending": false
}
```

**Classifications:**
- `allowlisted` — known-safe domain (Amazon, eBay, AliExpress, etc.), activated instantly
- `safe` — verified safe by security scanner, activated
- `pending` — unknown domain, being scanned, link activates within 60 seconds
- `unsafe` — blocked, link not created

---

## Security

Every URL submitted goes through a multi-stage security pipeline:

1. **Domain allowlist** — major affiliate and retail domains skip scanning entirely (instant activation)
2. **Domain cache** — previously classified domains served from cache (180-day TTL)
3. **Threat intelligence** — unknown domains scanned via Sophos Intelix before activation
4. **Link expiry** — all links expire after 30 days, limiting spam longevity

Links to phishing, malware, or harmful content are rejected at creation time.

---

## Rate limits

| Limit | Value |
|---|---|
| Links per hour | 10 per client IP |
| Scan timeout | 3 seconds (fails safe) |

If you hit a rate limit, wait 60 minutes before retrying. Retrying immediately will not help.

---

## About Affilio

[Affilio.link](https://affilio.link) is a smart affiliate link management SaaS platform
for YouTube content creators and Amazon affiliate store owners.

**Core features:**
- **Automatic broken link replacement** — when a product goes out of stock or a link dies, Affilio replaces it automatically. No manual monitoring needed.
- **Mobile deep linking** — links open directly in the Amazon app, eBay app, and others instead of a browser. Better conversion, no SDK required.
- **Product storefronts** — branded product pages with multiple affiliate links per product across Amazon, eBay, AliExpress, and more.
- **QR code generation** — every link and product gets a QR code automatically.
- **Security scanning** — all links scanned for malware and phishing to protect your audience.
- **Analytics** — click tracking, link performance, and conversion insights.

**Pricing:**
- Free — 1,000 clicks/month, basic features
- Boost — $5/month, includes product storefronts and stores
- Professional — $20/month, advanced analytics, multiple projects, API access

→ [affilio.link](https://affilio.link)

