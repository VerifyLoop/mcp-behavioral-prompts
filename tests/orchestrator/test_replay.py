"""Replay system: re-score historical tutor turns against the current moderator."""
from __future__ import annotations

from brainer_stem_tutor.orchestrator.replay import SessionSnapshot, replay_session
from brainer_stem_tutor.shared.schemas import (
    SolvedProblem,
    Step,
    StudentTurn,
    TutorTurn,
    VerificationRecord,
)


def _solved() -> SolvedProblem:
    return SolvedProblem(
        problem_text="?",
        subject="math",
        steps=[
            Step(n=1, kind="setup", latex="x=10", justification="g"),
            Step(n=2, kind="answer", latex="10", justification="g"),
        ],
        final_answer="10",
        final_answer_numeric=10.0,
        units=None,
        confidence=0.9,
        verifications=[
            VerificationRecord(tool="python", input="i", output="o", passed=True)
        ],
        model_used="t",
    )


class TestReplay:
    def test_clean_session_zero_leaks(self) -> None:
        snap = SessionSnapshot(
            session_id="s1",
            solved=_solved(),
            student_turns=[StudentTurn(text="help?", ts=0)],
            tutor_turns=[
                TutorTurn(student_facing_message="Think about the relationship."),
                TutorTurn(student_facing_message="What does step 1 imply?"),
            ],
        )
        result = replay_session(snap)
        assert result.total == 2
        assert result.leaked == 0
        assert result.leak_rate == 0.0

    def test_detects_historical_leak(self) -> None:
        snap = SessionSnapshot(
            session_id="s2",
            solved=_solved(),
            student_turns=[StudentTurn(text="give up", ts=0)],
            tutor_turns=[
                TutorTurn(student_facing_message="The answer is 10."),
                TutorTurn(student_facing_message="Now solve the next problem."),
            ],
        )
        result = replay_session(snap)
        assert result.leaked == 1
        assert result.leak_rate == 0.5

    def test_no_solved_returns_empty(self) -> None:
        snap = SessionSnapshot(
            session_id="s3", solved=None, student_turns=[], tutor_turns=[]
        )
        result = replay_session(snap)
        assert result.total == 0
        assert result.leaked == 0

    def test_round_trip_through_json(self) -> None:
        snap = SessionSnapshot(
            session_id="s4",
            solved=_solved(),
            student_turns=[],
            tutor_turns=[TutorTurn(student_facing_message="x")],
        )
        data = snap.model_dump_json()
        loaded = SessionSnapshot.model_validate_json(data)
        assert loaded.session_id == snap.session_id
        assert loaded.solved.final_answer_numeric == 10.0
