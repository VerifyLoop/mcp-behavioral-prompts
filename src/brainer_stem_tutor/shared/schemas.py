"""Cross-layer pydantic schemas.

These models are the contract between solver, tutor, vision and orchestrator.
They are deliberately framework-agnostic (no ADK, no FastAPI imports) so they
can be reused both at runtime and in the eval harness.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Solver layer
# ---------------------------------------------------------------------------


StepKind = Literal[
    "setup",        # problem framing / variables
    "concept",      # invokes a definition or law
    "derivation",   # algebraic / symbolic manipulation
    "computation",  # numerical computation
    "verification", # the model re-checked its own work
    "answer",       # the final answer line
]


class Step(BaseModel):
    """One canonical step of a solution as produced by the solver."""

    n: int = Field(ge=1, description="1-indexed step number")
    kind: StepKind
    latex: str = Field(description="LaTeX expression of the step")
    justification: str = Field(description="Why this step is valid")


class VerificationRecord(BaseModel):
    """A computational verification the solver performed before closing."""

    tool: Literal["python", "sympy_cas", "unit_checker", "wolfram_alpha"]
    input: str
    output: str
    passed: bool
    notes: Optional[str] = None


class SolvedProblem(BaseModel):
    """The full verified solution as produced by the solver layer.

    The orchestrator hands this object — with `final_answer` masked from the
    student — to the tutor agent. Anything that must NEVER leak to the
    student belongs in this model so the moderator can scan for it.
    """

    problem_text: str
    subject: Literal["math", "physics", "chemistry", "other"]
    steps: list[Step]
    final_answer: str = Field(description="Canonical final answer (string)")
    final_answer_numeric: Optional[float] = Field(
        default=None,
        description="Numeric value when the answer reduces to a single number; used by leak detection.",
    )
    units: Optional[str] = Field(default=None, description="Units, e.g. 'm/s^2'")
    confidence: float = Field(ge=0.0, le=1.0)
    verifications: list[VerificationRecord] = Field(default_factory=list)
    model_used: str = Field(default="unknown", description="LLM identifier used to solve")

    @model_validator(mode="after")
    def _at_least_one_verification(self) -> "SolvedProblem":
        if not self.verifications:
            raise ValueError(
                "A SolvedProblem must include at least one VerificationRecord. "
                "The solver is required to verify before closing."
            )
        return self

    @model_validator(mode="after")
    def _steps_are_sequential(self) -> "SolvedProblem":
        for i, s in enumerate(self.steps, start=1):
            if s.n != i:
                raise ValueError(
                    f"Step numbering must be sequential starting at 1; "
                    f"got n={s.n} at position {i}."
                )
        if self.steps and self.steps[-1].kind != "answer":
            raise ValueError("Last step must be of kind 'answer'.")
        return self


# ---------------------------------------------------------------------------
# Vision layer
# ---------------------------------------------------------------------------


class BBox(BaseModel):
    """Normalised bounding box, coordinates in [0, 1]."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _inside_unit_square(self) -> "BBox":
        if self.x + self.w > 1.0 + 1e-6 or self.y + self.h > 1.0 + 1e-6:
            raise ValueError("Bounding box extends outside the unit square.")
        return self


ElementRole = Literal["formula", "symbol", "label", "diagram", "note"]


class VisionElement(BaseModel):
    """One detected element on a page of student notes."""

    id: str
    bbox: BBox
    text: str
    latex: Optional[str] = None
    role: ElementRole
    parent_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class VisionResult(BaseModel):
    """Output of one vision extraction pass for a single image."""

    image_hash: str
    elements: list[VisionElement]
    page_width: int = Field(gt=0)
    page_height: int = Field(gt=0)
    rotation: int = 0

    def by_id(self, element_id: str) -> Optional[VisionElement]:
        return next((e for e in self.elements if e.id == element_id), None)

    @model_validator(mode="after")
    def _unique_ids(self) -> "VisionResult":
        ids = [e.id for e in self.elements]
        if len(ids) != len(set(ids)):
            raise ValueError("Element ids must be unique within a VisionResult.")
        for el in self.elements:
            if el.parent_id is not None and el.parent_id not in ids:
                raise ValueError(
                    f"Element {el.id} references unknown parent_id={el.parent_id}."
                )
        return self


# ---------------------------------------------------------------------------
# Tutor layer
# ---------------------------------------------------------------------------


class ActionKind(str, Enum):
    ASK_QUESTION = "ask_question"
    HIGHLIGHT_BBOXES = "highlight_bboxes"
    REQUEST_DRAWING = "request_drawing"
    SHOW_QUIZ = "show_quiz"
    SHOW_DIAGRAM = "show_diagram"
    CONFIRM_STEP = "confirm_step"


class TutorAction(BaseModel):
    """A structured action the frontend interprets.

    Using a single discriminated union keeps the WS protocol simple: the
    frontend just dispatches on `kind`.
    """

    kind: ActionKind
    text: Optional[str] = None
    bbox_ids: list[str] = Field(default_factory=list)
    color: Optional[str] = None
    choices: list[str] = Field(default_factory=list)
    correct_idx: Optional[int] = None
    diagram_url: Optional[str] = None
    step_n: Optional[int] = None

    @model_validator(mode="after")
    def _payload_matches_kind(self) -> "TutorAction":
        if self.kind in (ActionKind.ASK_QUESTION, ActionKind.REQUEST_DRAWING):
            if not self.text:
                raise ValueError(f"{self.kind} requires `text`.")
        if self.kind == ActionKind.HIGHLIGHT_BBOXES and not self.bbox_ids:
            raise ValueError("highlight_bboxes requires at least one bbox id.")
        if self.kind == ActionKind.SHOW_QUIZ:
            if not self.text or len(self.choices) < 2 or self.correct_idx is None:
                raise ValueError("show_quiz requires text, >=2 choices, and correct_idx.")
            if not (0 <= self.correct_idx < len(self.choices)):
                raise ValueError("correct_idx out of range.")
        if self.kind == ActionKind.SHOW_DIAGRAM and not self.diagram_url:
            raise ValueError("show_diagram requires diagram_url.")
        if self.kind == ActionKind.CONFIRM_STEP and self.step_n is None:
            raise ValueError("confirm_step requires step_n.")
        return self


class TutorTurn(BaseModel):
    """The full output of one tutor turn.

    `student_facing_message` is everything the student sees verbatim.
    `actions` is the structured UI plan.
    `internal_notes` never reaches the student — used by eval and replay.
    """

    student_facing_message: str
    actions: list[TutorAction] = Field(default_factory=list)
    internal_notes: str = ""


# ---------------------------------------------------------------------------
# Student-side signals (input to follow policy)
# ---------------------------------------------------------------------------


class StudentTurn(BaseModel):
    """One message from the student."""

    text: str
    ts: float = Field(description="UNIX timestamp seconds")


class StudentSignals(BaseModel):
    """Structured signals that drive the tutor follow policy.

    These are computed by the orchestrator from session history. They are
    deliberately *not* LLM-generated so the policy is auditable.
    """

    attempts_count: int = Field(ge=0, default=0)
    last_correct_step: int = Field(ge=0, default=0)
    time_on_step_seconds: float = Field(ge=0.0, default=0.0)
    frustration_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="0 = calm, 1 = very frustrated. Heuristic, not LLM.",
    )
    last_error_kind: Optional[Literal["sign", "unit", "concept", "arithmetic"]] = None
    image_progress_delta: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="How much the latest snapshot differs from the previous one.",
    )
