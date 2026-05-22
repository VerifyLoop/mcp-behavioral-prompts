"""SolvedCache LRU semantics — eviction at boundary."""
from __future__ import annotations

from brainer_stem_tutor.shared.schemas import (
    SolvedProblem,
    Step,
    VerificationRecord,
)
from brainer_stem_tutor.solver.cache import SolvedCache


def _make(answer: str) -> SolvedProblem:
    return SolvedProblem(
        problem_text=f"q-{answer}",
        subject="math",
        steps=[
            Step(n=1, kind="setup", latex="?", justification="g"),
            Step(n=2, kind="answer", latex=answer, justification="g"),
        ],
        final_answer=answer,
        final_answer_numeric=None,
        units=None,
        confidence=0.9,
        verifications=[
            VerificationRecord(tool="sympy_cas", input="i", output="o", passed=True)
        ],
        model_used="t",
    )


class TestSolvedCacheLRU:
    def test_put_get_round_trip(self) -> None:
        cache = SolvedCache(max_entries=4)
        cache.put("p1", _make("1"))
        assert cache.get("p1") is not None

    def test_eviction_removes_oldest(self) -> None:
        cache = SolvedCache(max_entries=3)
        cache.put("p1", _make("1"))
        cache.put("p2", _make("2"))
        cache.put("p3", _make("3"))
        cache.put("p4", _make("4"))   # triggers eviction
        assert len(cache) == 3
        assert cache.get("p1") is None
        assert cache.get("p4") is not None

    def test_putting_existing_key_refreshes_recency(self) -> None:
        cache = SolvedCache(max_entries=3)
        cache.put("p1", _make("a"))
        cache.put("p2", _make("b"))
        cache.put("p3", _make("c"))
        cache.put("p1", _make("a2"))  # refresh -> moves p1 to most recent
        cache.put("p4", _make("d"))   # eviction -> should drop p2, not p1
        assert cache.get("p1") is not None
        assert cache.get("p2") is None

    def test_clear(self) -> None:
        cache = SolvedCache()
        cache.put("p1", _make("1"))
        cache.clear()
        assert len(cache) == 0

    def test_image_hash_namespaces_entries(self) -> None:
        cache = SolvedCache()
        cache.put("p1", _make("1"), image_hash="img-a")
        cache.put("p1", _make("2"), image_hash="img-b")
        a = cache.get("p1", image_hash="img-a")
        b = cache.get("p1", image_hash="img-b")
        assert a is not None and b is not None
        assert a.final_answer != b.final_answer
