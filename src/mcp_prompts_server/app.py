import logging
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from .config import settings

logger = logging.getLogger(__name__)

# Central FastMCP instance imported by all primitive modules
app = FastMCP(
    name=settings.SERVER_NAME,
    instructions="This server provides behavioral prompts for AI assistant modification."
)

@app.tool()
async def health_check() -> str:
    """Production health check endpoint."""
    return f"OK - {settings.SERVER_NAME} active at {datetime.now().isoformat()}"

logger.info(f"FastMCP instance '{settings.SERVER_NAME}' created.")