"""social-trends-mcp: aggregation MCP server + CLI for social trends.

The package fronts heterogeneous upstreams (Apify, Bright Data, ScrapeCreators,
the Twitch CLI/API) behind a small set of canonical, Pydantic-validated tools.
All deterministic work (normalization, dedup, provenance) lives here; an agent
that uses the server only orchestrates.
"""

__version__ = "0.1.0"
