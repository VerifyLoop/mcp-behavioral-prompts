"""Behavioral prompt definitions, registered on the shared FastMCP app.

Each prompt body lives in a Markdown template under `templates/`; this
module wires the templates to MCP prompt names and parameters.
"""
import logging
from typing import Literal

from mcp.server.fastmcp.prompts.base import UserMessage

from ..app import app
from .loader import render_template

logger = logging.getLogger(__name__)


@app.prompt(title="Complex Project Analyst")
async def project_analyst_prompt(version: int = 1) -> UserMessage:
    """Iterative project definition through descriptive refinement cycles.

    Args:
        version: Iteration number to display in the output header (v$version).
    """
    logger.debug("Activating prompt: Complex Project Analyst (v=%s)", version)
    text = render_template("project_analyst", version=str(version))
    return UserMessage(content=text)


@app.prompt(title="Socratic Strategic Consultant")
async def socratic_consultant_prompt(topic: str = "") -> UserMessage:
    """Strategic consulting via critical Socratic questioning.

    Args:
        topic: Optional focus area to anchor the critical questions.
    """
    logger.debug("Activating prompt: Socratic Strategic Consultant (topic=%r)", topic)
    topic_block = (
        f"**FOCUS DELL'ANALISI**: {topic.strip()}\n\n" if topic.strip() else ""
    )
    text = render_template("socratic_consultant", topic_block=topic_block)
    return UserMessage(content=text)


@app.prompt(title="Critical Code Reviewer")
async def critical_code_reviewer_prompt(
    context: Literal["prototype", "development", "production"] = "production",
    language: str = "",
) -> UserMessage:
    """Critical code review focused on issues blocking the target context.

    Args:
        context: Target operational context (prototype/development/production).
        language: Optional programming language to focus the review on.
    """
    logger.debug(
        "Activating prompt: Critical Code Reviewer (context=%s, language=%r)",
        context,
        language,
    )
    language_block = (
        f"**Target language**: {language.strip()}\n\n" if language.strip() else ""
    )
    text = render_template(
        "critical_code_reviewer",
        context=context,
        language_block=language_block,
    )
    return UserMessage(content=text)


@app.prompt(title="AI Software Architect (Planning)")
async def software_architect_prompt(
    context: Literal["prototype", "development", "production"] = "production",
) -> UserMessage:
    """Structured software planning and design process.

    Args:
        context: Operational context that drives risk depth and trade-offs.
    """
    logger.debug("Activating prompt: AI Software Architect (context=%s)", context)
    text = render_template("software_architect", context=context)
    return UserMessage(content=text)
