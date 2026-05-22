"""Tests for the live frame stability detector."""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.settings import TutorSettings
from brainer_stem_tutor.vision.live_detector import (
    LiveDetector,
    _phash,
    hamming,
)


def _solid_frame(value: int, size: int = 16) -> list[list[int]]:
    return [[value] * size for _ in range(size)]


def _half_frame(left: int, right: int, size: int = 16) -> list[list[int]]:
    mid = size // 2
    return [[left if i < mid else right for i in range(size)] for _ in range(size)]


class TestPHashBasics:
    def test_solid_white_zero(self) -> None:
        # solid > mean -> all 1s? actually pixels == mean -> all set, so hash = (1<<64)-1
        h = _phash(_solid_frame(255))
        assert h == (1 << 64) - 1

    def test_two_solids_have_low_distance(self) -> None:
        h1 = _phash(_solid_frame(120))
        h2 = _phash(_solid_frame(140))
        assert hamming(h1, h2) == 0  # both >= their own mean -> same fingerprint

    def test_dark_vs_light_split_differ(self) -> None:
        h1 = _phash(_half_frame(0, 255))
        h2 = _phash(_half_frame(255, 0))
        assert hamming(h1, h2) > 16  # should differ on most bits


class TestLiveDetector:
    def _detector(self) -> LiveDetector:
        return LiveDetector(
            TutorSettings(LIVE_FRAME_DIFF_THRESHOLD=0.1, LIVE_STABILITY_FRAMES=2)
        )

    def test_initial_frame_no_event(self) -> None:
        det = self._detector()
        ev = det.process(_solid_frame(120))
        assert ev.kind == "no_change"

    def test_no_change_between_identical_frames(self) -> None:
        det = self._detector()
        det.process(_solid_frame(120))
        ev = det.process(_solid_frame(120))
        assert ev.kind == "no_change"

    def test_stable_after_change_after_two_stable_frames(self) -> None:
        det = self._detector()
        # Frame 1: solid 0 -> baseline
        det.process(_solid_frame(0))
        # Frame 2: introduce big change -> pending
        e = det.process(_half_frame(0, 255))
        assert e.kind == "still_writing"
        # Frame 3: same as previous change -> streak 1
        e = det.process(_half_frame(0, 255))
        assert e.kind == "still_writing"
        # Frame 4: stable again -> emit completion
        e = det.process(_half_frame(0, 255))
        assert e.kind == "stable_after_change"

    def test_moving_target_resets_streak(self) -> None:
        det = self._detector()
        det.process(_solid_frame(0))
        det.process(_half_frame(0, 255))   # pending
        e = det.process(_solid_frame(255)) # different again -> still moving
        assert e.kind == "still_writing"
        assert "moving" in e.notes or det.state.stable_streak == 0

    def test_reset(self) -> None:
        det = self._detector()
        det.process(_solid_frame(0))
        det.reset()
        assert det.state.last_hash is None
