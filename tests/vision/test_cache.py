"""VisionCache LRU + granularity separation tests."""
from __future__ import annotations

from brainer_stem_tutor.shared.schemas import VisionResult
from brainer_stem_tutor.vision.cache import VisionCache


def _result(h: str) -> VisionResult:
    return VisionResult(
        image_hash=h,
        elements=[],
        page_width=100,
        page_height=100,
    )


class TestVisionCacheLRU:
    def test_granularity_separation(self) -> None:
        cache = VisionCache()
        cache.put("h1", _result("h1"), "coarse")
        cache.put("h1", _result("h1"), "fine")
        assert cache.get("h1", "coarse") is not None
        assert cache.get("h1", "fine") is not None

    def test_eviction(self) -> None:
        cache = VisionCache(max_entries=2)
        cache.put("h1", _result("h1"), "coarse")
        cache.put("h2", _result("h2"), "coarse")
        cache.put("h3", _result("h3"), "coarse")
        assert cache.get("h1", "coarse") is None
        assert cache.get("h3", "coarse") is not None

    def test_overwrite_refreshes_order(self) -> None:
        cache = VisionCache(max_entries=2)
        cache.put("h1", _result("h1"))
        cache.put("h2", _result("h2"))
        cache.put("h1", _result("h1"))  # refresh
        cache.put("h3", _result("h3"))  # h2 should evict
        assert cache.get("h1") is not None
        assert cache.get("h2") is None

    def test_len(self) -> None:
        cache = VisionCache()
        assert len(cache) == 0
        cache.put("h1", _result("h1"))
        cache.put("h1", _result("h1"), "fine")
        assert len(cache) == 2
