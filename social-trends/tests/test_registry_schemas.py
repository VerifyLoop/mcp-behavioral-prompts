from __future__ import annotations

from social_trends.providers import registry
from social_trends.schemas import HashtagTrend, Platform, TrendsResponse


def test_registry_status_lists_all_capabilities():
    rows = registry.status()
    caps = {r["capability"] for r in rows}
    assert caps == {registry.HASHTAGS, registry.TWITCH_TOP}
    for r in rows:
        assert isinstance(r["available"], bool)


def test_registry_resolve_returns_provider():
    assert registry.resolve(registry.TWITCH_TOP).name == "twitch"
    assert registry.resolve(registry.HASHTAGS).name == "scrapecreators"


def test_trends_response_envelope_counts_and_serializes():
    items = [HashtagTrend(platform=Platform.tiktok, name="fyp", source="scrapecreators")]
    resp = TrendsResponse.of(items, sources=["scrapecreators"], cost_estimate_usd=0.01)
    assert resp.count == 1
    dumped = resp.model_dump(mode="json")
    assert dumped["count"] == 1
    assert dumped["sources"] == ["scrapecreators"]
    assert dumped["items"][0]["name"] == "fyp"
