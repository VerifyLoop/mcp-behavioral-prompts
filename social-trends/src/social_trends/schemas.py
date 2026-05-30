"""Canonical, cross-platform schemas.

Every record carries provenance (`source`, `fetched_at`) so downstream
consumers can audit where a datum came from — a hard requirement given the
data-source constraints documented in docs/social-trends-mcp-plan.md (sec. 1).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TypeVar

from pydantic import BaseModel, Field, SerializeAsAny


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Platform(str, Enum):
    tiktok = "tiktok"
    instagram = "instagram"
    twitch = "twitch"
    youtube = "youtube"


class HashtagTrend(BaseModel):
    platform: Platform
    name: str
    country: str | None = None
    volume: int | None = None
    growth_rate: float | None = None
    source: str
    fetched_at: datetime = Field(default_factory=_utcnow)


class TwitchEntryKind(str, Enum):
    game = "game"
    stream = "stream"


class TwitchEntry(BaseModel):
    kind: TwitchEntryKind
    id: str
    name: str
    rank: int
    viewer_count: int | None = None
    box_art_url: str | None = None
    source: str
    fetched_at: datetime = Field(default_factory=_utcnow)


T = TypeVar("T", bound=BaseModel)


class TrendsResponse(BaseModel):
    """Uniform envelope returned by every tool."""

    items: list[SerializeAsAny[BaseModel]]
    sources: list[str]
    count: int
    cost_estimate_usd: float = 0.0
    cache_hit: bool = False
    fetched_at: datetime = Field(default_factory=_utcnow)

    @classmethod
    def of(
        cls,
        items: list[BaseModel],
        *,
        sources: list[str],
        cost_estimate_usd: float = 0.0,
        cache_hit: bool = False,
    ) -> "TrendsResponse":
        return cls(
            items=items,
            sources=sources,
            count=len(items),
            cost_estimate_usd=cost_estimate_usd,
            cache_hit=cache_hit,
        )
