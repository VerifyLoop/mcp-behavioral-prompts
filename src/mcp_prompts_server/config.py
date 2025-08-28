from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LOG_LEVEL_TYPE = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

class Settings(BaseSettings):
    """Server settings loaded from .env file with validation."""
    SERVER_NAME: str = "MCP-Behavioral-Prompts"
    LOG_LEVEL: LOG_LEVEL_TYPE = "INFO"
    LOG_FILE: Path = Path("logs/server.log")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

settings = Settings()