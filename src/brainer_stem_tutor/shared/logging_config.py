"""Logging configuration for the brainer_stem_tutor stack.

Kept independent from `mcp_prompts_server.logging_config` so the two can be
configured separately (different log files, different levels). Idempotent:
calling `setup_logging` twice doesn't duplicate handlers.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .settings import TutorSettings, get_settings

_BRAINER_LOGGER_NAME = "brainer_stem_tutor"
_CONFIGURED = False


def setup_logging(settings: TutorSettings | None = None) -> logging.Logger:
    """Configure the brainer_stem_tutor logger tree.

    - Attaches a rotating file handler at the path from settings.LOG_FILE
      (5MB, 5 backups) and a stderr stream handler.
    - Logs propagate to the root logger so apps that already have logging
      configured see brainer messages without extra wiring.
    - Idempotent.
    """
    global _CONFIGURED
    s = settings or get_settings()
    logger = logging.getLogger(_BRAINER_LOGGER_NAME)
    logger.setLevel(s.LOG_LEVEL)
    if _CONFIGURED:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    s.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(s.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    _CONFIGURED = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger under the brainer_stem_tutor namespace.

    Use as `from .shared.logging_config import get_logger;
    logger = get_logger(__name__)` so module names compose into the tree.
    """
    if name.startswith(_BRAINER_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{_BRAINER_LOGGER_NAME}.{name.rsplit('.', 1)[-1]}")
