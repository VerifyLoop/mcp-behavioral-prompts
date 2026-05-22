"""Solver correctness regression tests for the gaps the audit surfaced.

- Complex-only roots ('x**2 + 1 = 0') must mark verification as failed.
- Multi-variable equations ('solve x**2 - y for x') must mark verification
  as under-specified.
- sympy timeouts must surface as ok=False rather than hanging.
"""
from __future__ import annotations

import time

import pytest

from brainer_stem_tutor.solver import MockSolverLLM, SolverAgent
from brainer_stem_tutor.solver.mcp_tools._timeout import run_with_timeout
from brainer_stem_tutor.solver.mcp_tools.sympy_cas import (
    sympy_simplify,
    sympy_solve_equation,
    sympy_verify,
)


class TestComplexAndUnderspecifiedRoots:
    def test_complex_only_roots_failed_verification(self) -> None:
        agent = SolverAgent(MockSolverLLM())
        solved = agent.solve("Solve x**2 + 1 = 0 for x")
        # No real solutions: agent should not claim high confidence.
        assert solved.confidence <= 0.5
        # At least one verification should mention complex roots or failure.
        notes = " ".join(v.notes or "" for v in solved.verifications)
        assert "complex" in notes or "no real" in notes or any(
            not v.passed for v in solved.verifications
        )

    def test_under_specified_equation_failed_verification(self) -> None:
        agent = SolverAgent(MockSolverLLM())
        solved = agent.solve("Solve x**2 - y**2 = 0 for x")
        # Roots depend on y -> at least one verification must fail.
        assert any(not v.passed for v in solved.verifications)
        assert solved.confidence <= 0.5

    def test_quadratic_two_real_roots_still_succeeds(self) -> None:
        agent = SolverAgent(MockSolverLLM())
        solved = agent.solve("Solve x**2 - 4 = 0 for x")
        # Two real roots, both back-substitute to 0 -> high confidence.
        assert solved.confidence >= 0.9
        assert all(v.passed for v in solved.verifications)


class TestSympyTimeout:
    def test_simplify_within_budget(self) -> None:
        r = sympy_simplify("x**2 + 2*x + 1", timeout=1.0)
        assert r.ok

    def test_solve_within_budget(self) -> None:
        r = sympy_solve_equation("2*x - 6 = 0", "x", timeout=1.0)
        assert r.ok and "3" in r.output

    def test_verify_within_budget(self) -> None:
        r = sympy_verify("2+2", "4", timeout=1.0)
        assert r.ok

    def test_timeout_raises_then_caught(self) -> None:
        def slow():
            time.sleep(0.5)

        with pytest.raises(TimeoutError):
            run_with_timeout(slow, seconds=0.1)

    def test_sympy_simplify_timeout_returns_ok_false(self) -> None:
        # Force a synthetic timeout by using a microsecond budget. The exact
        # operation doesn't matter — we want the wrapper to surface the
        # timeout as ok=False, not raise out of the tool.
        r = sympy_simplify("(x + 1)**2 * sin(x)**3 / cos(x)", timeout=1e-9)
        assert not r.ok
        assert "timeout" in (r.notes or "")
