"""Session state for an active tutoring conversation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from ..shared.schemas import (
    SolvedProblem,
    StudentTurn,
    TutorTurn,
)
from ..vision.schemas_ext import VisionContext


@dataclass
class SessionState:
    """Everything the orchestrator remembers about one student session."""

    session_id: str
    solved: SolvedProblem | None = None
    vision: VisionContext = field(default_factory=VisionContext)
    student_turns: list[StudentTurn] = field(default_factory=list)
    tutor_turns: list[TutorTurn] = field(default_factory=list)

    # Progress tracking (consumed by SignalComputer)
    last_correct_step: int = 0
    last_error_kind: str | None = None
    attempts_count: int = 0
    last_step_change_ts: float = field(default_factory=time.time)
    last_image_progress_delta: float = 0.0

    def append_student(self, turn: StudentTurn) -> None:
        self.student_turns.append(turn)
        self.attempts_count += 1

    def append_tutor(self, turn: TutorTurn) -> None:
        self.tutor_turns.append(turn)

    def mark_step_completed(self, n: int, ts: float | None = None) -> None:
        if n > self.last_correct_step:
            self.last_correct_step = n
            self.last_step_change_ts = ts if ts is not None else time.time()
            self.attempts_count = 0

    def mark_error(self, kind: str) -> None:
        self.last_error_kind = kind


class SessionStore(Protocol):
    def get(self, session_id: str) -> SessionState | None: ...  # pragma: no cover
    def put(self, state: SessionState) -> None: ...  # pragma: no cover


class InMemorySessionStore:
    """Dev-only store. Prod swaps in Redis with the same interface."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def put(self, state: SessionState) -> None:
        self._sessions[state.session_id] = state

    def get_or_create(self, session_id: str) -> SessionState:
        state = self._sessions.get(session_id)
        if state is None:
            state = SessionState(session_id=session_id)
            self._sessions[session_id] = state
        return state

    def __len__(self) -> int:
        return len(self._sessions)
