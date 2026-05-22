"""Optional FastAPI transport for the orchestrator.

This module is imported lazily so the rest of the package does not depend on
FastAPI. Production deployment swaps `_build_orchestrator()` for one that
wires real LLM-backed agents.

Run with:
    pip install fastapi uvicorn
    PYTHONPATH=src uvicorn brainer_stem_tutor.orchestrator.fastapi_app:app
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from ..solver import MockSolverLLM, SolverAgent
from ..tutor import MockTutorLLM, TutorAgent
from ..vision import MockVisionLLM, VisionAgent
from .orchestrator import Orchestrator

logger = logging.getLogger(__name__)


def _build_orchestrator() -> Orchestrator:
    return Orchestrator(
        solver=SolverAgent(MockSolverLLM()),
        tutor=TutorAgent(MockTutorLLM()),
        vision=VisionAgent(MockVisionLLM()),
    )


orchestrator = _build_orchestrator()


# Request / response wrappers — keep the orchestrator transport-agnostic.

class ProblemRequest(BaseModel):
    session_id: str
    problem_text: str


class MessageRequest(BaseModel):
    session_id: str
    text: str


class StepCompletedRequest(BaseModel):
    session_id: str
    step_n: int


class ErrorRequest(BaseModel):
    session_id: str
    kind: str


def create_app():
    """Lazily build the FastAPI app so the import is optional."""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="Brainer STEM Tutor")

    @app.post("/sessions/{session_id}/problem")
    def post_problem(session_id: str, body: ProblemRequest):
        if session_id != body.session_id:
            raise HTTPException(status_code=400, detail="session_id mismatch")
        resp = orchestrator.on_problem_statement(session_id, body.problem_text)
        return {
            "notes": resp.notes,
            "solved_summary": (
                {
                    "subject": resp.solved.subject,
                    "n_steps": len(resp.solved.steps),
                    "confidence": resp.solved.confidence,
                }
                if resp.solved
                else None
            ),
        }

    @app.post("/sessions/{session_id}/message")
    def post_message(session_id: str, body: MessageRequest):
        resp = orchestrator.on_student_message(session_id, body.text)
        if resp.tutor_turn is None:
            return {"notes": resp.notes, "turn": None}
        return {
            "notes": resp.notes,
            "turn": resp.tutor_turn.model_dump(exclude={"internal_notes"}),
        }

    @app.post("/sessions/{session_id}/step")
    def post_step(session_id: str, body: StepCompletedRequest):
        resp = orchestrator.mark_step_completed(session_id, body.step_n)
        return {"notes": resp.notes}

    @app.post("/sessions/{session_id}/error")
    def post_error(session_id: str, body: ErrorRequest):
        resp = orchestrator.mark_error(session_id, body.kind)
        return {"notes": resp.notes}

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


# Convenience for `uvicorn brainer_stem_tutor.orchestrator.fastapi_app:app`
try:
    app = create_app()
except ImportError:  # pragma: no cover - fastapi missing in slim envs
    app = None
