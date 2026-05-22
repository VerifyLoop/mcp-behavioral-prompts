"""MCP prompts that expose the brainer_stem_tutor system prompts to other agents.

The actual prompt text lives next to the agent that uses it (in
`brainer_stem_tutor/<layer>/prompts.py`) so the package can be embedded
without depending on the MCP server. These wrappers republish them as MCP
prompt primitives so a client like Claude Desktop can pick them up.
"""
from __future__ import annotations

import logging

from mcp.server.fastmcp.prompts.base import UserMessage

from brainer_stem_tutor.solver.prompts import SOLVER_SYSTEM_PROMPT
from brainer_stem_tutor.tutor.prompts import TUTOR_SYSTEM_PROMPT
from brainer_stem_tutor.vision.prompts import VISION_SYSTEM_PROMPT

from ..app import app

logger = logging.getLogger(__name__)


@app.prompt(title="Brainer STEM Solver")
async def stem_solver_prompt() -> UserMessage:
    """Structured JSON-output system prompt for the STEM solver agent."""
    logger.debug("Activating prompt: Brainer STEM Solver")
    return UserMessage(content=SOLVER_SYSTEM_PROMPT.strip())


@app.prompt(title="Brainer STEM Socratic Tutor")
async def stem_tutor_prompt() -> UserMessage:
    """Socratic tutor system prompt with anti-leak invariants."""
    logger.debug("Activating prompt: Brainer STEM Socratic Tutor")
    return UserMessage(content=TUTOR_SYSTEM_PROMPT.strip())


@app.prompt(title="Brainer Vision Extractor")
async def stem_vision_prompt() -> UserMessage:
    """Bbox + LaTeX extraction system prompt for the vision agent."""
    logger.debug("Activating prompt: Brainer Vision Extractor")
    return UserMessage(content=VISION_SYSTEM_PROMPT.strip())
