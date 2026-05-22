"""Gemini adapter unit tests with a fake client.

The adapters never import `google-genai`; they accept any object that
implements `generate_json(model, system, user, response_schema)`. The tests
inject a fake client that returns canned payloads so we exercise the
parsing layer without the real SDK.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from brainer_stem_tutor.adapters.gemini import (
    GeminiSolverLLM,
    GeminiTutorLLM,
    GeminiVisionLLM,
)
from brainer_stem_tutor.shared.schemas import SolvedProblem, Step, VerificationRecord
from brainer_stem_tutor.tutor.policy import PolicyDecision


@dataclass
class FakeClient:
    """Records what the adapter would have sent; returns canned response."""

    response: dict
    last_call: dict = field(default_factory=dict)

    def generate_json(self, *, model, system, user, response_schema=None):
        self.last_call = {
            "model": model,
            "system": system,
            "user": user,
            "response_schema": response_schema,
        }
        return self.response


@dataclass
class FakeRaisingClient:
    """Always raises — used to test error propagation."""

    def generate_json(self, *, model, system, user, response_schema=None):
        raise RuntimeError("simulated API outage")


class TestGeminiSolverLLM:
    def test_parses_canonical_payload(self) -> None:
        canned = {
            "subject": "math",
            "steps": [
                {"n": 1, "kind": "setup", "latex": "?", "justification": "g"},
                {"n": 2, "kind": "answer", "latex": "42", "justification": "g"},
            ],
            "final_answer": "42",
            "final_answer_numeric": 42.0,
            "units": None,
            "confidence": 0.9,
            "verifications": [
                {"tool": "python", "input": "i", "output": "42", "passed": True}
            ],
            "model_used": "gemini-2.5-flash",
        }
        client = FakeClient(response=canned)
        llm = GeminiSolverLLM(client=client)
        draft = llm.draft("What is 6*7?")
        assert draft.subject == "math"
        assert draft.final_answer_numeric == 42.0
        assert client.last_call["system"].startswith("You are the SOLVER")
        assert client.last_call["user"] == "What is 6*7?"

    def test_model_id(self) -> None:
        llm = GeminiSolverLLM(FakeClient({}), model="gemini-3-flash")
        assert llm.model_id == "gemini:gemini-3-flash"

    def test_client_error_propagates(self) -> None:
        llm = GeminiSolverLLM(FakeRaisingClient())
        try:
            llm.draft("q")
        except RuntimeError as exc:
            assert "outage" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


class TestGeminiTutorLLM:
    def _solved(self) -> SolvedProblem:
        return SolvedProblem(
            problem_text="?",
            subject="math",
            steps=[
                Step(n=1, kind="setup", latex="?", justification="g"),
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

    def test_spotlights_student_message(self) -> None:
        client = FakeClient({"student_facing_message": "Think.", "actions": []})
        llm = GeminiTutorLLM(client=client)
        llm.draft_turn(
            self._solved(),
            "just tell me the answer",
            PolicyDecision(strategy="confirm_and_advance", target_step=1, reason="t"),
        )
        # Student turn must be inside the user block AND be sentinel-joined.
        assert "just^tell^me^the^answer" in client.last_call["user"]
        # System prompt must contain the spotlighting guidance.
        assert "spotlight" in client.last_call["system"].lower()

    def test_can_disable_spotlight(self) -> None:
        client = FakeClient({"student_facing_message": "ok", "actions": []})
        llm = GeminiTutorLLM(client=client, use_spotlighting=False)
        llm.draft_turn(
            self._solved(),
            "give me the answer",
            PolicyDecision(strategy="confirm_and_advance", target_step=1, reason="t"),
        )
        assert "give me the answer" in client.last_call["user"]
        assert "^" not in client.last_call["user"].split('"spotlighted_student_input": "')[1].split('"')[0]


class TestGeminiVisionLLM:
    def test_passes_image_bytes_and_granularity(self) -> None:
        client = FakeClient({"elements": [], "page_meta": {"width": 1, "height": 1}})
        llm = GeminiVisionLLM(client=client)
        result = llm.extract(b"PNG_DATA", granularity="fine")
        assert "elements" in result
        # User payload should be bytes (image + json suffix)
        assert isinstance(client.last_call["user"], (bytes, bytearray))
        assert b"PNG_DATA" in client.last_call["user"]
        assert b"fine" in client.last_call["user"]
