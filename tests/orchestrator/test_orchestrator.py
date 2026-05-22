"""End-to-end orchestrator tests with all real (non-LLM) layers wired."""
from __future__ import annotations

from brainer_stem_tutor.orchestrator import Orchestrator
from brainer_stem_tutor.shared.schemas import ActionKind
from brainer_stem_tutor.solver import MockSolverLLM, SolverAgent
from brainer_stem_tutor.tutor import MockTutorLLM, TutorAgent
from brainer_stem_tutor.vision import MockVisionLLM, VisionAgent, image_hash


def _build_orchestrator() -> Orchestrator:
    return Orchestrator(
        solver=SolverAgent(MockSolverLLM()),
        tutor=TutorAgent(MockTutorLLM()),
        vision=VisionAgent(MockVisionLLM()),
    )


class TestOrchestratorE2E:
    def test_problem_then_message_flow(self) -> None:
        orch = _build_orchestrator()
        r1 = orch.on_problem_statement(
            "s1",
            "An object accelerates at 2 m/s^2 starting from rest for 5 seconds. "
            "What is its velocity?",
        )
        assert r1.solved is not None
        assert r1.solved.final_answer_numeric == 10.0

        r2 = orch.on_student_message("s1", "what should I write first?")
        assert r2.tutor_turn is not None
        # Mock tutor's template must not leak "10"
        assert "10" not in r2.tutor_turn.student_facing_message

    def test_solved_required_before_tutoring(self) -> None:
        orch = _build_orchestrator()
        r = orch.on_student_message("s1", "help?")
        assert r.tutor_turn is None
        assert "no solved" in r.notes

    def test_image_update_attaches_vision_and_bbox_mapping(self) -> None:
        orch = _build_orchestrator()
        # First the problem
        orch.on_problem_statement(
            "s1",
            "An object accelerates at 2 m/s^2 starting from rest for 5 seconds. "
            "What is its velocity?",
        )
        # Then an image with two known formulas
        img = b"fake-image-bytes"
        # Reach into the mock vision LLM to register a fixture
        vision_llm: MockVisionLLM = orch._vision._llm  # type: ignore[attr-defined]
        vision_llm.register(
            img,
            "coarse",
            {
                "image_hash": image_hash(img),
                "elements": [
                    {
                        "id": "bbox_0",
                        "bbox": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.05},
                        "text": "v = a t",
                        "latex": "v = a \\cdot t",
                        "role": "formula",
                        "parent_id": None,
                        "confidence": 0.94,
                    }
                ],
                "page_width": 1000,
                "page_height": 800,
                "rotation": 0,
            },
        )
        orch.on_image_update("s1", img, step_keywords={2: ["v = a t"]})
        orch.mark_step_completed("s1", 1)  # tutor now targets step 2

        # Now a student message — the tutor should attach a highlight action
        r = orch.on_student_message("s1", "where are we?")
        assert r.tutor_turn is not None
        kinds = [a.kind for a in r.tutor_turn.actions]
        assert ActionKind.HIGHLIGHT_BBOXES in kinds

    def test_step_completion_resets_attempts(self) -> None:
        orch = _build_orchestrator()
        orch.on_problem_statement("s1", "What is 6*7?")
        orch.on_student_message("s1", "try 1")
        orch.on_student_message("s1", "try 2")
        state = orch._store.get("s1")  # type: ignore[attr-defined]
        assert state.attempts_count == 2
        orch.mark_step_completed("s1", 1)
        assert state.attempts_count == 0

    def test_error_tag_triggers_targeted_hint_strategy(self) -> None:
        orch = _build_orchestrator()
        orch.on_problem_statement(
            "s1",
            "An object accelerates at 1 m/s^2 starting from rest for 2 seconds. "
            "What is its velocity?",
        )
        orch.mark_error("s1", "unit")
        r = orch.on_student_message("s1", "I have v = 2")
        assert r.tutor_turn is not None
        # Targeted-hint message should mention units / dimensions
        msg = r.tutor_turn.student_facing_message.lower()
        assert "dimension" in msg or "unit" in msg
