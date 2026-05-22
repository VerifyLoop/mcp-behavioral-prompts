"""Settings for the brainer_stem_tutor stack.

Kept separate from `mcp_prompts_server.config` so the two libraries do not
collide on env var names and so the tutor can be configured independently.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class TutorSettings(BaseSettings):
    """Configuration for the brainer_stem_tutor stack."""

    SOLVER_MODEL: str = "gemini-2.5-flash"
    TUTOR_MODEL: str = "gemini-2.5-flash"
    VISION_MODEL: str = "gemini-3-flash"

    WOLFRAM_ENABLED: bool = False
    WOLFRAM_CONFIDENCE_THRESHOLD: float = 0.6

    # Anti-leak moderator
    MODERATOR_MAX_CONSECUTIVE_STEPS: int = 2
    MODERATOR_NUMERIC_TOLERANCE: float = 1e-3

    # Follow-policy thresholds (seconds)
    POLICY_STUCK_SECONDS: float = 90.0
    POLICY_FRUSTRATION_THRESHOLD: float = 0.6

    # Live detection
    LIVE_FRAME_DIFF_THRESHOLD: float = 0.05
    LIVE_STABILITY_FRAMES: int = 2

    LOG_LEVEL: LogLevel = "INFO"
    LOG_FILE: Path = Path("logs/brainer_tutor.log")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BRAINER_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> TutorSettings:
    """Cached settings accessor — instantiation reads env once."""
    return TutorSettings()
