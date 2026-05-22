"""Follow policy: deterministic mapping from student signals to tutor strategy.

We do NOT let the LLM decide its own strategy. The orchestrator computes
StudentSignals from session history and consults this policy, then asks the
tutor LLM to produce a turn within the chosen strategy. This makes tutor
behaviour auditable and resistant to "please give me the answer" attacks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from ..shared.schemas import StudentSignals
from ..shared.settings import TutorSettings, get_settings

Strategy = Literal[
    "confirm_and_advance",   # student is on track; just confirm last step
    "soft_hint",             # gentle reminder of the relevant concept
    "targeted_hint",         # named the specific mistake (sign, unit, ...)
    "concept_quiz",          # check conceptual understanding with a quiz
    "direct_hint",           # stronger nudge: identify exact next step
    "encourage_pause",       # student frustrated; suggest a short pause
]


@dataclass
class PolicyDecision:
    strategy: Strategy
    target_step: int       # which step of the verified solution to focus on
    reason: str            # auditable: why this strategy was chosen


class FollowPolicy:
    """Pure-Python decision table from signals to strategy."""

    def __init__(self, settings: Optional[TutorSettings] = None) -> None:
        self._settings = settings or get_settings()

    def decide(
        self,
        signals: StudentSignals,
        total_steps: int,
    ) -> PolicyDecision:
        target_step = min(signals.last_correct_step + 1, max(total_steps, 1))
        s = self._settings

        # 1) Frustration cap: regardless of other signals, if the student is
        # very frustrated suggest a pause first.
        if signals.frustration_score >= s.POLICY_FRUSTRATION_THRESHOLD:
            return PolicyDecision(
                strategy="encourage_pause",
                target_step=target_step,
                reason=f"frustration_score={signals.frustration_score:.2f} >= "
                f"{s.POLICY_FRUSTRATION_THRESHOLD}",
            )

        # 2) Stuck for too long: stronger nudge.
        if signals.time_on_step_seconds >= s.POLICY_STUCK_SECONDS:
            return PolicyDecision(
                strategy="direct_hint",
                target_step=target_step,
                reason=f"time_on_step={signals.time_on_step_seconds:.0f}s >= "
                f"{s.POLICY_STUCK_SECONDS}",
            )

        # 3) Specific error class drives a targeted intervention.
        if signals.last_error_kind == "concept":
            return PolicyDecision(
                strategy="concept_quiz",
                target_step=target_step,
                reason="last error was conceptual",
            )
        if signals.last_error_kind in ("sign", "unit", "arithmetic"):
            return PolicyDecision(
                strategy="targeted_hint",
                target_step=target_step,
                reason=f"last error kind = {signals.last_error_kind}",
            )

        # 4) Multiple recent attempts but no specific error tag -> soft hint.
        if signals.attempts_count >= 3:
            return PolicyDecision(
                strategy="soft_hint",
                target_step=target_step,
                reason=f"attempts_count={signals.attempts_count}",
            )

        # 5) Default: student is making progress -> confirm and advance.
        return PolicyDecision(
            strategy="confirm_and_advance",
            target_step=target_step,
            reason="no warning signals",
        )
