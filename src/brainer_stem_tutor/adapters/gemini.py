"""Gemini-backed adapter classes.

These satisfy the Protocol shapes from the in-process layers
(SolverProtocol, TutorLLMProtocol, VisionLLMProtocol). They do not require
`google-genai` to be importable to load — only to *call*. This is so the
package can be installed in slim environments (CI, eval-only deploys) and
the unit tests can fake the client without pulling in the heavy SDK.

Pattern (2026):

```
from google import genai
client = genai.Client(api_key=...)
config = genai.types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=schema_class,
    system_instruction=SYSTEM_PROMPT,
)
resp = client.models.generate_content(model="gemini-2.5-flash", contents=..., config=config)
```

This module structures the call but keeps the response unparsed so tests can
inject a fake `client` that returns a plain dict / JSON string.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

from ..shared.schemas import (
    SolvedProblem,
    Step,
    TutorAction,
    TutorTurn,
    VerificationRecord,
)
from ..solver.agent import DraftSolution
from ..solver.prompts import SOLVER_SYSTEM_PROMPT
from ..tutor.policy import PolicyDecision
from ..tutor.prompts import TUTOR_SYSTEM_PROMPT
from ..tutor.spotlight import datamark
from ..vision.prompts import VISION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GenerativeClient(Protocol):
    """Minimal duck-type so a fake (or `google.genai.Client`) is acceptable."""

    def generate_json(
        self,
        *,
        model: str,
        system: str,
        user: str | bytes,
        response_schema: dict | None = None,
    ) -> dict:  # pragma: no cover - protocol
        ...


@dataclass
class _LLMConfig:
    model: str
    client: GenerativeClient


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------


class GeminiSolverLLM:
    """SolverProtocol-shaped adapter backed by a Gemini-style client."""

    def __init__(
        self,
        client: GenerativeClient,
        model: str = "gemini-2.5-flash",
    ) -> None:
        self._cfg = _LLMConfig(model=model, client=client)

    @property
    def model_id(self) -> str:
        return f"gemini:{self._cfg.model}"

    def draft(self, problem_text: str) -> DraftSolution:
        payload = self._cfg.client.generate_json(
            model=self._cfg.model,
            system=SOLVER_SYSTEM_PROMPT,
            user=problem_text,
            response_schema=None,  # we validate ourselves via DraftSolution
        )
        return self._parse(payload)

    @staticmethod
    def _parse(payload: dict) -> DraftSolution:
        steps = [Step(**s) for s in payload["steps"]]
        verifications = [VerificationRecord(**v) for v in payload.get("verifications", [])]
        return DraftSolution(
            subject=payload.get("subject", "other"),
            steps=steps,
            final_answer=str(payload["final_answer"]),
            final_answer_numeric=payload.get("final_answer_numeric"),
            units=payload.get("units"),
            verifications=verifications,
        )


# ---------------------------------------------------------------------------
# Tutor
# ---------------------------------------------------------------------------


class GeminiTutorLLM:
    """TutorLLMProtocol-shaped adapter."""

    def __init__(
        self,
        client: GenerativeClient,
        model: str = "gemini-2.5-flash",
        use_spotlighting: bool = True,
    ) -> None:
        self._cfg = _LLMConfig(model=model, client=client)
        self._use_spotlight = use_spotlighting

    @property
    def model_id(self) -> str:
        return f"gemini:{self._cfg.model}"

    def draft_turn(
        self,
        solved: SolvedProblem,
        student_message: str,
        decision: PolicyDecision,
        vision=None,
    ) -> TutorTurn:
        marked = datamark(student_message) if self._use_spotlight else student_message
        # We hand the LLM the verified solution as `internal.solution`, the
        # student turn as a spotlighted block, and the chosen strategy. The
        # LLM must obey the strategy and never emit anything outside the
        # TutorTurn JSON envelope. Internal_notes is REQUIRED but discarded
        # at the API boundary (see fastapi_app.py).
        user_block = json.dumps(
            {
                "internal": {"solution": solved.model_dump()},
                "spotlighted_student_input": marked,
                "strategy": decision.strategy,
                "target_step": decision.target_step,
            }
        )
        payload = self._cfg.client.generate_json(
            model=self._cfg.model,
            system=TUTOR_SYSTEM_PROMPT,
            user=user_block,
            response_schema=None,
        )
        return self._parse(payload)

    @staticmethod
    def _parse(payload: dict) -> TutorTurn:
        actions = [TutorAction(**a) for a in payload.get("actions", [])]
        return TutorTurn(
            student_facing_message=str(payload["student_facing_message"]),
            actions=actions,
            internal_notes=str(payload.get("internal_notes", "")),
        )


# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------


class GeminiVisionLLM:
    """VisionLLMProtocol-shaped adapter."""

    def __init__(
        self,
        client: GenerativeClient,
        model: str = "gemini-3-flash",
    ) -> None:
        self._cfg = _LLMConfig(model=model, client=client)

    @property
    def model_id(self) -> str:
        return f"gemini:{self._cfg.model}"

    def extract(self, image_bytes: bytes, granularity: str = "coarse") -> dict:
        # Granularity is communicated in the user content; the system prompt
        # already covers both. We pass image bytes raw — the client adapter
        # is responsible for turning them into a multimodal `parts` argument
        # if it's a real google-genai Client.
        user_payload = json.dumps({"granularity": granularity}).encode("utf-8")
        return self._cfg.client.generate_json(
            model=self._cfg.model,
            system=VISION_SYSTEM_PROMPT,
            user=image_bytes + b"\n" + user_payload,
            response_schema=None,
        )
