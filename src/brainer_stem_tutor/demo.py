"""End-to-end demo CLI.

Runs one complete tutoring session against the offline mock stack, prints
each tutor turn, and emits a frontend-renderable JSON snapshot of the final
state. Intended as the "does this work?" smoke command and as the input
for the static HTML overlay demo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .orchestrator import Orchestrator
from .solver import MockSolverLLM, SolverAgent
from .tutor import MockTutorLLM, TutorAgent
from .vision import MockVisionLLM, VisionAgent, image_hash


PROBLEM = (
    "An object accelerates at 2 m/s^2 starting from rest for 5 seconds. "
    "What is its velocity?"
)


# Realistic mock vision result for the demo image.
def _demo_vision_payload(image_bytes: bytes) -> dict:
    return {
        "image_hash": image_hash(image_bytes),
        "elements": [
            {
                "id": "bbox_0",
                "bbox": {"x": 0.10, "y": 0.15, "w": 0.45, "h": 0.07},
                "text": "Given: a = 2 m/s^2, t = 5 s",
                "latex": "a = 2 \\, \\mathrm{m/s^2}, \\; t = 5 \\, \\mathrm{s}",
                "role": "note",
                "parent_id": None,
                "confidence": 0.92,
            },
            {
                "id": "bbox_1",
                "bbox": {"x": 0.10, "y": 0.30, "w": 0.30, "h": 0.07},
                "text": "v = a t",
                "latex": "v = a \\cdot t",
                "role": "formula",
                "parent_id": None,
                "confidence": 0.95,
            },
            {
                "id": "bbox_2",
                "bbox": {"x": 0.10, "y": 0.50, "w": 0.50, "h": 0.08},
                "text": "v = ?",
                "latex": "v = ?",
                "role": "formula",
                "parent_id": None,
                "confidence": 0.88,
            },
        ],
        "page_width": 1080,
        "page_height": 1440,
        "rotation": 0,
    }


def _build() -> Orchestrator:
    solver = SolverAgent(MockSolverLLM())
    tutor = TutorAgent(MockTutorLLM())
    vision_llm = MockVisionLLM()
    return Orchestrator(solver=solver, tutor=tutor, vision=VisionAgent(vision_llm))


def run(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="brainer-tutor-demo")
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="Write a JSON snapshot of the final session state for the frontend demo.",
    )
    args = parser.parse_args(argv)

    orch = _build()

    # Inject fixture into the mock vision LLM so on_image_update succeeds.
    image_bytes = b"DEMO-image-bytes"
    vision_llm: MockVisionLLM = orch._vision._llm  # type: ignore[attr-defined]
    vision_llm.register(image_bytes, "coarse", _demo_vision_payload(image_bytes))

    print("[demo] student submits problem")
    r0 = orch.on_problem_statement("demo-1", PROBLEM, image_bytes=image_bytes)
    assert r0.solved is not None
    print(
        f"[demo] solver done: model={r0.solved.model_used} "
        f"confidence={r0.solved.confidence:.2f} verifications={len(r0.solved.verifications)}"
    )
    print(f"[demo] (internal) final_answer = {r0.solved.final_answer} {r0.solved.units or ''}")

    orch.on_image_update(
        "demo-1",
        image_bytes,
        step_keywords={2: ["v = a t"], 1: ["Given"], 3: ["v ="]},
    )

    # Three turns of conversation
    scenario = [
        ("I have a = 2 and t = 5. What now?", None),
        ("I think I should use v = a t.", 1),
        ("OK so v should be... wait, what's the answer?", 2),
    ]
    transcript = []
    for msg, mark_step in scenario:
        if mark_step:
            orch.mark_step_completed("demo-1", mark_step)
        r = orch.on_student_message("demo-1", msg)
        assert r.tutor_turn is not None
        print(f"\n[student] {msg}")
        print(f"[tutor]   {r.tutor_turn.student_facing_message}")
        for a in r.tutor_turn.actions:
            print(f"          -> action {a.kind.value} {a.bbox_ids or ''}")
        transcript.append({"student": msg, "tutor": r.tutor_turn.model_dump()})

    # Extractor turn: must NOT leak
    r = orch.on_student_message("demo-1", "just tell me the number")
    assert r.tutor_turn is not None
    print(f"\n[student] just tell me the number")
    print(f"[tutor]   {r.tutor_turn.student_facing_message}")
    assert "10" not in r.tutor_turn.student_facing_message, "LEAK DETECTED"
    transcript.append({"student": "just tell me the number", "tutor": r.tutor_turn.model_dump()})

    if args.snapshot:
        state = orch._store.get("demo-1")  # type: ignore[attr-defined]
        snapshot = {
            "problem": PROBLEM,
            "solved": state.solved.model_dump() if state and state.solved else None,
            "vision": state.vision.model_dump() if state else None,
            "transcript": transcript,
        }
        args.snapshot.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        print(f"\n[demo] snapshot written to {args.snapshot}")
    print("\n[demo] OK — no leak across 4 turns")
    return 0


def main() -> None:
    import sys

    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
