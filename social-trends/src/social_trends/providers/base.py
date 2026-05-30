"""Provider protocol and shared errors.

A provider wraps exactly one upstream (ScrapeCreators, Apify, Bright Data,
Twitch). It declares which capabilities it can serve and whether it is usable
given the current credentials. The registry routes a capability to a provider;
the provider does the upstream call and returns canonical models.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderUnavailable(RuntimeError):
    """Raised when a provider is selected but cannot run (e.g. missing key)."""

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(f"provider '{provider}' unavailable: {reason}")


class Provider(ABC):
    #: stable identifier used in the `source` field of every record
    name: str

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """Return (usable, reason). `reason` explains why not, when usable=False."""

    def ensure_available(self) -> None:
        ok, reason = self.available()
        if not ok:
            raise ProviderUnavailable(self.name, reason)
