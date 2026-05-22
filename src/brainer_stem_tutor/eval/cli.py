"""CLI for the eval harness.

Usage:
    python -m brainer_stem_tutor.eval.cli --dataset smoke
    python -m brainer_stem_tutor.eval.cli --dataset italian_liceo --tutor

Prints a compact, plain-text report. CI hooks: when ``--ci`` is passed, exit
code is non-zero if a configured floor isn't met.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from ..orchestrator import Orchestrator
from ..solver import MockSolverLLM, SolverAgent
from ..tutor import MockTutorLLM, TutorAgent
from ..tutor.moderator import LeakModerator
from ..vision import MockVisionLLM, VisionAgent
from .datasets import load_problems
from .metrics import SolverMetrics, TutorMetrics
from .runners import SolverRunner, TutorRunner


def _build_default_orchestrator() -> Orchestrator:
    return Orchestrator(
        solver=SolverAgent(MockSolverLLM()),
        tutor=TutorAgent(MockTutorLLM()),
        vision=VisionAgent(MockVisionLLM()),
    )


def _format_solver(m: SolverMetrics) -> str:
    return (
        f"  n={m.n} acc={m.accuracy:.2f} acc_verified={m.accuracy_with_verification:.2f} "
        f"mean_conf={m.mean_confidence:.2f} brier={m.brier:.3f} "
        f"mean_verifs={m.mean_verifications:.1f} mean_steps={m.mean_steps:.1f} "
        f"failures={m.failure_count}"
    )


def _format_tutor(m: TutorMetrics) -> str:
    return (
        f"  n={m.n} leak_rate={m.leak_rate:.3f} leaks={m.leak_count} "
        f"by_persona={m.persona_breakdown} mean_chars={m.mean_message_chars:.1f}"
    )


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="brainer-tutor-eval")
    parser.add_argument(
        "--dataset",
        default="smoke",
        help="Dataset key (smoke, italian_liceo) or path to a JSONL file.",
    )
    parser.add_argument(
        "--tutor",
        action="store_true",
        help="Also run the tutor evaluation with simulated personas.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of plain text.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Apply pass/fail gates: acc>=0.8, leak_rate==0.0; exit 1 on fail.",
    )
    parser.add_argument("--out", type=Path, help="Write report to this file too.")
    args = parser.parse_args(argv)

    problems = load_problems(args.dataset)
    report: dict = {"dataset": args.dataset, "n_problems": len(problems)}

    orch = _build_default_orchestrator()
    runner = SolverRunner(orch._solver, config_name="C0_mock")  # type: ignore[attr-defined]
    solver_run = runner.run(problems)
    report["solver"] = asdict(solver_run.metrics)

    if args.tutor:
        moderator = LeakModerator()
        tutor_runner = TutorRunner(orch, moderator, config_name="C0_mock")
        tutor_run = tutor_runner.run(problems)
        report["tutor"] = asdict(tutor_run.metrics)

    if args.json:
        out = json.dumps(report, indent=2)
    else:
        lines = [
            f"# brainer-stem-tutor eval report",
            f"dataset: {args.dataset}  n_problems: {len(problems)}",
            f"solver ({solver_run.config_name}):",
            _format_solver(solver_run.metrics),
        ]
        if args.tutor:
            lines.append(f"tutor ({tutor_run.config_name}):")  # type: ignore[name-defined]
            lines.append(_format_tutor(tutor_run.metrics))  # type: ignore[name-defined]
        out = "\n".join(lines)

    print(out)
    if args.out:
        args.out.write_text(out + "\n", encoding="utf-8")

    if args.ci:
        m = solver_run.metrics
        if m.accuracy < 0.8:
            print(f"FAIL: solver accuracy {m.accuracy:.2f} < 0.80", file=sys.stderr)
            return 1
        if args.tutor and tutor_run.metrics.leak_rate > 0.0:  # type: ignore[name-defined]
            print(f"FAIL: tutor leak_rate > 0", file=sys.stderr)
            return 1
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
