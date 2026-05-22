"""Cache of vision extractions keyed by image hash."""
from __future__ import annotations

from ..shared.schemas import VisionResult


class VisionCache:
    """LRU-ish cache mapping image_hash -> VisionResult.

    Keeps a per-image entry for both granularities (coarse / fine) so the
    tutor can request fine breakdown without invalidating coarse results.
    """

    def __init__(self, max_entries: int = 256) -> None:
        self._max = max_entries
        self._store: dict[tuple[str, str], VisionResult] = {}
        self._order: list[tuple[str, str]] = []

    @staticmethod
    def _key(image_hash: str, granularity: str) -> tuple[str, str]:
        return (image_hash, granularity)

    def get(self, image_hash: str, granularity: str = "coarse") -> VisionResult | None:
        return self._store.get(self._key(image_hash, granularity))

    def put(
        self,
        image_hash: str,
        result: VisionResult,
        granularity: str = "coarse",
    ) -> None:
        k = self._key(image_hash, granularity)
        if k in self._store:
            self._order.remove(k)
        self._store[k] = result
        self._order.append(k)
        while len(self._order) > self._max:
            evict = self._order.pop(0)
            self._store.pop(evict, None)

    def __len__(self) -> int:
        return len(self._store)
