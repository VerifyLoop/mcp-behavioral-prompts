"""Tests for the vision agent and its cache."""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.schemas import VisionResult
from brainer_stem_tutor.vision import MockVisionLLM, VisionAgent, VisionCache, image_hash


@pytest.fixture
def sample_image() -> bytes:
    return b"PNG-fixture-bytes-not-a-real-image"


@pytest.fixture
def coarse_payload(sample_image) -> dict:
    return {
        "image_hash": image_hash(sample_image),
        "elements": [
            {
                "id": "bbox_0",
                "bbox": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.05},
                "text": "F = m a",
                "latex": "F = m \\cdot a",
                "role": "formula",
                "parent_id": None,
                "confidence": 0.94,
            },
            {
                "id": "bbox_1",
                "bbox": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.05},
                "text": "v = a t",
                "latex": "v = a \\cdot t",
                "role": "formula",
                "parent_id": None,
                "confidence": 0.93,
            },
        ],
        "page_width": 1080,
        "page_height": 1920,
        "rotation": 0,
    }


class TestVisionAgent:
    def test_extract_validates_and_caches(self, sample_image, coarse_payload) -> None:
        llm = MockVisionLLM()
        llm.register(sample_image, "coarse", coarse_payload)
        cache = VisionCache()
        agent = VisionAgent(llm, cache=cache)
        result = agent.extract(sample_image)
        assert isinstance(result, VisionResult)
        assert len(result.elements) == 2
        assert len(cache) == 1
        # Second call: must hit cache, no extra fixture needed.
        cached = agent.extract(sample_image)
        assert cached is result

    def test_extract_auto_fills_image_hash(self, sample_image) -> None:
        llm = MockVisionLLM()
        payload = {
            "elements": [],
            "page_width": 100,
            "page_height": 100,
            "rotation": 0,
        }
        llm.register(sample_image, "coarse", payload)
        agent = VisionAgent(llm)
        result = agent.extract(sample_image)
        assert result.image_hash == image_hash(sample_image)

    def test_step_to_bbox_mapping_by_keywords(self, sample_image, coarse_payload) -> None:
        llm = MockVisionLLM()
        llm.register(sample_image, "coarse", coarse_payload)
        agent = VisionAgent(llm)
        result = agent.extract(sample_image)
        mapping = VisionAgent.build_step_to_bbox_mapping(
            result,
            step_keywords={1: ["F = m a", "m a"], 2: ["v = a t"]},
        )
        assert mapping[1] == ["bbox_0"]
        assert mapping[2] == ["bbox_1"]
