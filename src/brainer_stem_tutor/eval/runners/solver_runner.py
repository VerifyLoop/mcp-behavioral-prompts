"""Batch runner for the solver agent over an EvalProblem dataset."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from ...solver import SolverAgent
from ..datasets import EvalProblem
from ..metrics.accuracy import SolverEntry, compute_solver_metrics

logger = logging.getLogger(__name__)


@dataclass
class SolverRunResult:
    config_name: str
    entries: list[SolverEntry]

    @property
    def metrics(self):
        return compute_solver_metrics(self.entries)


class SolverRunner:
    def __init__(self, agent: SolverAgent, config_name: str = "default") -> None:
        self._agent = agent
        self._config_name = config_name

    def run(self, problems: Iterable[EvalProblem]) -> SolverRunResult:
        entries: list[SolverEntry] = []
        for p in problems:
            try:
                solved = self._agent.solve(p.problem_text)
                entries.append(SolverEntry(problem=p, solved=solved))
            except Exception as exc:
                logger.warning("solver failed on %s: %s", p.id, exc)
                entries.append(SolverEntry(problem=p, solved=None, error=str(exc)))
        return SolverRunResult(config_name=self._config_name, entries=entries)
