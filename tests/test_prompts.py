"""Smoke tests for prompt registration and rendering on the FastMCP app."""
from __future__ import annotations

import pytest

from mcp_prompts_server.app import app
from mcp_prompts_server.prompts import registry  # noqa: F401  ensures registration

EXPECTED_PROMPT_NAMES = {
    "project_analyst_prompt",
    "socratic_consultant_prompt",
    "critical_code_reviewer_prompt",
    "software_architect_prompt",
}


@pytest.mark.asyncio
async def test_all_prompts_are_registered():
    registered = {p.name for p in await app.list_prompts()}
    missing = EXPECTED_PROMPT_NAMES - registered
    assert not missing, f"Missing prompts: {missing}"


@pytest.mark.asyncio
async def test_project_analyst_uses_version_argument():
    result = await app.get_prompt("project_analyst_prompt", {"version": "7"})
    rendered = "\n".join(m.content.text for m in result.messages)
    assert "v7" in rendered


@pytest.mark.asyncio
async def test_critical_code_reviewer_context_is_injected():
    result = await app.get_prompt(
        "critical_code_reviewer_prompt",
        {"context": "prototype", "language": "Python"},
    )
    rendered = "\n".join(m.content.text for m in result.messages)
    assert "prototype" in rendered
    assert "Python" in rendered


@pytest.mark.asyncio
async def test_socratic_default_has_no_focus_header():
    result = await app.get_prompt("socratic_consultant_prompt", {})
    rendered = "\n".join(m.content.text for m in result.messages)
    assert "FOCUS DELL'ANALISI" not in rendered


@pytest.mark.asyncio
async def test_socratic_with_topic_includes_focus_header():
    result = await app.get_prompt(
        "socratic_consultant_prompt", {"topic": "go-to-market strategy"}
    )
    rendered = "\n".join(m.content.text for m in result.messages)
    assert "FOCUS DELL'ANALISI" in rendered
    assert "go-to-market strategy" in rendered
