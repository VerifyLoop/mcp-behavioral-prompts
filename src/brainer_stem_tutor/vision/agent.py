"""Vision agent: image bytes -> VisionResult.

Real implementation: Gemini 3 Flash with response_schema enforcing the
shape. Mock implementation: takes a pre-rendered dict and returns it. The
agent layer handles caching and hash computation so neither LLM has to.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Protocol

from ..shared.schemas import BBox, VisionResult
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
        cache: VisionCache | None = None,
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
        raw = self._normalise_gemini_payload(dict(raw), h)
        result = VisionResult.model_validate(raw)
        self._cache.put(h, result, granularity)
        return result

    # ---- Gemini compatibility ---------------------------------------------

    @staticmethod
    def _normalise_gemini_payload(raw: dict, image_hash_value: str) -> dict:
        """Convert Gemini-native `box_2d` + `page_meta` shapes to our schema.

        Accepts BOTH shapes so a real Gemini call and an in-process mock can
        share the same VisionAgent without each having to know what the
        other emits:

        - Gemini-native: elements carry `box_2d=[y_min, x_min, y_max, x_max]`
          in 0-1000 integers, and the wrapper has `page_meta.width/height`.
        - Internal: elements carry `bbox={x,y,w,h}` in 0-1 floats and the
          wrapper has top-level `page_width/page_height`.
        """

        raw.setdefault("image_hash", image_hash_value)

        if "page_meta" in raw and isinstance(raw["page_meta"], dict):
            meta = raw.pop("page_meta")
            raw.setdefault("page_width", int(meta.get("width", raw.get("page_width", 1))))
            raw.setdefault("page_height", int(meta.get("height", raw.get("page_height", 1))))
            if "rotation" in meta and "rotation" not in raw:
                raw["rotation"] = int(meta["rotation"])

        elements = raw.get("elements", [])
        for el in elements:
            if "box_2d" in el and "bbox" not in el:
                el["bbox"] = BBox.from_gemini_box_2d(el.pop("box_2d")).model_dump()
        return raw

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
