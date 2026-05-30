"""ScrapeCreators provider (primary deep-metadata upstream).

Auth is a single `x-api-key` header — no OAuth. Without the key the provider
reports itself unavailable with an actionable reason rather than failing late.
"""
from __future__ import annotations

import httpx

from ..schemas import HashtagTrend, Platform
from ..settings import Settings, settings as default_settings
from .base import Provider


class ScrapeCreatorsProvider(Provider):
    name = "scrapecreators"

    def __init__(self, settings: Settings | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self._s = settings or default_settings
        self._client = client

    def available(self) -> tuple[bool, str]:
        if not self._s.SCRAPECREATORS_API_KEY:
            return False, "set SCRAPECREATORS_API_KEY (single x-api-key header, no OAuth)"
        return True, ""

    async def trending_hashtags(
        self, platform: Platform, country: str | None = None, first: int = 20
    ) -> list[HashtagTrend]:
        self.ensure_available()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._s.HTTP_TIMEOUT_S)
        params = {"platform": platform.value, "limit": first}
        if country:
            params["country"] = country
        try:
            resp = await client.get(
                f"{self._s.SCRAPECREATORS_BASE_URL}/v1/{platform.value}/trending/hashtags",
                params=params,
                headers={"x-api-key": self._s.SCRAPECREATORS_API_KEY or ""},
            )
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if owns_client:
                await client.aclose()

        out: list[HashtagTrend] = []
        for row in payload.get("hashtags", payload.get("data", [])):
            out.append(
                HashtagTrend(
                    platform=platform,
                    name=row.get("name") or row.get("hashtag", ""),
                    country=country,
                    volume=row.get("volume") or row.get("video_count"),
                    growth_rate=row.get("growth_rate"),
                    source=self.name,
                )
            )
        return out
