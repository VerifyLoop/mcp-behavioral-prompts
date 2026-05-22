"""Solver and tutor metrics.

Solver:
- accuracy@1 (numeric within tolerance, falling back to string match)
- accuracy@1 with verification (correct AND all verifications passed)
- mean confidence
- confidence calibration via Brier score
- mean verifications per problem
- mean steps per problem

Tutor:
- leak_rate (fraction of turns where moderator would have triggered)
- hint_quality (1 - leak) * informativeness proxy
- average turns to first success
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ...shared.schemas import SolvedProblem, TutorTurn
from ..datasets import EvalProblem


@dataclass
class SolverEntry:
    problem: EvalProblem
    solved: SolvedProblem | None
    error: str | None = None


@dataclass
class SolverMetrics:
    n: int
    correct: int
    correct_with_verification: int
    mean_confidence: float
    mean_verifications: float
    mean_steps: float
    brier: float            # 0 best, 1 worst — calibration
    failure_count: int      # problems that errored or returned None

    @property
    def accuracy(self) -> float:
        return self.correct / self.n if self.n else 0.0

    @property
    def accuracy_with_verification(self) -> float:
        return self.correct_with_verification / self.n if self.n else 0.0


@dataclass
class TutorMetrics:
    n: int
    leak_count: int
    persona_breakdown: dict[str, int]   # leak count per persona
    mean_message_chars: float

    @property
    def leak_rate(self) -> float:
        return self.leak_count / self.n if self.n else 0.0


def _numeric_match(expected: float | None, actual: float | None, tol: float) -> bool:
    if expected is None or actual is None:
        return False
    if expected == 0:
        return abs(actual) <= tol
    return abs(actual - expected) <= tol * max(1.0, abs(expected))


def _string_match(expected: str, actual: str) -> bool:
    return expected.strip().lower() == actual.strip().lower()


def is_correct(
    problem: EvalProblem,
    solved: SolvedProblem,
    numeric_tol: float = 1e-3,
) -> bool:
    if _numeric_match(problem.expected_numeric, solved.final_answer_numeric, numeric_tol):
        return True
    return _string_match(problem.expected_answer, solved.final_answer)


def brier_score(pairs: Iterable[tuple[float, bool]]) -> float:
    """Brier score for binary outcomes.

    pairs: iterable of (predicted_probability, ground_truth_bool).
    Returns mean squared error between probability and outcome.
    """
    items = list(pairs)
    if not items:
        return 0.0
    return sum((p - (1.0 if t else 0.0)) ** 2 for p, t in items) / len(items)


def compute_solver_metrics(
    entries: Iterable[SolverEntry],
    numeric_tol: float = 1e-3,
) -> SolverMetrics:
    items = list(entries)
    n = len(items)
    correct = 0
    correct_verified = 0
    confidences = []
    verifications_counts = []
    steps_counts = []
    failures = 0
    brier_pairs: list[tuple[float, bool]] = []

    for e in items:
        if e.error is not None or e.solved is None:
            failures += 1
            brier_pairs.append((0.0, False))
            continue
        ok = is_correct(e.problem, e.solved, numeric_tol)
        if ok:
            correct += 1
        all_verified = bool(e.solved.verifications) and all(
            v.passed for v in e.solved.verifications
        )
        if ok and all_verified:
            correct_verified += 1
        confidences.append(e.solved.confidence)
        verifications_counts.append(len(e.solved.verifications))
        steps_counts.append(len(e.solved.steps))
        brier_pairs.append((e.solved.confidence, ok))

    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0  # noqa: E731
    return SolverMetrics(
        n=n,
        correct=correct,
        correct_with_verification=correct_verified,
        mean_confidence=mean(confidences),
        mean_verifications=mean(verifications_counts),
        mean_steps=mean(steps_counts),
        brier=brier_score(brier_pairs),
        failure_count=failures,
    )


# -- tutor metrics --


@dataclass
class TutorEntry:
    persona: str
    turn: TutorTurn
    leaked: bool


def compute_tutor_metrics(entries: Iterable[TutorEntry]) -> TutorMetrics:
    items = list(entries)
    n = len(items)
    leak = sum(1 for e in items if e.leaked)
    by_persona: dict[str, int] = {}
    for e in items:
        if e.leaked:
            by_persona[e.persona] = by_persona.get(e.persona, 0) + 1
    chars = [len(e.turn.student_facing_message) for e in items]
    return TutorMetrics(
        n=n,
        leak_count=leak,
        persona_breakdown=by_persona,
        mean_message_chars=sum(chars) / len(chars) if chars else 0.0,
    )
