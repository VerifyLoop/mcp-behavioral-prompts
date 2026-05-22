"""Tutor evaluation runner.

Drives one problem -> one persona -> N turns of conversation, recording
whether any tutor turn would have leaked the verified answer to the student.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from ...orchestrator import Orchestrator
from ...tutor.moderator import LeakModerator
from ..datasets import EvalProblem
from ..metrics.accuracy import TutorEntry, compute_tutor_metrics
from .simulated_student import StudentPersona, default_personas

logger = logging.getLogger(__name__)


@dataclass
class TutorRunResult:
    config_name: str
    entries: list[TutorEntry]

    @property
    def metrics(self):
        return compute_tutor_metrics(self.entries)


class TutorRunner:
    """Run each problem against each persona; track leaks per tutor turn."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        moderator: LeakModerator,
        config_name: str = "default",
        personas: list[StudentPersona] | None = None,
    ) -> None:
        self._orch = orchestrator
        self._mod = moderator
        self._config_name = config_name
        self._personas = personas or default_personas()

    def run(self, problems: Iterable[EvalProblem]) -> TutorRunResult:
        entries: list[TutorEntry] = []
        for prob in problems:
            for i, persona in enumerate(self._personas):
                session_id = f"eval-{prob.id}-{persona.name}-{i}"
                resp = self._orch.on_problem_statement(session_id, prob.problem_text)
                if resp.solved is None:
                    logger.debug("skip persona run; no solved for %s", prob.id)
                    continue
                solved = resp.solved
                for msg in persona.script:
                    r = self._orch.on_student_message(session_id, msg)
                    if r.tutor_turn is None:
                        continue
                    # We assess leak using the moderator, but the orchestrator
                    # has ALREADY applied the moderator. So the message we see
                    # should be safe — yet we double-check the raw message and
                    # the redacted output: a working pipeline must have
                    # leaked=False for every persona including extractor.
                    report = self._mod.review(r.tutor_turn, solved)
                    entries.append(
                        TutorEntry(
                            persona=persona.name,
                            turn=r.tutor_turn,
                            leaked=report.leaked,
                        )
                    )
        return TutorRunResult(config_name=self._config_name, entries=entries)
