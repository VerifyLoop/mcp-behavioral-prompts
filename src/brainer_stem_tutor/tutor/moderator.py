"""Anti-leak moderator.

The tutor is trusted-but-bounded: even when prompted carefully, an LLM may
slip and reveal the final answer or copy multiple consecutive steps from the
verified solution. The moderator is a deterministic post-processor that
inspects every TutorTurn before it leaves the orchestrator.

Two leak signals matter:
1. The final answer (numeric or string) appears verbatim in the student-
   facing message.
2. More than `max_consecutive_steps` solution steps are quoted in a row.

When a leak is detected the message is rewritten to a safe fallback that
nudges the student with a Socratic prompt instead of confessing the answer.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from ..shared.schemas import SolvedProblem, TutorTurn
from ..shared.settings import TutorSettings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class LeakReport:
    """Why the moderator decided a message was unsafe."""

    leaked: bool
    reasons: list[str]
    redacted_message: Optional[str] = None
    matched_steps: list[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.matched_steps is None:
            self.matched_steps = []


# Tokenisation tuned for math/LaTeX: split on whitespace and most punctuation
# but keep digits, decimal points and minus signs together so "12.5" survives
# as one token.
_TOKEN_RE = re.compile(r"[A-Za-z]+|-?\d+(?:\.\d+)?|[^\s\w]")


def _tokenise(s: str) -> list[str]:
    return _TOKEN_RE.findall(s)


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


class LeakModerator:
    """Inspect a TutorTurn and decide whether it leaks the solution."""

    def __init__(self, settings: Optional[TutorSettings] = None) -> None:
        self._settings = settings or get_settings()

    def review(self, turn: TutorTurn, solved: SolvedProblem) -> LeakReport:
        reasons: list[str] = []
        matched: list[int] = []
        msg = turn.student_facing_message
        msg_norm = _normalise(msg)

        # 1) Final answer leak: exact numeric or string match.
        if self._numeric_leak(msg_norm, solved):
            reasons.append("numeric final_answer present in message")

        if self._string_leak(msg_norm, solved):
            reasons.append("string final_answer present in message")

        # 2) Step copy leak: count how many consecutive solution-step LaTeX
        # fragments appear in order in the message.
        consecutive = self._consecutive_step_match(msg_norm, solved, matched)
        if consecutive > self._settings.MODERATOR_MAX_CONSECUTIVE_STEPS:
            reasons.append(
                f"{consecutive} consecutive solution steps appear in message "
                f"(limit {self._settings.MODERATOR_MAX_CONSECUTIVE_STEPS})"
            )

        leaked = bool(reasons)
        redacted = self._redact(turn, solved) if leaked else None
        if leaked:
            logger.warning("moderator blocked leak: %s", reasons)
        return LeakReport(
            leaked=leaked,
            reasons=reasons,
            redacted_message=redacted,
            matched_steps=matched,
        )

    # -- detection helpers --

    def _numeric_leak(self, msg_norm: str, solved: SolvedProblem) -> bool:
        if solved.final_answer_numeric is None:
            return False
        target = solved.final_answer_numeric
        tol = self._settings.MODERATOR_NUMERIC_TOLERANCE
        # extract all signed decimal numbers from the message
        for m in re.finditer(r"-?\d+(?:\.\d+)?", msg_norm):
            try:
                val = float(m.group(0))
            except ValueError:
                continue
            if abs(val - target) <= tol or (
                target != 0 and abs((val - target) / target) <= tol
            ):
                return True
        return False

    def _string_leak(self, msg_norm: str, solved: SolvedProblem) -> bool:
        """Detect exact substring of the final_answer in the message."""
        fa = _normalise(solved.final_answer)
        if not fa or len(fa) < 2:
            return False
        # Plain substring; the regex word-boundary doesn't play well with
        # LaTeX-ish answers like "[-2, 2]" or "x + 1".
        return fa in msg_norm

    def _consecutive_step_match(
        self,
        msg_norm: str,
        solved: SolvedProblem,
        matched_out: list[int],
    ) -> int:
        """Longest run of consecutive solution steps quoted in `msg_norm`.

        A step counts as quoted when its LaTeX content (after removing
        backslashes/braces and lowercasing) appears as a substring.
        """
        run = 0
        best = 0
        for step in solved.steps:
            fragment = self._step_fingerprint(step.latex)
            if fragment and fragment in msg_norm:
                run += 1
                best = max(best, run)
                matched_out.append(step.n)
            else:
                run = 0
        return best

    @staticmethod
    def _step_fingerprint(latex: str) -> str:
        s = latex.replace("\\", "")
        s = re.sub(r"[{}]", "", s)
        s = _normalise(s)
        # Single-character fingerprints would false-positive trivially.
        return s if len(s) >= 3 else ""

    def _redact(self, turn: TutorTurn, solved: SolvedProblem) -> str:
        """Build a safe Socratic fallback when a leak is detected.

        Keeps the original actions but rewrites the message to a generic
        nudge that targets the FIRST unproven step. The caller will replace
        the turn's student_facing_message with this value.
        """
        target_step = next(
            (s.n for s in solved.steps if s.kind in ("setup", "concept", "derivation")),
            1,
        )
        return (
            f"Let's slow down and look at step {target_step} together. "
            "What does each symbol there represent, and what relationship between "
            "them did you use? Try to articulate it in one sentence before we "
            "move on."
        )
