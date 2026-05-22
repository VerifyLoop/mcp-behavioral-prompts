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
from typing import Literal

Subject = Literal["math", "physics", "chemistry", "other"]


@dataclass(frozen=True)
class EvalProblem:
    id: str
    subject: Subject
    problem_text: str
    expected_answer: str
    expected_numeric: float | None = None
    expected_units: str | None = None
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
        # Arithmetic / basic algebra (Liceo Scientifico, biennio)
        EvalProblem(
            id="it-liceo-1",
            subject="math",
            problem_text="What is 17 + 26?",
            expected_answer="43",
            expected_numeric=43.0,
            difficulty=1,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-2",
            subject="math",
            problem_text="What is 12 * 15?",
            expected_answer="180",
            expected_numeric=180.0,
            difficulty=1,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-3",
            subject="math",
            problem_text="Solve 3*x - 21 = 0 for x",
            expected_answer="[7]",
            expected_numeric=7.0,
            difficulty=1,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-4",
            subject="math",
            problem_text="Solve 5*x + 10 = 0 for x",
            expected_answer="[-2]",
            expected_numeric=-2.0,
            difficulty=1,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-5",
            subject="math",
            problem_text="Solve x**2 - 25 = 0 for x",
            expected_answer="[-5, 5]",
            expected_numeric=None,
            difficulty=2,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-6",
            subject="math",
            problem_text="Solve x**2 - 4*x + 4 = 0 for x",
            expected_answer="[2]",
            expected_numeric=2.0,
            difficulty=2,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-7",
            subject="math",
            problem_text="Solve x**2 + 1 = 0 for x",
            expected_answer="[]",  # no real solutions
            expected_numeric=None,
            difficulty=3,
            source="italian-liceo",
        ),
        # Kinematics (Liceo Scientifico, primo anno fisica)
        EvalProblem(
            id="it-liceo-8",
            subject="physics",
            problem_text=(
                "An object accelerates at 3 m/s^2 starting from rest for 4 seconds. "
                "What is its velocity?"
            ),
            expected_answer="12",
            expected_numeric=12.0,
            expected_units="m/s",
            difficulty=2,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-9",
            subject="physics",
            problem_text=(
                "An object accelerates at 9.81 m/s^2 starting from rest for 2 seconds. "
                "What is its velocity?"
            ),
            expected_answer="19.62",
            expected_numeric=19.62,
            expected_units="m/s",
            difficulty=2,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-10",
            subject="physics",
            problem_text=(
                "An object accelerates at 0.5 m/s^2 starting from rest for 60 seconds. "
                "What is its velocity?"
            ),
            expected_answer="30.0",
            expected_numeric=30.0,
            expected_units="m/s",
            difficulty=2,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-11",
            subject="physics",
            problem_text=(
                "An object accelerates at 2.5 m/s^2 starting from rest for 10 seconds. "
                "What is its velocity?"
            ),
            expected_answer="25.0",
            expected_numeric=25.0,
            expected_units="m/s",
            difficulty=2,
            source="italian-liceo",
        ),
        EvalProblem(
            id="it-liceo-12",
            subject="physics",
            problem_text=(
                "An object accelerates at 4 m/s^2 starting from rest for 8 seconds. "
                "What is its velocity?"
            ),
            expected_answer="32",
            expected_numeric=32.0,
            expected_units="m/s",
            difficulty=2,
            source="italian-liceo",
        ),
        # Edge cases — solver should fail cleanly, not silently:
        EvalProblem(
            id="it-liceo-13",
            subject="math",
            problem_text="Find x such that 7*x = 49",  # phrasing not matched by mock
            expected_answer="7",
            expected_numeric=7.0,
            difficulty=1,
            source="italian-liceo-edge",
        ),
        EvalProblem(
            id="it-liceo-14",
            subject="math",
            problem_text="Compute the value of (10 - 4)*3",  # parens unsupported by mock
            expected_answer="18",
            expected_numeric=18.0,
            difficulty=1,
            source="italian-liceo-edge",
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
