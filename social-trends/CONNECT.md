# CONNECT — what is actually wired, what is blocked, and how to light it up

Honest status of the live connections, recorded from the build session (2026-05-30).
The hard truth up front: **a sandboxed agent cannot create third-party accounts, complete
browser OAuth, or receive signup/verification emails**, and no API keys were provided. So the
paid upstreams (Apify, Bright Data, ScrapeCreators) are *wired in code* but cannot be exercised
live from here. Everything that does **not** need a credential has been run end-to-end.

## ✅ Verified live in this environment

- **Tooling installs.** `apify-cli` v1.6.1 installed via npm (`npm i -g apify-cli`).
  `@brightdata/mcp` confirmed published on npm (v2.9.5). Twitch CLI v1.1.24 downloaded.
- **Our server + CLI.** `poetry install` clean; `pytest` → **8 passed** (no network — `httpx`
  `MockTransport` returns the real Helix / ScrapeCreators response shapes). All 4 MCP tools
  register (`health_check`, `list_providers`, `twitch_top`, `trends_hashtags`).
- **Live HTTP path (credential-free).** `social-trends twitch-top` and the `twitch_top` MCP tool
  fetch from a real local Helix-shaped server over a socket and return normalized
  `TwitchEntry` records with `source`/`fetched_at` provenance. This is exactly the path the
  Twitch `mock-api` exercises.

## ⚠️ Blocked here, and why

- **Twitch `mock-api` binary.** The official `twitch` CLI v1.1.24 **panics on every command** in
  this sandbox: its startup update-checker calls `api.github.com`, egress is filtered, the empty
  response makes the Go binary index `[0]` of an empty slice and crash
  (`version_checker.go:121`). This is an environment artifact, not a flaw in our code — on a normal
  machine with open egress, `twitch mock-api generate && twitch mock-api start` works, and our
  provider points at it with `TWITCH_USE_MOCK=true` (default base `http://localhost:8080/mock`).
- **Apify / ScrapeCreators / Bright Data.** No keys available; `mcp.apify.com` and
  `docs.scrapecreators.com` return `403` to anonymous requests. Apify additionally needs **browser
  OAuth** which an agent cannot complete. These providers correctly report themselves *unavailable*
  with an actionable reason — run `social-trends list-providers` to see it.
- **`@scrape-creators/mcp` npm package.** The name from the original brief returns **404** on npm.
  The maintained surface is the CLI (`github.com/ScrapeCreators/scrapecreators-cli`) + the REST API
  (`x-api-key`); our `ScrapeCreatorsProvider` calls the REST API directly, which sidesteps the
  package-name question.

## How to light up each provider (drop keys in `.env`)

```bash
# ScrapeCreators — single header, no OAuth. Unblocks `hashtags` + future creator.* tools.
SCRAPECREATORS_API_KEY="sk_..."

# Twitch — real API:
TWITCH_CLIENT_ID="..."; TWITCH_APP_TOKEN="..."        # app access token
# Twitch — local mock (no real credential), once the CLI runs on an open-egress machine:
#   twitch mock-api generate && twitch mock-api start &
TWITCH_USE_MOCK="true"

# Apify — headless: export APIFY_TOKEN; or in Claude Desktop add remote MCP https://mcp.apify.com (OAuth).
APIFY_TOKEN="apify_api_..."

# Bright Data — npx @brightdata/mcp with API_TOKEN + GROUPS=social.
BRIGHTDATA_API_TOKEN="..."
```

Then verify:

```bash
poetry run social-trends list-providers     # the rows you keyed flip to available=yes
poetry run social-trends hashtags tiktok -c IT --json   # once SCRAPECREATORS_API_KEY is set
```

## What I need from you to go fully live

1. A **ScrapeCreators API key** — fastest unlock, single header, no OAuth. Gets `hashtags` (and the
   roadmap's `creator.*`) returning real data immediately.
2. Either a **Twitch app** (Client-ID + Secret → app token) **or** confirmation to run the Twitch
   `mock-api` on a machine with open egress (the mock needs no real credential).
3. Optionally **Apify**/**Bright Data** tokens for the broad-scraping and geo paths.

Without (1)–(3) the live social data cannot be produced from this sandbox, but the moment a key
lands in `.env` the corresponding tool starts returning real, normalized, provenance-tagged data —
no code change required.
