"""Tutor agent.

A small surface — the orchestrator calls `tutor.respond(...)` which:

1. Consults the FollowPolicy (signals -> strategy).
2. Asks the underlying TutorLLMProtocol to draft a turn for that strategy.
3. Runs the turn through the LeakModerator before returning it.

The "intelligence" is in the LLM. The "safety" is in the moderator. The
"control" is in the policy. Keeping these three concerns separate is what
lets us swap models without rewriting the safety net.
"""
from __future__ import annotations

import logging
import random
from typing import Optional, Protocol

from ..shared.schemas import (
    SolvedProblem,
    StudentSignals,
    TutorAction,
    TutorTurn,
)
from ..shared.schemas import ActionKind
from ..shared.settings import TutorSettings, get_settings
from ..vision.schemas_ext import VisionContext
from .moderator import LeakModerator
from .policy import FollowPolicy, PolicyDecision, Strategy

logger = logging.getLogger(__name__)


class TutorLLMProtocol(Protocol):
    """The interface a real ADK/Gemini-backed tutor implements."""

    @property
    def model_id(self) -> str:  # pragma: no cover - protocol
        ...

    def draft_turn(
        self,
        solved: SolvedProblem,
        student_message: str,
        decision: PolicyDecision,
        vision: Optional[VisionContext] = None,
    ) -> TutorTurn:  # pragma: no cover - protocol
        ...


class MockTutorLLM:
    """Template-based tutor used in tests and offline demos.

    Produces strategy-appropriate Socratic messages. No leakage by
    construction — never references final_answer, never copies steps.
    A real LLM is needed for the long tail; this mock proves the wiring
    and lets us measure leak_rate baseline.
    """

    model_id = "mock-tutor-v1"

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self._rng = rng or random.Random(0)

    def draft_turn(
        self,
        solved: SolvedProblem,
        student_message: str,
        decision: PolicyDecision,
        vision: Optional[VisionContext] = None,
    ) -> TutorTurn:
        actions: list[TutorAction] = []
        message = self._message_for(decision.strategy, solved, decision.target_step)

        if vision is not None and vision.last_result is not None:
            # Highlight whatever element the current focus step refers to.
            ids = vision.bbox_ids_for_step(decision.target_step)
            if ids:
                actions.append(
                    TutorAction(
                        kind=ActionKind.HIGHLIGHT_BBOXES, bbox_ids=ids, color="#fde047"
                    )
                )

        if decision.strategy == "concept_quiz":
            actions.append(
                TutorAction(
                    kind=ActionKind.SHOW_QUIZ,
                    text="Which concept governs the next step?",
                    choices=self._concept_choices(solved, decision.target_step),
                    correct_idx=0,
                )
            )
        if decision.strategy == "encourage_pause":
            actions.append(TutorAction(kind=ActionKind.ASK_QUESTION, text="Ready to continue?"))

        return TutorTurn(
            student_facing_message=message,
            actions=actions,
            internal_notes=f"strategy={decision.strategy} target_step={decision.target_step}",
        )

    # -- templates --

    def _message_for(
        self,
        strategy: Strategy,
        solved: SolvedProblem,
        target_step: int,
    ) -> str:
        focus = self._focus_concept(solved, target_step)

        if strategy == "confirm_and_advance":
            return (
                f"Good — your reasoning up to step {max(target_step - 1, 1)} holds. "
                f"For the next step, think about {focus}. What relationship "
                "does that suggest?"
            )
        if strategy == "soft_hint":
            return (
                f"You're close. Take another look at {focus} — is there a "
                "rule we haven't applied yet that connects the quantities "
                "in your last expression?"
            )
        if strategy == "targeted_hint":
            return (
                "Compare your last line with the dimensions of what you're "
                "trying to find. Does the units side of the equation balance? "
                "If not, that's where the slip is."
            )
        if strategy == "concept_quiz":
            return (
                f"Before we continue, let's confirm the concept we need for "
                f"step {target_step}."
            )
        if strategy == "direct_hint":
            return (
                f"You're stuck at step {target_step}. The next move is to "
                f"apply {focus}. Try writing the resulting expression yourself."
            )
        if strategy == "encourage_pause":
            return (
                "This problem is genuinely hard, and pushing through frustration "
                "makes it harder. Take a short break — when you're back we can "
                "recap the part you already have."
            )
        return "Tell me what you've tried so far so I can spot where to help."

    @staticmethod
    def _focus_concept(solved: SolvedProblem, target_step: int) -> str:
        step = next((s for s in solved.steps if s.n == target_step), solved.steps[0])
        if step.kind == "concept":
            return "the underlying definition or law"
        if step.kind == "derivation":
            return "the algebraic manipulation that follows"
        if step.kind == "computation":
            return "the numerical evaluation"
        return "what each symbol stands for"

    @staticmethod
    def _concept_choices(solved: SolvedProblem, target_step: int) -> list[str]:
        if solved.subject == "physics":
            return [
                "constant-acceleration kinematics",
                "energy conservation",
                "momentum conservation",
                "Newton's third law",
            ]
        if solved.subject == "math":
            return [
                "factoring / root extraction",
                "differentiation",
                "integration by parts",
                "trigonometric identities",
            ]
        return [
            "stoichiometric ratios",
            "conservation of mass",
            "thermodynamic equilibrium",
            "kinetic rate law",
        ]


class TutorAgent:
    """The orchestrator-facing tutor.

    Wraps a TutorLLMProtocol with policy + moderator. Holds a per-instance
    fingerprint cache so the moderator doesn't recompute step fingerprints on
    every conversational turn for the same problem.
    """

    def __init__(
        self,
        llm: TutorLLMProtocol,
        policy: Optional[FollowPolicy] = None,
        moderator: Optional[LeakModerator] = None,
        settings: Optional[TutorSettings] = None,
    ) -> None:
        self._llm = llm
        self._policy = policy or FollowPolicy(settings)
        self._moderator = moderator or LeakModerator(settings)
        self._fp_cache: dict[int, list[tuple[int, str]]] = {}

    def _fingerprints(self, solved: SolvedProblem) -> list[tuple[int, str]]:
        key = id(solved)
        fps = self._fp_cache.get(key)
        if fps is None:
            fps = LeakModerator.precompute_fingerprints(solved)
            self._fp_cache[key] = fps
        return fps

    def respond(
        self,
        solved: SolvedProblem,
        student_message: str,
        signals: StudentSignals,
        vision: Optional[VisionContext] = None,
    ) -> TutorTurn:
        decision = self._policy.decide(signals, total_steps=len(solved.steps))
        turn = self._llm.draft_turn(solved, student_message, decision, vision=vision)
        report = self._moderator.review(turn, solved, fingerprints=self._fingerprints(solved))
        if report.leaked:
            assert report.redacted_message is not None
            return TutorTurn(
                student_facing_message=report.redacted_message,
                actions=turn.actions,
                internal_notes=(
                    f"{turn.internal_notes} | moderator_blocked: "
                    f"{'; '.join(report.reasons)}"
                ),
            )
        return turn
