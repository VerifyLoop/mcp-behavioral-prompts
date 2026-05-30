"""FastMCP instance and canonical tools.

Tools are thin: validate input, ask the registry for a provider, normalize the
result into the uniform `TrendsResponse` envelope. No upstream-specific logic
leaks above this layer.
"""
import logging
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from . import providers as P
from .providers.base import ProviderUnavailable
from .providers.scrapecreators import ScrapeCreatorsProvider
from .providers.twitch import TwitchProvider
from .schemas import Platform, TrendsResponse
from .settings import settings

logger = logging.getLogger(__name__)

app = FastMCP(
    name=settings.SERVER_NAME,
    instructions=(
        "Aggregation server for social trends. Tools front Apify, Bright Data, "
        "ScrapeCreators and Twitch behind canonical, normalized responses. "
        "Use list_providers to see which capabilities are usable right now."
    ),
)


@app.tool()
async def health_check() -> str:
    """Production health check endpoint."""
    return f"OK - {settings.SERVER_NAME} active at {datetime.now(timezone.utc).isoformat()}"


@app.tool()
async def list_providers() -> list[dict]:
    """List each capability, its backing provider, and whether it is usable now."""
    return P.registry.status()


@app.tool()
async def twitch_top(first: int = 10) -> dict:
    """Top Twitch games by viewers (derived from Helix Get Top Games).

    Targets the real API when TWITCH_CLIENT_ID/APP_TOKEN are set, or the local
    `twitch mock-api` server when TWITCH_USE_MOCK=true.
    """
    provider = TwitchProvider()
    try:
        entries = await provider.top_games(first=first)
    except ProviderUnavailable as exc:
        return {"error": str(exc), "items": [], "sources": [provider.name]}
    return TrendsResponse.of(entries, sources=[provider.name]).model_dump(mode="json")


@app.tool()
async def trends_hashtags(platform: str, country: str = "", first: int = 20) -> dict:
    """Trending hashtags for a platform (ScrapeCreators), optionally by country.

    Pass an empty `country` for a global ranking.
    """
    try:
        plat = Platform(platform)
    except ValueError:
        return {"error": f"unknown platform '{platform}'",
                "supported": [p.value for p in Platform], "items": []}
    provider = ScrapeCreatorsProvider()
    try:
        items = await provider.trending_hashtags(plat, country=country or None, first=first)
    except ProviderUnavailable as exc:
        return {"error": str(exc), "items": [], "sources": [provider.name]}
    return TrendsResponse.of(items, sources=[provider.name]).model_dump(mode="json")


logger.info("FastMCP instance '%s' created.", settings.SERVER_NAME)
