"""Vision agent: image bytes -> VisionResult.

Real implementation: Gemini 3 Flash with response_schema enforcing the
shape. Mock implementation: takes a pre-rendered dict and returns it. The
agent layer handles caching and hash computation so neither LLM has to.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional, Protocol

from ..shared.schemas import BBox, VisionElement, VisionResult
from .cache import VisionCache

logger = logging.getLogger(__name__)


def image_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


class VisionLLMProtocol(Protocol):
    """The LLM contract: take image bytes, return raw element dicts."""

    @property
    def model_id(self) -> str:  # pragma: no cover - protocol
        ...

    def extract(
        self,
        image_bytes: bytes,
        granularity: str = "coarse",
    ) -> dict:  # pragma: no cover - protocol
        ...


class MockVisionLLM:
    """Pre-canned responses keyed by image hash.

    Used by tests and the demo. A real Gemini-backed implementation would
    replace this — same signature, same return shape.
    """

    model_id = "mock-vision-v1"

    def __init__(self) -> None:
        self._fixtures: dict[tuple[str, str], dict] = {}

    def register(self, image_bytes: bytes, granularity: str, payload: dict) -> None:
        self._fixtures[(image_hash(image_bytes), granularity)] = payload

    def extract(self, image_bytes: bytes, granularity: str = "coarse") -> dict:
        key = (image_hash(image_bytes), granularity)
        if key not in self._fixtures:
            raise KeyError(f"No fixture registered for {key}")
        return self._fixtures[key]


class VisionAgent:
    """Caches around the LLM and converts dicts to validated VisionResult."""

    def __init__(
        self,
        llm: VisionLLMProtocol,
        cache: Optional[VisionCache] = None,
    ) -> None:
        self._llm = llm
        self._cache = cache if cache is not None else VisionCache()

    def extract(
        self,
        image_bytes: bytes,
        granularity: str = "coarse",
    ) -> VisionResult:
        h = image_hash(image_bytes)
        cached = self._cache.get(h, granularity)
        if cached is not None:
            logger.debug("vision cache hit %s/%s", h[:8], granularity)
            return cached
        raw = self._llm.extract(image_bytes, granularity=granularity)
        raw = dict(raw)
        raw.setdefault("image_hash", h)
        result = VisionResult.model_validate(raw)
        self._cache.put(h, result, granularity)
        return result

    @staticmethod
    def build_step_to_bbox_mapping(
        result: VisionResult,
        step_keywords: dict[int, list[str]],
    ) -> dict[int, list[str]]:
        """Heuristic: for each step, pick the bbox whose text best matches.

        `step_keywords[n]` is a list of substrings — if any of them appears in
        an element's text, that element's id is associated with step n. Used
        by the orchestrator to bridge solver steps to vision elements when
        the LLM hasn't explicitly tagged them.
        """
        mapping: dict[int, list[str]] = {}
        for n, kws in step_keywords.items():
            ids = []
            for el in result.elements:
                hay = (el.text + " " + (el.latex or "")).lower()
                if any(k.lower() in hay for k in kws):
                    ids.append(el.id)
            if ids:
                mapping[n] = ids
        return mapping
