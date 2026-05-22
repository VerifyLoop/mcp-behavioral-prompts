"""Gemini-native payload acceptance: box_2d + page_meta shapes."""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.schemas import BBox, VisionResult
from brainer_stem_tutor.vision import MockVisionLLM, VisionAgent, image_hash


class TestBBoxGemini:
    def test_from_gemini_box_2d(self) -> None:
        # Gemini emits [y_min, x_min, y_max, x_max] in 0-1000
        b = BBox.from_gemini_box_2d([100, 200, 300, 600])
        assert b.x == 0.2
        assert b.y == 0.1
        assert b.w == 0.4
        assert b.h == 0.2

    def test_round_trip(self) -> None:
        b = BBox(x=0.1, y=0.2, w=0.3, h=0.4)
        box_2d = b.to_gemini_box_2d()
        b2 = BBox.from_gemini_box_2d(box_2d)
        assert abs(b2.x - b.x) < 1e-3
        assert abs(b2.y - b.y) < 1e-3
        assert abs(b2.w - b.w) < 1e-3
        assert abs(b2.h - b.h) < 1e-3

    def test_invalid_length_rejected(self) -> None:
        with pytest.raises(ValueError):
            BBox.from_gemini_box_2d([1, 2, 3])

    def test_non_positive_extent_rejected(self) -> None:
        with pytest.raises(ValueError):
            BBox.from_gemini_box_2d([200, 200, 100, 100])

    def test_to_pixels(self) -> None:
        b = BBox(x=0.1, y=0.2, w=0.3, h=0.4)
        assert b.to_pixels(1000, 1000) == (100, 200, 400, 600)


class TestVisionAgentGeminiPayload:
    def test_accepts_gemini_native_shape(self) -> None:
        img = b"img-bytes"
        llm = MockVisionLLM()
        llm.register(
            img,
            "coarse",
            {
                "elements": [
                    {
                        "id": "bbox_0",
                        "box_2d": [100, 200, 300, 600],
                        "text": "F = m a",
                        "latex": "F = m \\cdot a",
                        "role": "formula",
                        "parent_id": None,
                        "confidence": 0.95,
                    }
                ],
                "page_meta": {"width": 1080, "height": 1920, "rotation": 0},
            },
        )
        agent = VisionAgent(llm)
        result = agent.extract(img)
        assert isinstance(result, VisionResult)
        assert result.page_width == 1080
        assert result.page_height == 1920
        el = result.elements[0]
        assert el.bbox.x == 0.2
        assert el.bbox.y == 0.1

    def test_internal_shape_still_works(self) -> None:
        """Backward compat: existing payloads with bbox+page_width must keep working."""
        img = b"img-bytes-2"
        llm = MockVisionLLM()
        llm.register(
            img,
            "coarse",
            {
                "image_hash": image_hash(img),
                "elements": [
                    {
                        "id": "bbox_0",
                        "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05},
                        "text": "v = a t",
                        "latex": "v = a \\cdot t",
                        "role": "formula",
                        "parent_id": None,
                        "confidence": 0.9,
                    }
                ],
                "page_width": 1080,
                "page_height": 1440,
                "rotation": 0,
            },
        )
        result = VisionAgent(llm).extract(img)
        assert result.elements[0].bbox.x == 0.1
