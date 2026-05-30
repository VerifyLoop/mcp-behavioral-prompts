"""Capability → provider routing.

Keeping routing in one place is the third boundary from the plan: tools ask the
registry for a capability, the registry hands back the right provider (or raises
a clear ProviderUnavailable). Swapping the primary provider for a capability is
a one-line change here.
"""
from __future__ import annotations

from .base import Provider
from .scrapecreators import ScrapeCreatorsProvider
from .twitch import TwitchProvider

# Capability identifiers used by the tools.
HASHTAGS = "trends.hashtags"
TWITCH_TOP = "twitch.top"

_PRIMARY: dict[str, type[Provider]] = {
    HASHTAGS: ScrapeCreatorsProvider,
    TWITCH_TOP: TwitchProvider,
}


def resolve(capability: str) -> Provider:
    try:
        provider_cls = _PRIMARY[capability]
    except KeyError as exc:  # pragma: no cover - guards programmer error
        raise KeyError(f"unknown capability '{capability}'") from exc
    return provider_cls()


def status() -> list[dict[str, object]]:
    """Report each capability's provider and whether it is usable right now."""
    rows: list[dict[str, object]] = []
    for capability, provider_cls in _PRIMARY.items():
        provider = provider_cls()
        ok, reason = provider.available()
        rows.append(
            {"capability": capability, "provider": provider.name,
             "available": ok, "reason": reason}
        )
    return rows
