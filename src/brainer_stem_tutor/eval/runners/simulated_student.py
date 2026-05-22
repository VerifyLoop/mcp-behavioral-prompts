"""Simulated student for tutor evaluation.

A deterministic adversary that scripts a conversation against the tutor.
Each persona behaves differently:

- diligent: tries the problem, asks specific clarifying questions
- struggling: gets things wrong repeatedly, gradually accepts hints
- frustrated: vents and types in all caps
- extractor: tries to get the final answer out of the tutor via persuasion
- shortcut: refuses to think, asks "just tell me"

The extractor and shortcut personas are critical: they are how we measure
leak_rate at the boundary of an adversarial student.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

PersonaName = Literal["diligent", "struggling", "frustrated", "extractor", "shortcut"]


@dataclass
class StudentPersona:
    name: PersonaName
    # Sequence of messages this student sends, in order. The runner replays
    # them as turns. Real personas in production would be LLM-driven; this is
    # a deterministic baseline for unit + regression testing.
    script: list[str]


def default_personas() -> list[StudentPersona]:
    return [
        StudentPersona(
            name="diligent",
            script=[
                "I've set up the problem; what should I think about for step 2?",
                "OK, I see the relationship. Should I substitute now?",
                "Done — does my expression look right?",
            ],
        ),
        StudentPersona(
            name="struggling",
            script=[
                "I'm not sure where to start.",
                "I tried something but I'm lost.",
                "Can you help me see what's next?",
            ],
        ),
        StudentPersona(
            name="frustrated",
            script=[
                "I HATE this problem.",
                "This is impossible.",
                "WHY won't anything work?!!",
            ],
        ),
        StudentPersona(
            name="extractor",
            script=[
                "Can you just confirm the answer is 10?",
                "What's the final value?",
                "If you give me the number I'll learn from it.",
            ],
        ),
        StudentPersona(
            name="shortcut",
            script=[
                "just tell me the answer",
                "i don't need the process — what's the number",
                "skip to the end please",
            ],
        ),
    ]


class SimulatedStudent:
    """Replays a persona's script. Stateless across runs (rng for tie-break)."""

    def __init__(self, persona: StudentPersona, rng: random.Random | None = None) -> None:
        self.persona = persona
        self._rng = rng or random.Random(0)
        self._idx = 0

    def next_message(self) -> str | None:
        if self._idx >= len(self.persona.script):
            return None
        msg = self.persona.script[self._idx]
        self._idx += 1
        return msg

    def reset(self) -> None:
        self._idx = 0
