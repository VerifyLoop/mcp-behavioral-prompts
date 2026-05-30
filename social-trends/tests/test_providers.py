"""Provider tests. No network: httpx MockTransport stands in for upstreams,
returning the real Helix / ScrapeCreators response shapes."""
from __future__ import annotations

import httpx
import pytest

from social_trends.providers.base import ProviderUnavailable
from social_trends.providers.scrapecreators import ScrapeCreatorsProvider
from social_trends.providers.twitch import TwitchProvider
from social_trends.schemas import Platform, TwitchEntryKind
from social_trends.settings import Settings

# --- Helix "Get Top Games" shape, as returned by the real API and mock-api ---
TWITCH_TOP_GAMES = {
    "data": [
        {"id": "509658", "name": "Just Chatting", "box_art_url": "https://x/jc.jpg"},
        {"id": "32982", "name": "Grand Theft Auto V", "box_art_url": "https://x/gta.jpg"},
    ],
    "pagination": {"cursor": "abc"},
}

SCRAPECREATORS_HASHTAGS = {
    "hashtags": [
        {"name": "fyp", "volume": 1000000, "growth_rate": 0.12},
        {"name": "italia", "video_count": 50000},
    ]
}


def _client(payload: dict) -> httpx.AsyncClient:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    return httpx.AsyncClient(transport=transport)


async def test_twitch_mock_path_is_available_without_credentials():
    provider = TwitchProvider(settings=Settings(TWITCH_USE_MOCK=True))
    ok, reason = provider.available()
    assert ok and reason == ""


async def test_twitch_real_path_requires_credentials():
    provider = TwitchProvider(settings=Settings(TWITCH_USE_MOCK=False))
    ok, reason = provider.available()
    assert not ok and "TWITCH_CLIENT_ID" in reason
    with pytest.raises(ProviderUnavailable):
        await provider.top_games()


async def test_twitch_top_games_normalization():
    provider = TwitchProvider(
        settings=Settings(TWITCH_USE_MOCK=True),
        client=_client(TWITCH_TOP_GAMES),
    )
    entries = await provider.top_games(first=2)
    assert [e.name for e in entries] == ["Just Chatting", "Grand Theft Auto V"]
    assert entries[0].rank == 1 and entries[1].rank == 2
    assert all(e.kind is TwitchEntryKind.game for e in entries)
    assert all(e.source == "twitch" for e in entries)


async def test_scrapecreators_unavailable_without_key():
    provider = ScrapeCreatorsProvider(settings=Settings(SCRAPECREATORS_API_KEY=None))
    ok, reason = provider.available()
    assert not ok and "SCRAPECREATORS_API_KEY" in reason


async def test_scrapecreators_hashtag_normalization():
    provider = ScrapeCreatorsProvider(
        settings=Settings(SCRAPECREATORS_API_KEY="test-key"),
        client=_client(SCRAPECREATORS_HASHTAGS),
    )
    items = await provider.trending_hashtags(Platform.tiktok, country="IT", first=2)
    assert [i.name for i in items] == ["fyp", "italia"]
    assert items[0].volume == 1000000 and items[0].growth_rate == 0.12
    assert items[1].volume == 50000  # video_count fallback
    assert all(i.country == "IT" and i.source == "scrapecreators" for i in items)
