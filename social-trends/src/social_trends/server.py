"""MCP server entrypoint. Mirrors the graceful-shutdown scaffold of this repo."""
from __future__ import annotations

import logging
import signal
import sys
from typing import NoReturn

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(levelname)-8s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

from .app import app  # noqa: E402
from .settings import settings  # noqa: E402


def _signal_handler(signum: int, frame) -> NoReturn:
    logger.info("Received %s. Graceful shutdown.", signal.Signals(signum).name)
    sys.exit(0)


def main() -> None:
    """Run the FastMCP server over stdio."""
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
        logger.info("Starting MCP server '%s'...", settings.SERVER_NAME)
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted. Shutting down.")
    except Exception as exc:  # pragma: no cover
        logger.error("Critical error: %s", exc)
        sys.exit(1)
    finally:
        logger.info("MCP server '%s' terminated.", settings.SERVER_NAME)


if __name__ == "__main__":
    main()
