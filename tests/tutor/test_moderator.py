"""Anti-leak moderator: this is the safety net the whole product depends on."""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.schemas import (
    SolvedProblem,
    Step,
    TutorTurn,
    VerificationRecord,
)
from brainer_stem_tutor.shared.settings import TutorSettings
from brainer_stem_tutor.tutor.moderator import LeakModerator


@pytest.fixture
def solved_kinematic() -> SolvedProblem:
    return SolvedProblem(
        problem_text="acc 2 m/s^2 for 5s, velocity?",
        subject="physics",
        steps=[
            Step(n=1, kind="setup", latex="a=2, t=5", justification="given"),
            Step(n=2, kind="concept", latex="v = a t", justification="kinematics"),
            Step(n=3, kind="computation", latex="v = 2 * 5 = 10", justification="multiply"),
            Step(n=4, kind="answer", latex="10 m/s", justification="final"),
        ],
        final_answer="10",
        final_answer_numeric=10.0,
        units="m/s",
        confidence=0.99,
        verifications=[
            VerificationRecord(
                tool="unit_checker",
                input="m/s^2*s",
                output="m/s",
                passed=True,
            )
        ],
        model_used="test",
    )


@pytest.fixture
def moderator() -> LeakModerator:
    return LeakModerator(TutorSettings(MODERATOR_MAX_CONSECUTIVE_STEPS=2))


class TestNumericLeak:
    def test_exact_numeric_leak_blocks(self, moderator, solved_kinematic) -> None:
        turn = TutorTurn(student_facing_message="The velocity is 10 m/s.", actions=[])
        report = moderator.review(turn, solved_kinematic)
        assert report.leaked
        assert any("numeric" in r for r in report.reasons)
        assert report.redacted_message is not None

    def test_tolerated_close_numeric_blocks(self, moderator, solved_kinematic) -> None:
        # 10.0005 with default 1e-3 tolerance should still be flagged
        turn = TutorTurn(student_facing_message="Should be around 10.0005.", actions=[])
        report = moderator.review(turn, solved_kinematic)
        assert report.leaked

    def test_unrelated_number_allowed(self, moderator, solved_kinematic) -> None:
        turn = TutorTurn(
            student_facing_message="Consider step 2 — what concept applies?", actions=[]
        )
        report = moderator.review(turn, solved_kinematic)
        # "2" appears but is far from 10 -> not a leak
        assert not report.leaked

    def test_when_final_numeric_is_none_skip_numeric_check(self, moderator) -> None:
        sp = SolvedProblem(
            problem_text="solve x^2 - 4",
            subject="math",
            steps=[
                Step(n=1, kind="setup", latex="x**2 - 4", justification="g"),
                Step(n=2, kind="answer", latex="[-2, 2]", justification="g"),
            ],
            final_answer="[-2, 2]",
            final_answer_numeric=None,
            units=None,
            confidence=0.99,
            verifications=[
                VerificationRecord(tool="sympy_cas", input="x", output="true", passed=True)
            ],
            model_used="t",
        )
        turn = TutorTurn(
            student_facing_message="Think about factoring the quadratic.", actions=[]
        )
        assert not moderator.review(turn, sp).leaked


class TestStringLeak:
    def test_string_final_answer_leak(self, moderator) -> None:
        sp = SolvedProblem(
            problem_text="Q",
            subject="math",
            steps=[
                Step(n=1, kind="setup", latex="?", justification="g"),
                Step(n=2, kind="answer", latex="x = (b - sqrt(b^2-4ac))/2a", justification="g"),
            ],
            final_answer="x = (b - sqrt(b^2-4ac))/2a",
            final_answer_numeric=None,
            units=None,
            confidence=0.9,
            verifications=[
                VerificationRecord(tool="sympy_cas", input="i", output="o", passed=True)
            ],
            model_used="t",
        )
        turn = TutorTurn(
            student_facing_message="The answer is x = (b - sqrt(b^2-4ac))/2a, see?",
            actions=[],
        )
        assert moderator.review(turn, sp).leaked


class TestStepCopyLeak:
    def test_blocks_more_than_two_consecutive_steps(
        self, moderator, solved_kinematic
    ) -> None:
        turn = TutorTurn(
            student_facing_message=(
                "Just follow: a=2, t=5, then v = a t, and v = 2 * 5 = 10."
            ),
            actions=[],
        )
        report = moderator.review(turn, solved_kinematic)
        assert report.leaked
        assert any("consecutive" in r for r in report.reasons)

    def test_two_steps_allowed(self, moderator, solved_kinematic) -> None:
        # Quote step 1 then skip — under the limit
        turn = TutorTurn(
            student_facing_message="Start from a=2, t=5 and recall v = a t — now what?",
            actions=[],
        )
        report = moderator.review(turn, solved_kinematic)
        # Even though it touches steps 1 and 2 consecutively (=2), the limit
        # is "more than 2" — exactly 2 must be allowed.
        assert not report.leaked


class TestRedaction:
    def test_redacted_message_does_not_contain_answer(
        self, moderator, solved_kinematic
    ) -> None:
        turn = TutorTurn(student_facing_message="The velocity is 10 m/s.", actions=[])
        report = moderator.review(turn, solved_kinematic)
        assert report.leaked
        assert "10" not in report.redacted_message
        assert "step" in report.redacted_message.lower()
