"""Microbenchmark for the moderator review hot path.

Not a strict CI gate (host-dependent) but logs throughput so regressions
surface in code review. The check below — 200 reviews under 1 second on
any reasonable host — has plenty of headroom; a real perf regression
would take it from milliseconds to seconds.
"""
from __future__ import annotations

import time

from brainer_stem_tutor.shared.schemas import (
    SolvedProblem,
    Step,
    TutorTurn,
    VerificationRecord,
)
from brainer_stem_tutor.tutor.moderator import LeakModerator


def _solved() -> SolvedProblem:
    return SolvedProblem(
        problem_text="?",
        subject="math",
        steps=[
            Step(n=i, kind="setup" if i < 10 else "answer", latex=f"x_{i}=v_{i}", justification="g")
            for i in range(1, 11)
        ],
        final_answer="42",
        final_answer_numeric=42.0,
        units=None,
        confidence=0.9,
        verifications=[
            VerificationRecord(tool="python", input="i", output="o", passed=True)
        ],
        model_used="t",
    )


def test_moderator_throughput() -> None:
    mod = LeakModerator()
    solved = _solved()
    fps = LeakModerator.precompute_fingerprints(solved)
    msg = (
        "Consider the relationship between the symbols in the previous step. "
        "What concept connects them? Think about the units involved as well "
        "and whether your expression is dimensionally consistent."
    )
    turn = TutorTurn(student_facing_message=msg)

    n = 200
    start = time.perf_counter()
    for _ in range(n):
        mod.review(turn, solved, fingerprints=fps)
    elapsed = time.perf_counter() - start
    rate = n / elapsed
    print(f"\nmoderator: {n} reviews in {elapsed*1000:.1f}ms ({rate:.0f}/s)")
    assert elapsed < 1.0, f"moderator too slow: {elapsed:.2f}s for {n} reviews"


def test_precompute_fingerprints_cheap() -> None:
    solved = _solved()
    n = 1000
    start = time.perf_counter()
    for _ in range(n):
        LeakModerator.precompute_fingerprints(solved)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"fingerprint precompute too slow: {elapsed:.2f}s"
