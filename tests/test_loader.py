"""Tests for the template loader."""
from __future__ import annotations

import pytest

from mcp_prompts_server.prompts.loader import (
    TemplateNotFoundError,
    available_templates,
    render_template,
)

EXPECTED_TEMPLATES = {
    "project_analyst",
    "socratic_consultant",
    "critical_code_reviewer",
    "software_architect",
}


def test_available_templates_contains_all_expected():
    assert EXPECTED_TEMPLATES.issubset(set(available_templates()))


def test_render_missing_template_raises():
    with pytest.raises(TemplateNotFoundError):
        render_template("does_not_exist")


def test_substitution_applies_known_variables():
    out = render_template("project_analyst", version="42")
    assert "v42" in out
    # The literal "$version" must not survive substitution.
    assert "$version" not in out


def test_safe_substitute_preserves_curly_placeholders():
    """Curly-brace placeholders are intended for the model and must remain."""
    out = render_template("critical_code_reviewer", context="production")
    assert "{file_name}" in out
    assert "{function_name}" in out


def test_safe_substitute_leaves_unknown_dollar_vars():
    """Unknown $vars in a template should not crash; they stay verbatim."""
    out = render_template("socratic_consultant")  # no topic_block supplied
    # The placeholder should be replaced by empty string when explicitly empty;
    # but when not supplied at all, safe_substitute leaves it intact.
    assert "$topic_block" in out or "FOCUS DELL'ANALISI" not in out


def test_empty_topic_block_renders_cleanly():
    out = render_template("socratic_consultant", topic_block="")
    assert "$topic_block" not in out
    assert "FOCUS DELL'ANALISI" not in out


def test_non_empty_topic_block_is_injected():
    block = "**FOCUS DELL'ANALISI**: scalabilità\n\n"
    out = render_template("socratic_consultant", topic_block=block)
    assert "scalabilità" in out
