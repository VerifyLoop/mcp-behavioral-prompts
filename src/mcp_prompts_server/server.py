import logging
import signal
import sys
from typing import NoReturn

from .config import settings
from .logging_config import setup_logging

setup_logging(settings)
logger = logging.getLogger(__name__)

from .app import app

try:
    from . import prompts
    logger.info("Prompts package loaded successfully.")
except ImportError:
    logger.warning("No prompts package found or empty.")

def signal_handler(signum: int, frame) -> NoReturn:
    """Handle termination signals for graceful shutdown."""
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} signal. Graceful shutdown initiated.")
    sys.exit(0)

def main() -> None:
    """Main entry point for MCP server."""
    try:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info(f"Starting MCP server '{settings.SERVER_NAME}'...")
        logger.info("Server ready. Press Ctrl+C to terminate.")
        
        app.run()
        
    except KeyboardInterrupt:
        logger.info("User interruption received. Shutting down...")
    except Exception as e:
        logger.error(f"Critical error during server startup: {e}")
        logger.error("Server cannot start. Check configuration.")
        sys.exit(1)
    finally:
        logger.info(f"MCP server '{settings.SERVER_NAME}' terminated.")

if __name__ == "__main__":
    main()