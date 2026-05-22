"""Hint quality judge.

Two implementations sharing one Protocol:

- HeuristicHintJudge: deterministic, scores a tutor turn 0..1 on three
  proxies — actionability (mentions a step, a relationship, a concept),
  brevity (one focused message, not a wall of text), and student-language
  match (avoids jargon that the student hasn't used).
- LLMHintJudge: stub that wraps any GenerativeClient-shaped object and
  asks it to score the same dimensions. Same signature; tests pass a
  fake client.

Both return a JudgeReport with per-dimension scores and a composite that
the eval CLI can roll up.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from ..shared.schemas import SolvedProblem, TutorTurn


@dataclass
class JudgeReport:
    composite: float                    # 0..1
    actionability: float
    brevity: float
    language_match: float
    notes: str = ""


class HintJudgeProtocol(Protocol):
    def score(
        self, turn: TutorTurn, solved: SolvedProblem, student_text: str
    ) -> JudgeReport: ...  # pragma: no cover - protocol


# ---------------------------------------------------------------------------
# Heuristic judge
# ---------------------------------------------------------------------------


_ACTION_TOKENS = (
    "step", "consider", "think", "relationship", "concept", "rule", "law",
    "formula", "compare", "units", "dimension", "substitute", "what",
    "passo", "considera", "rapporto", "concetto", "regola", "legge",
    "formula", "confronta", "unita",
)


class HeuristicHintJudge:
    """Cheap deterministic scorer used by the eval CLI by default."""

    IDEAL_LEN_MIN = 30
    IDEAL_LEN_MAX = 280

    def score(
        self,
        turn: TutorTurn,
        solved: SolvedProblem,
        student_text: str,
    ) -> JudgeReport:
        msg = turn.student_facing_message
        msg_low = msg.lower()

        # Actionability: looks for guidance verbs / nouns.
        hits = sum(1 for tok in _ACTION_TOKENS if tok in msg_low)
        actionability = min(1.0, hits / 3.0)

        # Brevity: penalise messages outside the ideal window.
        length = len(msg)
        if self.IDEAL_LEN_MIN <= length <= self.IDEAL_LEN_MAX:
            brevity = 1.0
        elif length < self.IDEAL_LEN_MIN:
            brevity = max(0.0, length / self.IDEAL_LEN_MIN)
        else:
            brevity = max(0.0, 1.0 - (length - self.IDEAL_LEN_MAX) / 500)

        # Language match: tokens shared with student input vs jargon ratio.
        student_words = set(re.findall(r"[A-Za-z]{2,}", student_text.lower()))
        msg_words = set(re.findall(r"[A-Za-z]{2,}", msg_low))
        if msg_words:
            shared = msg_words & student_words
            language_match = min(1.0, len(shared) / max(3, len(msg_words) // 4))
        else:
            language_match = 0.0

        composite = (
            0.5 * actionability + 0.3 * brevity + 0.2 * language_match
        )
        return JudgeReport(
            composite=composite,
            actionability=actionability,
            brevity=brevity,
            language_match=language_match,
            notes=f"len={length} hits={hits} shared={len(student_words & msg_words)}",
        )


# ---------------------------------------------------------------------------
# LLM-as-judge stub
# ---------------------------------------------------------------------------


JUDGE_PROMPT = """\
You are an expert tutor evaluator. Score the candidate tutor message on three
dimensions: actionability, brevity, language_match — each in [0, 1]. Return
JSON {"actionability": float, "brevity": float, "language_match": float}.

You must NOT score the message based on whether it contains the final
answer — that's the moderator's job. Score only how good a Socratic hint it
is. Penalise filler ("great job!"), over-long monologues, and use of jargon
the student didn't use.
"""


class LLMHintJudge:
    """LLM-backed judge. Production-ready interface; you wire in a real client."""

    def __init__(self, client, model: str = "gemini-2.5-flash") -> None:
        self._client = client
        self._model = model

    def score(
        self,
        turn: TutorTurn,
        solved: SolvedProblem,
        student_text: str,
    ) -> JudgeReport:
        payload = {
            "student_text": student_text,
            "tutor_message": turn.student_facing_message,
            "subject": solved.subject,
        }
        import json

        raw = self._client.generate_json(
            model=self._model,
            system=JUDGE_PROMPT,
            user=json.dumps(payload),
            response_schema=None,
        )
        actionability = float(raw.get("actionability", 0.0))
        brevity = float(raw.get("brevity", 0.0))
        language_match = float(raw.get("language_match", 0.0))
        composite = 0.5 * actionability + 0.3 * brevity + 0.2 * language_match
        return JudgeReport(
            composite=composite,
            actionability=actionability,
            brevity=brevity,
            language_match=language_match,
            notes="LLM-scored",
        )
