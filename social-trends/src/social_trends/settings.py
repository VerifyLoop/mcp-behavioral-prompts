"""Runtime configuration, loaded from environment / .env.

Secrets are intentionally optional: a provider whose key is absent reports
itself unavailable (with a clear reason) instead of crashing the server. This
lets the whole stack boot and the credential-free paths (Twitch mock-api) work
even when no real keys are configured.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SERVER_NAME: str = "social-trends-mcp"

    # --- ScrapeCreators (primary deep-metadata provider) ---
    SCRAPECREATORS_API_KEY: str | None = None
    SCRAPECREATORS_BASE_URL: str = "https://api.scrapecreators.com"

    # --- Apify (broad scraping actors) ---
    APIFY_TOKEN: str | None = None

    # --- Bright Data (geo / unblocked web) ---
    BRIGHTDATA_API_TOKEN: str | None = None

    # --- Twitch ---
    # Real API needs a Client-Id + app token. The local mock-api server
    # (`twitch mock-api start`) needs neither real credential and is what the
    # tests and the credential-free demo target.
    TWITCH_CLIENT_ID: str | None = None
    TWITCH_APP_TOKEN: str | None = None
    TWITCH_API_BASE: str = "https://api.twitch.tv/helix"
    TWITCH_USE_MOCK: bool = False
    TWITCH_MOCK_BASE: str = "http://localhost:8080/mock"

    HTTP_TIMEOUT_S: float = 15.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
