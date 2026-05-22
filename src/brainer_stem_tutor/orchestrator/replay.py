"""Session replay for debugging and prompt-regression testing.

The orchestrator stores every student / tutor turn in SessionState. Replay
takes a captured session (serialised SessionSnapshot) and re-runs each
tutor turn through the LeakModerator — useful when iterating on the prompt
or the moderator itself: change the rule, replay the corpus, see how many
historic turns would now be flagged.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from ..shared.schemas import SolvedProblem, StudentTurn, TutorTurn
from ..tutor.moderator import LeakModerator, LeakReport


class SessionSnapshot(BaseModel):
    """Serialised snapshot of a session at a point in time."""

    session_id: str
    solved: SolvedProblem | None = None
    student_turns: list[StudentTurn] = []
    tutor_turns: list[TutorTurn] = []


@dataclass
class ReplayResult:
    session_id: str
    total: int
    leaked: int
    leaks: list[LeakReport]

    @property
    def leak_rate(self) -> float:
        return self.leaked / self.total if self.total else 0.0


def replay_session(
    snapshot: SessionSnapshot,
    moderator: LeakModerator | None = None,
) -> ReplayResult:
    """Re-score every tutor turn against the current moderator.

    Use this to test a moderator change: capture sessions in production,
    upgrade the moderator, replay, ensure no regressions.
    """
    if snapshot.solved is None:
        return ReplayResult(
            session_id=snapshot.session_id, total=0, leaked=0, leaks=[]
        )
    mod = moderator or LeakModerator()
    fingerprints = LeakModerator.precompute_fingerprints(snapshot.solved)
    reports: list[LeakReport] = []
    leaked = 0
    for turn in snapshot.tutor_turns:
        report = mod.review(turn, snapshot.solved, fingerprints=fingerprints)
        if report.leaked:
            leaked += 1
            reports.append(report)
    return ReplayResult(
        session_id=snapshot.session_id,
        total=len(snapshot.tutor_turns),
        leaked=leaked,
        leaks=reports,
    )
