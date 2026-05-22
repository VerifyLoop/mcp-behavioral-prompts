"""Dataset loaders for the eval harness.

The production runner pulls MATH / GSM8K / OlympiadBench / JEEBench via
HuggingFace. To keep the test harness self-contained we ship a small builtin
dataset of arithmetic / equation / physics problems whose answers we know
exactly, plus a `load_problems("path/to/file.jsonl")` for custom sets.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


Subject = Literal["math", "physics", "chemistry", "other"]


@dataclass(frozen=True)
class EvalProblem:
    id: str
    subject: Subject
    problem_text: str
    expected_answer: str
    expected_numeric: Optional[float] = None
    expected_units: Optional[str] = None
    difficulty: int = 1   # 1-5, MATH-style levels
    source: str = "builtin"


BUILTIN_DATASETS: dict[str, list[EvalProblem]] = {
    "smoke": [
        EvalProblem(
            id="smoke-1",
            subject="math",
            problem_text="What is 2+2?",
            expected_answer="4",
            expected_numeric=4.0,
            difficulty=1,
        ),
        EvalProblem(
            id="smoke-2",
            subject="math",
            problem_text="What is 7*6?",
            expected_answer="42",
            expected_numeric=42.0,
            difficulty=1,
        ),
        EvalProblem(
            id="smoke-3",
            subject="math",
            problem_text="Solve 3*x - 12 = 0 for x",
            expected_answer="[4]",
            expected_numeric=4.0,
            difficulty=2,
        ),
        EvalProblem(
            id="smoke-4",
            subject="physics",
            problem_text=(
                "An object accelerates at 2 m/s^2 starting from rest for 5 seconds. "
                "What is its velocity?"
            ),
            expected_answer="10",
            expected_numeric=10.0,
            expected_units="m/s",
            difficulty=2,
        ),
        EvalProblem(
            id="smoke-5",
            subject="physics",
            problem_text=(
                "An object accelerates at 9.8 m/s^2 starting from rest for 3 seconds. "
                "What is its velocity?"
            ),
            expected_answer="29.4",
            expected_numeric=29.4,
            expected_units="m/s",
            difficulty=2,
        ),
    ],
    "italian_liceo": [
        EvalProblem(
            id="it-liceo-1",
            subject="math",
            problem_text="Risolvi 2*x - 10 = 0 per x",
            expected_answer="[5]",
            expected_numeric=5.0,
            difficulty=1,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-2",
            subject="physics",
            problem_text=(
                "Un corpo accelera at 3 m/s^2 starting from rest for 4 seconds. "
                "Quanto vale la velocita?"
            ),
            # Note: mock LLM is keyed on English phrasing; mixing languages tests
            # how the eval surfaces unsupported inputs.
            expected_answer="12",
            expected_numeric=12.0,
            expected_units="m/s",
            difficulty=2,
            source="italian-liceo",
        ),
    ],
}


def load_problems(source: str) -> list[EvalProblem]:
    """Load a dataset by name (BUILTIN_DATASETS key) or path to JSONL.

    JSONL format: one EvalProblem per line, with the same fields as the
    dataclass.
    """
    if source in BUILTIN_DATASETS:
        return list(BUILTIN_DATASETS[source])
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Unknown dataset: {source}")
    problems: list[EvalProblem] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            problems.append(EvalProblem(**obj))
    return problems
