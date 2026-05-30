"""Twitch provider.

Twitch has no native "trends" endpoint, so we derive trends from Helix
`Get Top Games` / `Get Streams` (ranked by viewers). The same code path targets
either the real API or the local `twitch mock-api` server — the mock needs no
real credential, which makes it the deterministic, cost-free path for tests and
the credential-free demo.
"""
from __future__ import annotations

import httpx

from ..schemas import TwitchEntry, TwitchEntryKind
from ..settings import Settings, settings as default_settings
from .base import Provider


class TwitchProvider(Provider):
    name = "twitch"

    def __init__(self, settings: Settings | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self._s = settings or default_settings
        self._client = client  # injectable for tests

    @property
    def base_url(self) -> str:
        return self._s.TWITCH_MOCK_BASE if self._s.TWITCH_USE_MOCK else self._s.TWITCH_API_BASE

    def available(self) -> tuple[bool, str]:
        if self._s.TWITCH_USE_MOCK:
            return True, ""
        if not self._s.TWITCH_CLIENT_ID or not self._s.TWITCH_APP_TOKEN:
            return False, (
                "set TWITCH_CLIENT_ID + TWITCH_APP_TOKEN for the real API, "
                "or TWITCH_USE_MOCK=true to target `twitch mock-api`"
            )
        return True, ""

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._s.TWITCH_CLIENT_ID:
            h["Client-Id"] = self._s.TWITCH_CLIENT_ID
        if self._s.TWITCH_APP_TOKEN:
            h["Authorization"] = f"Bearer {self._s.TWITCH_APP_TOKEN}"
        return h

    async def top_games(self, first: int = 10) -> list[TwitchEntry]:
        self.ensure_available()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._s.HTTP_TIMEOUT_S)
        try:
            resp = await client.get(
                f"{self.base_url}/games/top",
                params={"first": first},
                headers=self._headers(),
            )
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if owns_client:
                await client.aclose()

        entries: list[TwitchEntry] = []
        for rank, game in enumerate(payload.get("data", []), start=1):
            entries.append(
                TwitchEntry(
                    kind=TwitchEntryKind.game,
                    id=str(game.get("id", "")),
                    name=game.get("name", ""),
                    rank=rank,
                    box_art_url=game.get("box_art_url"),
                    source=self.name,
                )
            )
        return entries
