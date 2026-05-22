"""TutorAgent integration: policy + LLM + moderator wired together."""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.schemas import (
    ActionKind,
    BBox,
    SolvedProblem,
    Step,
    StudentSignals,
    TutorTurn,
    VerificationRecord,
    VisionElement,
    VisionResult,
)
from brainer_stem_tutor.tutor import MockTutorLLM, TutorAgent
from brainer_stem_tutor.vision.schemas_ext import VisionContext


@pytest.fixture
def solved() -> SolvedProblem:
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
            VerificationRecord(tool="unit_checker", input="i", output="o", passed=True),
        ],
        model_used="test",
    )


class TestTutorAgent:
    def test_default_path_confirm_and_advance(self, solved) -> None:
        agent = TutorAgent(MockTutorLLM())
        turn = agent.respond(
            solved,
            "I got step 1, now what?",
            StudentSignals(last_correct_step=1),
        )
        assert isinstance(turn, TutorTurn)
        # Confirm-and-advance template should not leak "10"
        assert "10" not in turn.student_facing_message
        assert "moderator_blocked" not in turn.internal_notes

    def test_quiz_action_emitted_for_concept_strategy(self, solved) -> None:
        agent = TutorAgent(MockTutorLLM())
        turn = agent.respond(
            solved,
            "I don't know which formula to use",
            StudentSignals(last_error_kind="concept"),
        )
        kinds = [a.kind for a in turn.actions]
        assert ActionKind.SHOW_QUIZ in kinds

    def test_highlight_attached_when_vision_mapping_exists(self, solved) -> None:
        vr = VisionResult(
            image_hash="img1",
            elements=[
                VisionElement(
                    id="bbox_0",
                    bbox=BBox(x=0.1, y=0.1, w=0.2, h=0.05),
                    text="v = at",
                    role="formula",
                    confidence=0.9,
                )
            ],
            page_width=100,
            page_height=100,
        )
        ctx = VisionContext(last_result=vr).with_mapping(2, ["bbox_0"])
        agent = TutorAgent(MockTutorLLM())
        turn = agent.respond(
            solved,
            "where am i?",
            StudentSignals(last_correct_step=1),
            vision=ctx,
        )
        hl = next(
            (a for a in turn.actions if a.kind == ActionKind.HIGHLIGHT_BBOXES), None
        )
        assert hl is not None
        assert hl.bbox_ids == ["bbox_0"]

    def test_moderator_blocks_leaky_llm(self, solved) -> None:
        class LeakyLLM:
            model_id = "leaky"

            def draft_turn(self, solved, msg, decision, vision=None):
                return TutorTurn(
                    student_facing_message="The velocity is 10 m/s.",
                    actions=[],
                    internal_notes="naive",
                )

        agent = TutorAgent(LeakyLLM())
        turn = agent.respond(
            solved,
            "tell me",
            StudentSignals(last_correct_step=2),
        )
        assert "10" not in turn.student_facing_message
        assert "moderator_blocked" in turn.internal_notes

    def test_frustrated_student_gets_pause_message(self, solved) -> None:
        agent = TutorAgent(MockTutorLLM())
        turn = agent.respond(
            solved,
            "i hate this",
            StudentSignals(frustration_score=0.9),
        )
        assert "break" in turn.student_facing_message.lower() or "pause" in turn.student_facing_message.lower()
