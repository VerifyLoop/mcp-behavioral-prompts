"""In-memory cache of solved problems.

Keyed on (problem_text, image_hash). Saves cost when the same student asks
about the same exercise twice in a session.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from ..shared.schemas import SolvedProblem


def _key(problem_text: str, image_hash: Optional[str]) -> str:
    h = hashlib.sha256()
    h.update(problem_text.strip().encode("utf-8"))
    h.update(b"|")
    h.update((image_hash or "").encode("utf-8"))
    return h.hexdigest()


class SolvedCache:
    """Thread-unsafe in-memory cache. Swap with Redis in prod."""

    def __init__(self, max_entries: int = 1024) -> None:
        self._max = max_entries
        self._store: dict[str, SolvedProblem] = {}
        self._order: list[str] = []

    def get(self, problem_text: str, image_hash: Optional[str] = None) -> Optional[SolvedProblem]:
        return self._store.get(_key(problem_text, image_hash))

    def put(
        self,
        problem_text: str,
        solved: SolvedProblem,
        image_hash: Optional[str] = None,
    ) -> None:
        k = _key(problem_text, image_hash)
        if k in self._store:
            self._order.remove(k)
        self._store[k] = solved
        self._order.append(k)
        while len(self._order) > self._max:
            evict = self._order.pop(0)
            self._store.pop(evict, None)

    def __len__(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
        self._order.clear()
