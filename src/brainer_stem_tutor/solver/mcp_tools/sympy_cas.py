"""Symbolic CAS verifications backed by sympy.

These functions are MCP-tool-shaped (string in, string out, no side effects)
so a FastMCP wrapper can expose them as-is to the solver agent. Every sympy
call goes through `run_with_timeout` so a pathological problem can't hang
the agent.
"""
from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from ._timeout import run_with_timeout

DEFAULT_TIMEOUT_SECONDS = 3.0


@dataclass
class CASResult:
    """Lightweight return type so callers can branch on `ok` without parsing."""

    ok: bool
    output: str
    notes: str | None = None


def _safe_parse(expr: str) -> sp.Expr:
    """Parse a user expression in a restricted sympy context."""
    return sp.sympify(expr, evaluate=True)


def sympy_simplify(expr: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> CASResult:
    """Simplify an expression. Used by the solver to canonicalise its work."""
    try:
        e = _safe_parse(expr)
        s = run_with_timeout(sp.simplify, args=(e,), seconds=timeout)
        return CASResult(ok=True, output=str(s))
    except TimeoutError as exc:
        return CASResult(ok=False, output="", notes=f"simplify timeout: {exc}")
    except Exception as exc:
        return CASResult(ok=False, output="", notes=f"simplify failed: {exc}")


def sympy_solve_equation(
    equation: str,
    variable: str = "x",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CASResult:
    """Solve `lhs = rhs` (or expression-set-to-zero) for `variable`.

    Accepts either `x**2 - 4` (treated as = 0) or `x**2 = 4`.
    """
    try:
        if "=" in equation:
            lhs_str, rhs_str = equation.split("=", 1)
            lhs = _safe_parse(lhs_str)
            rhs = _safe_parse(rhs_str)
            eq = sp.Eq(lhs, rhs)
        else:
            eq = sp.Eq(_safe_parse(equation), 0)
        var = sp.symbols(variable)
        solutions = run_with_timeout(sp.solve, args=(eq, var), seconds=timeout)
        return CASResult(ok=True, output=str(solutions))
    except TimeoutError as exc:
        return CASResult(ok=False, output="", notes=f"solve timeout: {exc}")
    except Exception as exc:
        return CASResult(ok=False, output="", notes=f"solve failed: {exc}")


def sympy_verify(
    candidate_expr: str,
    target_expr: str,
    numerical_tolerance: float = 1e-9,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CASResult:
    """Decide whether `candidate_expr` and `target_expr` are equivalent.

    Tries algebraic equivalence first (simplify(c - t) == 0), then falls back
    to a numeric check at a few sample points for expressions involving free
    symbols.
    """
    try:
        c = _safe_parse(candidate_expr)
        t = _safe_parse(target_expr)
    except Exception as exc:
        return CASResult(ok=False, output="false", notes=f"parse error: {exc}")

    try:
        diff = run_with_timeout(sp.simplify, args=(c - t,), seconds=timeout)
    except TimeoutError as exc:
        return CASResult(ok=False, output="false", notes=f"simplify timeout: {exc}")
    except Exception as exc:
        return CASResult(ok=False, output="false", notes=f"simplify error: {exc}")

    if diff == 0:
        return CASResult(ok=True, output="true", notes="algebraically identical")

    free = sorted(diff.free_symbols, key=lambda s: s.name)
    if not free:
        try:
            num = float(diff.evalf())
            if abs(num) < numerical_tolerance:
                return CASResult(ok=True, output="true", notes=f"numeric diff={num:.2e}")
            return CASResult(ok=False, output="false", notes=f"numeric diff={num:.2e}")
        except Exception as exc:
            return CASResult(ok=False, output="false", notes=f"evalf error: {exc}")

    # Numeric sweep on free symbols.
    test_points = [0.5, 1.0, 1.5, 2.0, -1.0]
    try:
        for v in test_points:
            sub = {s: v for s in free}
            val = float(diff.evalf(subs=sub))
            if abs(val) > numerical_tolerance:
                return CASResult(
                    ok=False,
                    output="false",
                    notes=f"diff={val:.2e} at sub={sub}",
                )
        return CASResult(ok=True, output="true", notes="agrees on all sample points")
    except Exception as exc:
        return CASResult(ok=False, output="false", notes=f"numeric error: {exc}")
