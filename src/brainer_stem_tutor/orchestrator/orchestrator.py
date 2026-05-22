"""End-to-end orchestrator.

Glues vision + solver + tutor for one tutoring session. Designed to be
transport-agnostic: a FastAPI route or a WebSocket handler is a thin shim
around `Orchestrator.on_image`, `Orchestrator.on_student_message`, etc.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from ..shared.schemas import (
    SolvedProblem,
    StudentTurn,
    TutorTurn,
    VisionResult,
)
from ..shared.settings import TutorSettings, get_settings
from ..solver import SolverAgent
from ..tutor import TutorAgent
from ..vision import VisionAgent
from ..vision.schemas_ext import VisionContext
from .session import InMemorySessionStore, SessionState, SessionStore
from .signals import SignalComputer

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResponse:
    """What the orchestrator hands back to the transport layer."""

    tutor_turn: Optional[TutorTurn] = None
    vision_result: Optional[VisionResult] = None
    solved: Optional[SolvedProblem] = None
    notes: str = ""


class Orchestrator:
    def __init__(
        self,
        solver: SolverAgent,
        tutor: TutorAgent,
        vision: VisionAgent,
        store: Optional[SessionStore] = None,
        signal_computer: Optional[SignalComputer] = None,
        settings: Optional[TutorSettings] = None,
    ) -> None:
        self._solver = solver
        self._tutor = tutor
        self._vision = vision
        self._store = store if store is not None else InMemorySessionStore()
        self._signals = signal_computer or SignalComputer(settings)
        self._settings = settings or get_settings()

    def _state(self, session_id: str) -> SessionState:
        # InMemorySessionStore exposes get_or_create; for other stores we
        # fall back to get+put.
        if hasattr(self._store, "get_or_create"):
            return self._store.get_or_create(session_id)  # type: ignore[attr-defined]
        state = self._store.get(session_id)
        if state is None:
            state = SessionState(session_id=session_id)
            self._store.put(state)
        return state

    # -- public entry points --

    def on_problem_statement(
        self,
        session_id: str,
        problem_text: str,
        image_bytes: Optional[bytes] = None,
    ) -> OrchestratorResponse:
        """Student declared the problem they want help with."""
        state = self._state(session_id)
        vision_result: Optional[VisionResult] = None
        if image_bytes is not None:
            vision_result = self._vision.extract(image_bytes)
            state.vision = VisionContext(last_result=vision_result)

        image_hash = vision_result.image_hash if vision_result else None
        solved = self._solver.solve(problem_text, image_hash=image_hash)
        state.solved = solved
        state.last_step_change_ts = time.time()
        self._store.put(state)
        return OrchestratorResponse(
            solved=solved,
            vision_result=vision_result,
            notes="problem accepted",
        )

    def on_student_message(
        self,
        session_id: str,
        text: str,
        ts: Optional[float] = None,
    ) -> OrchestratorResponse:
        state = self._state(session_id)
        if state.solved is None:
            return OrchestratorResponse(
                notes="no solved problem yet; ignoring message"
            )
        state.append_student(StudentTurn(text=text, ts=ts if ts is not None else time.time()))
        signals = self._signals.compute(state)
        turn = self._tutor.respond(
            state.solved,
            student_message=text,
            signals=signals,
            vision=state.vision,
        )
        state.append_tutor(turn)
        self._store.put(state)
        return OrchestratorResponse(tutor_turn=turn)

    def on_image_update(
        self,
        session_id: str,
        image_bytes: bytes,
        step_keywords: Optional[dict[int, list[str]]] = None,
    ) -> OrchestratorResponse:
        """A new snapshot of the student's notes arrived."""
        state = self._state(session_id)
        result = self._vision.extract(image_bytes)
        state.vision = VisionContext(last_result=result)
        if step_keywords:
            mapping = VisionAgent.build_step_to_bbox_mapping(result, step_keywords)
            state.vision = VisionContext(last_result=result, step_to_bboxes=mapping)
        self._store.put(state)
        return OrchestratorResponse(vision_result=result, notes="vision updated")

    def mark_step_completed(self, session_id: str, step_n: int) -> OrchestratorResponse:
        state = self._state(session_id)
        state.mark_step_completed(step_n)
        self._store.put(state)
        return OrchestratorResponse(notes=f"step {step_n} completed")

    def mark_error(self, session_id: str, kind: str) -> OrchestratorResponse:
        state = self._state(session_id)
        state.mark_error(kind)
        self._store.put(state)
        return OrchestratorResponse(notes=f"error tagged: {kind}")
