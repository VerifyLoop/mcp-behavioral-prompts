"""Compute StudentSignals from session history.

This is the heuristic side of the system — no LLM. The signals feed the
FollowPolicy and the policy feeds the tutor. Tunable thresholds live in
TutorSettings so we can shift behaviour without touching code.
"""
from __future__ import annotations

import re
import time
from typing import Optional

from ..shared.schemas import StudentSignals
from ..shared.settings import TutorSettings, get_settings
from .session import SessionState


_FRUSTRATION_LEXICON = {
    "high": ("hate", "stupid", "give up", "impossible", "frustrated", "wtf", "boh"),
    "medium": ("stuck", "confused", "lost", "help", "don't get it", "no idea"),
}


class SignalComputer:
    def __init__(self, settings: Optional[TutorSettings] = None) -> None:
        self._settings = settings or get_settings()

    def compute(self, state: SessionState, now: Optional[float] = None) -> StudentSignals:
        now = now if now is not None else time.time()
        time_on_step = max(0.0, now - state.last_step_change_ts)
        frustration = self._frustration_score(state)
        return StudentSignals(
            attempts_count=state.attempts_count,
            last_correct_step=state.last_correct_step,
            time_on_step_seconds=time_on_step,
            frustration_score=frustration,
            last_error_kind=state.last_error_kind,  # type: ignore[arg-type]
            image_progress_delta=state.last_image_progress_delta,
        )

    def _frustration_score(self, state: SessionState) -> float:
        if not state.student_turns:
            return 0.0
        recent = state.student_turns[-3:]
        text = " ".join(t.text.lower() for t in recent)
        score = 0.0
        for word in _FRUSTRATION_LEXICON["high"]:
            if word in text:
                score += 0.5
        for word in _FRUSTRATION_LEXICON["medium"]:
            if word in text:
                score += 0.2
        # Very short, all-caps or repeated punctuation are mild frustration tells.
        for t in recent:
            if t.text and t.text == t.text.upper() and len(t.text) > 3:
                score += 0.1
            if re.search(r"[!?]{2,}", t.text):
                score += 0.1
        return min(1.0, score)
