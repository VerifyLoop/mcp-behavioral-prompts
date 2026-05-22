"""Hint quality judges: heuristic and LLM-stub."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from brainer_stem_tutor.eval.judge import HeuristicHintJudge, LLMHintJudge
from brainer_stem_tutor.shared.schemas import (
    SolvedProblem,
    Step,
    TutorTurn,
    VerificationRecord,
)


@pytest.fixture
def solved() -> SolvedProblem:
    return SolvedProblem(
        problem_text="What is 6*7?",
        subject="math",
        steps=[
            Step(n=1, kind="setup", latex="6*7", justification="g"),
            Step(n=2, kind="answer", latex="42", justification="g"),
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


class TestHeuristicHintJudge:
    def test_good_socratic_hint_scores_high(self, solved) -> None:
        turn = TutorTurn(
            student_facing_message=(
                "Think about the relationship in step 1. What rule connects "
                "the two numbers in your setup?"
            )
        )
        r = HeuristicHintJudge().score(turn, solved, "how do I start?")
        assert r.actionability >= 0.6
        assert r.composite > 0.5

    def test_too_short_loses_brevity(self, solved) -> None:
        turn = TutorTurn(student_facing_message="Try.")
        r = HeuristicHintJudge().score(turn, solved, "ok")
        assert r.brevity < 0.5

    def test_too_long_loses_brevity(self, solved) -> None:
        turn = TutorTurn(student_facing_message="x" * 1500)
        r = HeuristicHintJudge().score(turn, solved, "ok")
        assert r.brevity < 0.5

    def test_empty_message_actionability_zero(self, solved) -> None:
        turn = TutorTurn(student_facing_message=" ")
        r = HeuristicHintJudge().score(turn, solved, "?")
        assert r.actionability == 0.0


class TestLLMHintJudge:
    def test_uses_client_and_composes_score(self, solved) -> None:
        @dataclass
        class FakeClient:
            response: dict
            calls: int = 0

            def generate_json(self, *, model, system, user, response_schema=None):
                self.calls += 1
                return self.response

        client = FakeClient(
            response={"actionability": 0.8, "brevity": 1.0, "language_match": 0.5}
        )
        judge = LLMHintJudge(client=client)
        r = judge.score(
            TutorTurn(student_facing_message="What relationship governs step 1?"),
            solved,
            "where do I start?",
        )
        assert client.calls == 1
        # composite = 0.5*0.8 + 0.3*1.0 + 0.2*0.5 = 0.4 + 0.3 + 0.1 = 0.8
        assert abs(r.composite - 0.8) < 1e-6

    def test_missing_fields_default_zero(self, solved) -> None:
        class C:
            def generate_json(self, *, model, system, user, response_schema=None):
                return {}

        r = LLMHintJudge(client=C()).score(
            TutorTurn(student_facing_message="x"), solved, "?"
        )
        assert r.composite == 0.0
