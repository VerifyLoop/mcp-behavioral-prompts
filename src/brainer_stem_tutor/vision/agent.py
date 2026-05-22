"""Vision agent — placeholder, fleshed out in the vision phase.

Kept here so `from .vision import VisionAgent` works during tutor tests.
"""
from __future__ import annotations

from typing import Protocol


class VisionLLMProtocol(Protocol):  # pragma: no cover - placeholder
    @property
    def model_id(self) -> str:
        ...


class MockVisionLLM:  # pragma: no cover - placeholder
    model_id = "mock-vision-v1"


class VisionAgent:  # pragma: no cover - placeholder
    pass
