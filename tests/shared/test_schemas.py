"""Schema-level invariants. These contracts hold the whole system together."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from brainer_stem_tutor.shared import (
    BBox,
    SolvedProblem,
    Step,
    TutorAction,
    VerificationRecord,
    VisionElement,
    VisionResult,
)
from brainer_stem_tutor.shared.schemas import ActionKind


def make_solved(**overrides) -> SolvedProblem:
    defaults = dict(
        problem_text="What is 2+2?",
        subject="math",
        steps=[
            Step(n=1, kind="setup", latex="2+2", justification="given"),
            Step(n=2, kind="answer", latex="4", justification="sum"),
        ],
        final_answer="4",
        final_answer_numeric=4.0,
        units=None,
        confidence=0.99,
        verifications=[
            VerificationRecord(tool="python", input="2+2", output="4", passed=True)
        ],
        model_used="test-model",
    )
    defaults.update(overrides)
    return SolvedProblem(**defaults)


class TestSolvedProblem:
    def test_round_trip(self) -> None:
        sp = make_solved()
        clone = SolvedProblem.model_validate(sp.model_dump())
        assert clone == sp

    def test_requires_verification(self) -> None:
        with pytest.raises(ValidationError, match="VerificationRecord"):
            make_solved(verifications=[])

    def test_steps_must_be_sequential(self) -> None:
        with pytest.raises(ValidationError, match="sequential"):
            make_solved(
                steps=[
                    Step(n=1, kind="setup", latex="x", justification="g"),
                    Step(n=3, kind="answer", latex="y", justification="g"),
                ]
            )

    def test_last_step_must_be_answer(self) -> None:
        with pytest.raises(ValidationError, match="answer"):
            make_solved(
                steps=[
                    Step(n=1, kind="setup", latex="x", justification="g"),
                    Step(n=2, kind="derivation", latex="y", justification="g"),
                ]
            )

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            make_solved(confidence=1.5)
        with pytest.raises(ValidationError):
            make_solved(confidence=-0.1)


class TestBBox:
    def test_valid(self) -> None:
        BBox(x=0.1, y=0.1, w=0.5, h=0.5)

    def test_overflow_x(self) -> None:
        with pytest.raises(ValidationError, match="unit square"):
            BBox(x=0.6, y=0.1, w=0.5, h=0.1)

    def test_overflow_y(self) -> None:
        with pytest.raises(ValidationError, match="unit square"):
            BBox(x=0.1, y=0.6, w=0.1, h=0.5)

    def test_negative_w(self) -> None:
        with pytest.raises(ValidationError):
            BBox(x=0.1, y=0.1, w=-0.1, h=0.1)


class TestVisionResult:
    def _el(self, eid: str, parent: str | None = None) -> VisionElement:
        return VisionElement(
            id=eid,
            bbox=BBox(x=0.0, y=0.0, w=0.1, h=0.1),
            text="x",
            role="formula",
            parent_id=parent,
            confidence=0.9,
        )

    def test_unique_ids(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            VisionResult(
                image_hash="abc",
                elements=[self._el("a"), self._el("a")],
                page_width=10,
                page_height=10,
            )

    def test_parent_must_exist(self) -> None:
        with pytest.raises(ValidationError, match="parent_id"):
            VisionResult(
                image_hash="abc",
                elements=[self._el("a", parent="ghost")],
                page_width=10,
                page_height=10,
            )

    def test_lookup_by_id(self) -> None:
        vr = VisionResult(
            image_hash="abc",
            elements=[self._el("a"), self._el("b", parent="a")],
            page_width=10,
            page_height=10,
        )
        assert vr.by_id("b").parent_id == "a"
        assert vr.by_id("ghost") is None


class TestTutorAction:
    def test_ask_question_requires_text(self) -> None:
        with pytest.raises(ValidationError, match="text"):
            TutorAction(kind=ActionKind.ASK_QUESTION)

    def test_highlight_requires_ids(self) -> None:
        with pytest.raises(ValidationError, match="bbox"):
            TutorAction(kind=ActionKind.HIGHLIGHT_BBOXES, bbox_ids=[])

    def test_quiz_validation(self) -> None:
        with pytest.raises(ValidationError):
            TutorAction(
                kind=ActionKind.SHOW_QUIZ, text="q?", choices=["a"], correct_idx=0
            )
        with pytest.raises(ValidationError, match="range"):
            TutorAction(
                kind=ActionKind.SHOW_QUIZ,
                text="q?",
                choices=["a", "b"],
                correct_idx=5,
            )

    def test_confirm_step_requires_n(self) -> None:
        with pytest.raises(ValidationError, match="step_n"):
            TutorAction(kind=ActionKind.CONFIRM_STEP)

    def test_valid_actions_round_trip(self) -> None:
        for action in [
            TutorAction(kind=ActionKind.ASK_QUESTION, text="why?"),
            TutorAction(kind=ActionKind.HIGHLIGHT_BBOXES, bbox_ids=["bbox_0"]),
            TutorAction(kind=ActionKind.REQUEST_DRAWING, text="draw the FBD"),
            TutorAction(
                kind=ActionKind.SHOW_QUIZ,
                text="units?",
                choices=["m/s", "m/s^2"],
                correct_idx=1,
            ),
            TutorAction(kind=ActionKind.SHOW_DIAGRAM, diagram_url="/d/1.png"),
            TutorAction(kind=ActionKind.CONFIRM_STEP, step_n=3),
        ]:
            assert TutorAction.model_validate(action.model_dump()) == action
