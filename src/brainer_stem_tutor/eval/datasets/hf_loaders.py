"""HuggingFace-shaped loaders for GSM8K and MATH.

Both functions accept a JSONL file with the canonical HF fields and return
EvalProblem objects ready for the runner. Splitting the loader from the HF
fetch means our test suite can ship a tiny offline subset without depending
on `datasets` or network access; production runs can do
`datasets.load_dataset("openai/gsm8k", "main", split="test").to_pandas()
.to_json(...)` and feed the result here.

GSM8K (`openai/gsm8k`):
  fields: question (str), answer (str ending with "#### <number>")

MATH (`EleutherAI/hendrycks_math`):
  fields: problem, level (e.g. "Level 3"), type, solution (LaTeX with \\boxed)
"""
from __future__ import annotations

import json
from pathlib import Path

from ..scorers import extract_boxed_answer, extract_gsm8k_answer
from .loaders import EvalProblem


def load_gsm8k_jsonl(path: str | Path) -> list[EvalProblem]:
    items: list[EvalProblem] = []
    p = Path(path)
    for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines()):
        raw = raw.strip()
        if not raw:
            continue
        obj = json.loads(raw)
        gold = extract_gsm8k_answer(obj["answer"]) or ""
        try:
            num = float(gold) if gold else None
        except ValueError:
            num = None
        items.append(
            EvalProblem(
                id=f"gsm8k-{i}",
                subject="math",
                problem_text=obj["question"],
                expected_answer=gold,
                expected_numeric=num,
                difficulty=2,
                source="gsm8k",
            )
        )
    return items


def load_math_jsonl(path: str | Path) -> list[EvalProblem]:
    items: list[EvalProblem] = []
    p = Path(path)
    for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines()):
        raw = raw.strip()
        if not raw:
            continue
        obj = json.loads(raw)
        gold = extract_boxed_answer(obj["solution"]) or ""
        try:
            num = float(gold) if gold else None
        except ValueError:
            num = None
        level_str = obj.get("level", "Level 1")
        difficulty = int(level_str.split()[-1]) if level_str.split()[-1].isdigit() else 1
        items.append(
            EvalProblem(
                id=f"math-{i}",
                subject="math",
                problem_text=obj["problem"],
                expected_answer=gold,
                expected_numeric=num,
                difficulty=difficulty,
                source=f"hendrycks-math/{obj.get('type', 'unknown')}",
            )
        )
    return items
