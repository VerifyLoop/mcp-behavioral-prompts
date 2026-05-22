"""Metrics: accuracy + brier + tutor leak counting."""
from __future__ import annotations

import math

import pytest

from brainer_stem_tutor.eval.datasets import EvalProblem
from brainer_stem_tutor.eval.metrics.accuracy import (
    SolverEntry,
    TutorEntry,
    brier_score,
    compute_solver_metrics,
    compute_tutor_metrics,
    is_correct,
)
from brainer_stem_tutor.shared.schemas import (
    SolvedProblem,
    Step,
    TutorTurn,
    VerificationRecord,
)


def _problem(numeric: float = 42.0, answer: str | None = None) -> EvalProblem:
    return EvalProblem(
        id="p",
        subject="math",
        problem_text="?",
        expected_answer=answer if answer is not None else str(numeric),
        expected_numeric=numeric,
    )


def _solved(numeric: float | None = 42.0, answer: str | None = None, conf: float = 0.95) -> SolvedProblem:
    if answer is None:
        answer = str(numeric) if numeric is not None else "?"
    return SolvedProblem(
        problem_text="?",
        subject="math",
        steps=[
            Step(n=1, kind="setup", latex="?", justification="g"),
            Step(n=2, kind="answer", latex=answer, justification="g"),
        ],
        final_answer=answer,
        final_answer_numeric=numeric,
        units=None,
        confidence=conf,
        verifications=[
            VerificationRecord(tool="sympy_cas", input="i", output="o", passed=True)
        ],
        model_used="t",
    )


class TestIsCorrect:
    def test_numeric_exact(self) -> None:
        assert is_correct(_problem(42.0), _solved(42.0))

    def test_numeric_close_under_tolerance(self) -> None:
        assert is_correct(_problem(1.0), _solved(1.0001), numeric_tol=1e-3)

    def test_numeric_off(self) -> None:
        assert not is_correct(_problem(1.0), _solved(2.0))

    def test_string_fallback(self) -> None:
        p = EvalProblem(id="p", subject="math", problem_text="?", expected_answer="[1, 2]")
        s = _solved(numeric=None, answer="[1, 2]")
        assert is_correct(p, s)


class TestBrierScore:
    def test_empty(self) -> None:
        assert brier_score([]) == 0.0

    def test_perfect_calibration(self) -> None:
        assert brier_score([(1.0, True), (0.0, False)]) == 0.0

    def test_worst_calibration(self) -> None:
        assert brier_score([(0.0, True), (1.0, False)]) == 1.0

    def test_uncertain_calibration(self) -> None:
        # 50% confidence with mixed outcomes -> 0.25
        s = brier_score([(0.5, True), (0.5, False)])
        assert math.isclose(s, 0.25)


class TestSolverMetrics:
    def test_all_correct_high_confidence(self) -> None:
        entries = [SolverEntry(problem=_problem(42.0), solved=_solved(42.0))]
        m = compute_solver_metrics(entries)
        assert m.accuracy == 1.0
        assert m.accuracy_with_verification == 1.0
        assert m.mean_confidence == 0.95
        assert m.failure_count == 0
        assert m.mean_verifications == 1.0

    def test_failure_handling(self) -> None:
        entries = [
            SolverEntry(problem=_problem(42.0), solved=None, error="boom"),
            SolverEntry(problem=_problem(42.0), solved=_solved(42.0)),
        ]
        m = compute_solver_metrics(entries)
        assert m.n == 2
        assert m.correct == 1
        assert m.failure_count == 1


class TestTutorMetrics:
    def test_no_leaks(self) -> None:
        entries = [
            TutorEntry(persona="diligent", turn=TutorTurn(student_facing_message="ok"), leaked=False)
        ]
        m = compute_tutor_metrics(entries)
        assert m.leak_count == 0
        assert m.leak_rate == 0.0

    def test_persona_breakdown(self) -> None:
        entries = [
            TutorEntry("diligent", TutorTurn(student_facing_message="a"), False),
            TutorEntry("extractor", TutorTurn(student_facing_message="b"), True),
            TutorEntry("extractor", TutorTurn(student_facing_message="c"), True),
        ]
        m = compute_tutor_metrics(entries)
        assert m.persona_breakdown == {"extractor": 2}
        assert m.leak_rate == pytest.approx(2 / 3)
