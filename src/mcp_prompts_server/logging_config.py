import logging
import sys
from logging.handlers import RotatingFileHandler

from colorlog import ColoredFormatter

from .config import Settings

def setup_logging(settings: Settings) -> None:
    """Configure structured logging with colored console output and rotating file handler."""
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        return

    root_logger.setLevel(settings.LOG_LEVEL)

    console_formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s "
        "%(blue)s[%(name)s]%(reset)s "
        "%(message)s",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-8s [%(name)s:%(lineno)d] - %(message)s"
    )
    file_handler = RotatingFileHandler(
        settings.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    logging.info(f"Logging configured at level: {settings.LOG_LEVEL}")