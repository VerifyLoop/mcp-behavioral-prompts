"""Vision-side schemas the tutor consumes.

`VisionContext` is what the orchestrator hands the tutor: the most recent
VisionResult plus an optional mapping from solver-step number to a set of
bbox ids the tutor should highlight when reasoning about that step.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..shared.schemas import VisionResult


class VisionContext(BaseModel):
    last_result: Optional[VisionResult] = None
    step_to_bboxes: dict[int, list[str]] = Field(default_factory=dict)

    def bbox_ids_for_step(self, step_n: int) -> list[str]:
        return list(self.step_to_bboxes.get(step_n, []))

    def with_mapping(self, step_n: int, bbox_ids: list[str]) -> "VisionContext":
        new_map = dict(self.step_to_bboxes)
        new_map[step_n] = list(bbox_ids)
        return VisionContext(last_result=self.last_result, step_to_bboxes=new_map)
