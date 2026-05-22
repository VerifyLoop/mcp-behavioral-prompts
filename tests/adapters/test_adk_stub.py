"""The ADK stub raises a clear ImportError when ADK isn't on the path.

This documents that the scaffolding compiles + has the right shape, while
making it obvious to a future developer how to wire the real LlmAgent.
"""
from __future__ import annotations

import pytest

from brainer_stem_tutor.adapters.adk import build_adk_solver_agent_stub


def test_clear_error_when_adk_missing():
    # `google.adk` isn't installed in CI; the stub must raise a clear hint.
    with pytest.raises(ImportError) as exc:
        build_adk_solver_agent_stub()
    msg = str(exc.value).lower()
    assert "google adk" in msg or "google-adk" in msg
