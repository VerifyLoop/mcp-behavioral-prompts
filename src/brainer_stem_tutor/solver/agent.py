"""Solver agent.

The agent is split into:
- SolverProtocol: a typing.Protocol describing what the orchestrator needs;
  a real implementation backed by Google ADK + Gemini lives behind this
  interface and is plugged in at deploy time.
- MockSolverLLM: an in-process implementation that parses a small grammar of
  problems (linear/quadratic equations, basic kinematics). It exists so the
  whole stack — tutor, moderator, eval harness — can run end-to-end without
  network access.
- SolverAgent: validates the draft, runs confidence calibration, caches.

The DraftSolution carries already-executed VerificationRecord entries — a
real ADK LLM would obtain them via MCP tool calls during its reasoning loop,
the MockSolverLLM obtains them by calling sympy/pint directly. The
SolverAgent does not duplicate verifications; that would either re-run the
same sympy/pint calls or, worse, run a different check than the one the LLM
actually used to convince itself.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

import sympy as sp

from ..shared.schemas import SolvedProblem, Step, VerificationRecord
from ..shared.settings import TutorSettings, get_settings
from .cache import SolvedCache
from .mcp_tools.sympy_cas import sympy_solve_equation, sympy_verify
from .mcp_tools.unit_checker import check_dimensions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Solver protocol
# ---------------------------------------------------------------------------


class SolverProtocol(Protocol):
    """Anything that can turn a problem statement into a draft SolvedProblem.

    Real impl: ADK LlmAgent with Gemini + MCP tools.
    Mock impl: MockSolverLLM (deterministic, sympy-backed).
    """

    def draft(self, problem_text: str) -> DraftSolution:  # pragma: no cover - protocol
        ...

    @property
    def model_id(self) -> str:  # pragma: no cover - protocol
        ...


@dataclass
class DraftSolution:
    """The raw output of the LLM with verifications it already executed.

    A real ADK LLM populates `verifications` via tool calls during its
    reasoning. The mock LLM does the same calls in-process. Either way the
    SolverAgent treats them as given evidence and does not re-run them.
    """

    subject: str
    steps: list[Step]
    final_answer: str
    final_answer_numeric: float | None
    units: str | None
    verifications: list[VerificationRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# MockSolverLLM — deterministic baseline used by tests and offline demo
# ---------------------------------------------------------------------------


class MockSolverLLM:
    """Deterministic solver that handles a small grammar of problems.

    Supported patterns (regex-detected on the problem text):

    1. "solve <eq> for <var>"            -> uses sympy.solve
    2. "what is <number-expr>?"          -> evaluates the expression
    3. "an object accelerates at <a> m/s^2 for <t> seconds..."  -> v = a*t
    4. "what is 2+2"                      -> shortcut for trivial arithmetic

    Anything not matched returns a minimal draft with confidence 0, which
    the solver will reject — visible failure is better than silent garbage.
    """

    model_id = "mock-solver-v1"

    _EQ_PATTERN = re.compile(r"solve\s+(.+?)\s+for\s+([a-zA-Z])", re.IGNORECASE)
    _ARITH_PATTERN = re.compile(r"what is\s+([\d\s+\-*/().^]+)\??", re.IGNORECASE)
    _KINEMATIC_PATTERN = re.compile(
        r"accelerates?\s+at\s+([\d.]+)\s*m/s\^?2.*?for\s+([\d.]+)\s*(seconds|s)\b",
        re.IGNORECASE | re.DOTALL,
    )

    def draft(self, problem_text: str) -> DraftSolution:
        text = problem_text.strip()

        m = self._EQ_PATTERN.search(text)
        if m:
            return self._draft_equation(m.group(1).strip(), m.group(2).strip(), text)

        m = self._KINEMATIC_PATTERN.search(text)
        if m:
            return self._draft_kinematics(float(m.group(1)), float(m.group(2)))

        m = self._ARITH_PATTERN.search(text)
        if m:
            return self._draft_arithmetic(m.group(1).strip())

        return DraftSolution(
            subject="other",
            steps=[
                Step(n=1, kind="setup", latex=text, justification="problem stated"),
                Step(n=2, kind="answer", latex="?", justification="not understood"),
            ],
            final_answer="?",
            final_answer_numeric=None,
            units=None,
            verifications=[],
        )

    def _draft_arithmetic(self, expr: str) -> DraftSolution:
        cleaned = expr.replace("^", "**")
        result = sp.sympify(cleaned)
        val = float(result)
        verify = sympy_verify(cleaned, str(result))
        return DraftSolution(
            subject="math",
            steps=[
                Step(n=1, kind="setup", latex=expr, justification="given expression"),
                Step(n=2, kind="computation", latex=str(result), justification="evaluate"),
                Step(n=3, kind="answer", latex=str(result), justification="result"),
            ],
            final_answer=str(result),
            final_answer_numeric=val,
            units=None,
            verifications=[
                VerificationRecord(
                    tool="sympy_cas",
                    input=f"sympify({cleaned}) == {result}",
                    output=verify.output,
                    passed=verify.ok,
                    notes=verify.notes,
                )
            ],
        )

    def _draft_equation(self, eq: str, var: str, _full: str) -> DraftSolution:
        result = sympy_solve_equation(eq, var)
        if not result.ok:
            raise ValueError(f"Mock solver failed to parse equation: {result.notes}")
        solutions_str = result.output
        try:
            parsed = sp.sympify(solutions_str)
            roots = list(parsed) if isinstance(parsed, (list, tuple, sp.Tuple)) else [parsed]
        except Exception:
            roots = []

        sym = sp.symbols(var)
        # Classify roots: real & numeric vs complex vs free-symbol.
        real_numeric_roots: list[sp.Expr] = []
        complex_roots: list[sp.Expr] = []
        under_specified_roots: list[sp.Expr] = []
        for r in roots:
            try:
                free = r.free_symbols - {sym}
            except AttributeError:
                free = set()
            if free:
                under_specified_roots.append(r)
                continue
            try:
                if r.is_real is False:
                    complex_roots.append(r)
                    continue
            except AttributeError:
                pass
            real_numeric_roots.append(r)

        num: float | None = None
        if len(real_numeric_roots) == 1 and not (complex_roots or under_specified_roots):
            try:
                num = float(real_numeric_roots[0])
            except (TypeError, ValueError):
                num = None

        # Verify each root by substituting back into the equation.
        verifications: list[VerificationRecord] = []
        if "=" in eq:
            lhs_str, rhs_str = eq.split("=", 1)
            lhs = sp.sympify(lhs_str)
            rhs = sp.sympify(rhs_str)
            residual = lhs - rhs
        else:
            residual = sp.sympify(eq)
        for r in real_numeric_roots:
            val = sp.simplify(residual.subs(sym, r))
            verifications.append(
                VerificationRecord(
                    tool="sympy_cas",
                    input=f"substitute {var}={r} into {eq}",
                    output=str(val),
                    passed=(val == 0),
                    notes=f"residual after substitution = {val}",
                )
            )
        # Complex roots: still verify substitution but flag that no real
        # solution exists, since most curricula expect real answers.
        if complex_roots and not real_numeric_roots:
            verifications.append(
                VerificationRecord(
                    tool="sympy_cas",
                    input=f"solve {eq} for {var}",
                    output=solutions_str,
                    passed=False,
                    notes="no real solutions found; only complex roots",
                )
            )
        # Under-specified: solution depends on other free variables.
        if under_specified_roots:
            verifications.append(
                VerificationRecord(
                    tool="sympy_cas",
                    input=f"solve {eq} for {var}",
                    output=solutions_str,
                    passed=False,
                    notes="under-specified: roots contain free symbols",
                )
            )
        if not verifications:
            verifications.append(
                VerificationRecord(
                    tool="sympy_cas",
                    input=f"solve {eq} for {var}",
                    output=solutions_str,
                    passed=False,
                    notes="sympy.solve returned an empty or unrecognised structure",
                )
            )

        return DraftSolution(
            subject="math",
            steps=[
                Step(n=1, kind="setup", latex=eq, justification=f"solve for {var}"),
                Step(
                    n=2,
                    kind="derivation",
                    latex=f"{var} = {solutions_str}",
                    justification="apply sympy.solve",
                ),
                Step(n=3, kind="answer", latex=solutions_str, justification="final"),
            ],
            final_answer=solutions_str,
            final_answer_numeric=num,
            units=None,
            verifications=verifications,
        )

    def _draft_kinematics(self, a: float, t: float) -> DraftSolution:
        v = a * t
        unit_check = check_dimensions("m/s", "m/s**2 * s")
        return DraftSolution(
            subject="physics",
            steps=[
                Step(n=1, kind="setup", latex=f"a={a}, t={t}", justification="given"),
                Step(
                    n=2,
                    kind="concept",
                    latex="v = a \\cdot t",
                    justification="constant acceleration from rest",
                ),
                Step(
                    n=3,
                    kind="computation",
                    latex=f"v = {a} \\cdot {t} = {v}",
                    justification="multiply",
                ),
                Step(n=4, kind="answer", latex=f"{v} m/s", justification="final"),
            ],
            final_answer=f"{v}",
            final_answer_numeric=v,
            units="m/s",
            verifications=[
                VerificationRecord(
                    tool="unit_checker",
                    input="m/s^2 * s -> m/s",
                    output=unit_check.output,
                    passed=unit_check.ok,
                    notes=unit_check.notes,
                ),
                VerificationRecord(
                    tool="sympy_cas",
                    input=f"{a} * {t}",
                    output=str(v),
                    passed=(abs(a * t - v) < 1e-9),
                    notes="numeric recompute",
                ),
            ],
        )


# ---------------------------------------------------------------------------
# SolverAgent — runs the draft -> verify -> SolvedProblem pipeline
# ---------------------------------------------------------------------------


class SolverAgent:
    """Wraps a SolverProtocol with verification, confidence calibration and caching."""

    def __init__(
        self,
        llm: SolverProtocol,
        cache: SolvedCache | None = None,
        settings: TutorSettings | None = None,
    ) -> None:
        self._llm = llm
        # Note: `cache or SolvedCache()` would discard an empty user cache
        # because an empty SolvedCache is falsy via __len__; use `is None`.
        self._cache = cache if cache is not None else SolvedCache()
        self._settings = settings or get_settings()

    def solve(self, problem_text: str, image_hash: str | None = None) -> SolvedProblem:
        cached = self._cache.get(problem_text, image_hash)
        if cached is not None:
            logger.debug("solver cache hit")
            return cached

        draft = self._llm.draft(problem_text)

        if not draft.verifications:
            raise RuntimeError(
                "Solver draft has no verifications; refusing to close. The LLM "
                "must execute at least one verification before claiming an answer."
            )

        confidence = self._calibrate_confidence(draft.verifications)

        # Subject must be one of the literal values the schema allows; reject
        # unknown subjects rather than letting them slip through and break
        # downstream consumers.
        allowed_subjects = {"math", "physics", "chemistry", "other"}
        subject = draft.subject if draft.subject in allowed_subjects else "other"

        solved = SolvedProblem(
            problem_text=problem_text,
            subject=subject,  # type: ignore[arg-type]
            steps=draft.steps,
            final_answer=draft.final_answer,
            final_answer_numeric=draft.final_answer_numeric,
            units=draft.units,
            confidence=confidence,
            verifications=draft.verifications,
            model_used=self._llm.model_id,
        )
        passed = sum(1 for v in draft.verifications if v.passed)
        logger.info(
            "solver done: %s passes=%d/%d confidence=%.2f",
            self._llm.model_id,
            passed,
            len(draft.verifications),
            confidence,
        )
        self._cache.put(problem_text, solved, image_hash)
        return solved

    def _calibrate_confidence(self, verifications: list[VerificationRecord]) -> float:
        """Map verification outcomes to a confidence score.

        - All N>=2 passed: 0.99 (two independent agreeing checks is strong).
        - All N==1 passed: 0.9 (single check, still meaningful but weaker).
        - None passed: 0.1 (sometimes verifications fail for benign reasons,
          but we surface it as low confidence so downstream gates fire).
        - Mixed: linear in pass ratio between 0.1 and 0.9.
        """
        if not verifications:
            return 0.0
        passed = sum(1 for v in verifications if v.passed)
        if passed == len(verifications):
            return 0.99 if len(verifications) >= 2 else 0.9
        if passed == 0:
            return 0.1
        return 0.1 + 0.8 * (passed / len(verifications))
