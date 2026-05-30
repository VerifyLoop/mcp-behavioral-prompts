# social-trends-mcp

Aggregation **MCP server + CLI** for social trends (TikTok, Instagram, Twitch, …).
It fronts heterogeneous upstreams — **Apify**, **Bright Data**, **ScrapeCreators**, the
**Twitch CLI/API** — behind a small set of canonical, Pydantic-validated tools. All
deterministic work (normalization, dedup, provenance) lives in the server; an agent that
uses it only orchestrates.

Design rationale and roadmap: [`../docs/social-trends-mcp-plan.md`](../docs/social-trends-mcp-plan.md).
What is actually wired vs. what is blocked on credentials: [`CONNECT.md`](CONNECT.md).

## Status (Phase 1)

| Capability | Tool / CLI | Provider | Works now? |
|---|---|---|---|
| Twitch top games | `twitch-top` | Twitch (real API **or** `mock-api`) | ✅ via `mock-api`, no credentials |
| Trending hashtags | `hashtags <platform>` | ScrapeCreators | ⛔ needs `SCRAPECREATORS_API_KEY` |
| Provider status | `list-providers` | — | ✅ |

## Quickstart

```bash
cd social-trends
poetry install
cp .env.example .env          # add keys for the providers you have

poetry run social-trends list-providers          # what is usable right now
poetry run social-trends version

# Credential-free demo against the Twitch mock-api (see CONNECT.md):
#   twitch mock-api generate && twitch mock-api start &
TWITCH_USE_MOCK=true poetry run social-trends twitch-top --json

# As an MCP server over stdio (for Claude Desktop / Cursor / Claude Code):
poetry run social-trends-mcp
```

## Tests

```bash
poetry run pytest        # no network; httpx MockTransport stands in for upstreams
```
