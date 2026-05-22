"""GSM8K + MATH JSONL loaders."""
from __future__ import annotations

import json

from brainer_stem_tutor.eval.datasets.hf_loaders import (
    load_gsm8k_jsonl,
    load_math_jsonl,
)


def _write_jsonl(path, items):
    path.write_text("\n".join(json.dumps(i) for i in items) + "\n", encoding="utf-8")


class TestGSM8KLoader:
    def test_loads_canonical_fields(self, tmp_path) -> None:
        p = tmp_path / "gsm.jsonl"
        _write_jsonl(
            p,
            [
                {"question": "John has 3 apples and buys 2 more. How many?", "answer": "3+2=5\n#### 5"},
                {"question": "What is 10*10?", "answer": "100\n#### 100"},
            ],
        )
        problems = load_gsm8k_jsonl(p)
        assert len(problems) == 2
        assert problems[0].expected_numeric == 5.0
        assert problems[1].expected_numeric == 100.0
        assert all(p.source == "gsm8k" for p in problems)


class TestMATHLoader:
    def test_loads_canonical_fields(self, tmp_path) -> None:
        p = tmp_path / "math.jsonl"
        _write_jsonl(
            p,
            [
                {
                    "problem": "Find x.",
                    "level": "Level 3",
                    "type": "algebra",
                    "solution": "Setting up... $\\boxed{42}$.",
                },
                {
                    "problem": "Compute something.",
                    "level": "Level 5",
                    "type": "calculus",
                    "solution": "After work, $\\boxed{\\frac{1}{2}}$.",
                },
            ],
        )
        problems = load_math_jsonl(p)
        assert len(problems) == 2
        assert problems[0].difficulty == 3
        assert problems[0].expected_answer == "42"
        assert problems[1].difficulty == 5
        assert problems[1].expected_answer == "\\frac{1}{2}"
        assert problems[0].source == "hendrycks-math/algebra"
