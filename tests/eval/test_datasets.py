"""Dataset loader tests."""
from __future__ import annotations

import json

import pytest

from brainer_stem_tutor.eval.datasets import BUILTIN_DATASETS, EvalProblem, load_problems


class TestBuiltinDatasets:
    def test_smoke_has_problems(self) -> None:
        ps = load_problems("smoke")
        assert len(ps) >= 5
        for p in ps:
            assert isinstance(p, EvalProblem)

    def test_italian_liceo_present(self) -> None:
        ps = load_problems("italian_liceo")
        assert any(p.source == "italian-liceo" for p in ps)


class TestJSONLLoader:
    def test_load_jsonl(self, tmp_path) -> None:
        p = tmp_path / "ds.jsonl"
        p.write_text(
            json.dumps(
                {
                    "id": "x",
                    "subject": "math",
                    "problem_text": "What is 1+1?",
                    "expected_answer": "2",
                    "expected_numeric": 2.0,
                    "expected_units": None,
                    "difficulty": 1,
                    "source": "custom",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        loaded = load_problems(str(p))
        assert len(loaded) == 1
        assert loaded[0].id == "x"

    def test_unknown_source_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_problems("not-a-dataset")
