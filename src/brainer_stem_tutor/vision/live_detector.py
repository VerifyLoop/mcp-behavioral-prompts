"""Live detection: decide when a student has finished writing a new piece.

The frontend sends one frame every ~1.5s. We do NOT call Gemini on every
frame — instead we compute a perceptual hash, compare with the previous
hash, and emit a "formula_completed" event only after the frame has been
visually stable for `stability_frames` consecutive frames following a
significant change.

The pHash implementation is a tiny 8x8 DCT-free variant: downsample to 8x8
grayscale, compare each pixel to the mean, pack into a 64-bit fingerprint.
Distance is Hamming.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ..shared.settings import TutorSettings, get_settings

logger = logging.getLogger(__name__)


GrayFrame = list[list[int]]  # 2D matrix of 0..255 ints


@dataclass
class LiveEvent:
    """An event the orchestrator should react to."""

    kind: str    # "stable_after_change" | "still_writing" | "no_change"
    distance: int = 0
    notes: str = ""


@dataclass
class LiveDetectorState:
    last_hash: Optional[int] = None
    stable_streak: int = 0
    pending_change: bool = False
    pending_hash: Optional[int] = None


def _phash(frame: GrayFrame, size: int = 8) -> int:
    """Tiny perceptual hash. Pure Python so we don't depend on Pillow/numpy.

    Caller supplies an already-downsampled grayscale frame of arbitrary size;
    we resample by nearest-neighbour to size x size and compare each pixel
    to the mean.
    """
    if not frame or not frame[0]:
        raise ValueError("empty frame")
    h_in = len(frame)
    w_in = len(frame[0])
    pixels: list[int] = []
    for j in range(size):
        sy = min(int(j * h_in / size), h_in - 1)
        row = frame[sy]
        for i in range(size):
            sx = min(int(i * w_in / size), w_in - 1)
            pixels.append(row[sx])
    mean = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= mean else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class LiveDetector:
    """Streams frames in, emits LiveEvents.

    Lifecycle:
    - first frame: no event, just remember the hash.
    - subsequent frame: if Hamming distance > diff_threshold_bits, mark
      `pending_change` with the new hash. Reset stable streak.
    - subsequent frames matching the pending hash: increment streak.
    - when streak >= stability_frames: emit "stable_after_change" once,
      clear pending state.
    """

    def __init__(
        self,
        settings: Optional[TutorSettings] = None,
        diff_threshold_bits: Optional[int] = None,
        stability_frames: Optional[int] = None,
    ) -> None:
        s = settings or get_settings()
        # 64-bit phash -> threshold in bits is fraction * 64.
        self._diff = (
            diff_threshold_bits
            if diff_threshold_bits is not None
            else max(1, int(s.LIVE_FRAME_DIFF_THRESHOLD * 64))
        )
        self._stability = (
            stability_frames if stability_frames is not None else s.LIVE_STABILITY_FRAMES
        )
        self._state = LiveDetectorState()

    @property
    def state(self) -> LiveDetectorState:
        return self._state

    def reset(self) -> None:
        self._state = LiveDetectorState()

    def process(self, frame: GrayFrame) -> LiveEvent:
        h = _phash(frame)
        st = self._state

        if st.last_hash is None:
            st.last_hash = h
            return LiveEvent(kind="no_change", notes="initial frame")

        if st.pending_change:
            # Currently waiting for stability after a change.
            assert st.pending_hash is not None
            dist = hamming(h, st.pending_hash)
            if dist <= self._diff // 2:
                st.stable_streak += 1
                if st.stable_streak >= self._stability:
                    st.last_hash = st.pending_hash
                    st.pending_change = False
                    st.pending_hash = None
                    st.stable_streak = 0
                    return LiveEvent(
                        kind="stable_after_change",
                        distance=0,
                        notes="formula completed",
                    )
                return LiveEvent(
                    kind="still_writing",
                    distance=dist,
                    notes=f"streak={st.stable_streak}/{self._stability}",
                )
            # The pending change moved again -> update target.
            st.pending_hash = h
            st.stable_streak = 0
            return LiveEvent(kind="still_writing", distance=dist, notes="moving target")

        # No pending change: did the frame change significantly from last stable?
        dist = hamming(h, st.last_hash)
        if dist > self._diff:
            st.pending_change = True
            st.pending_hash = h
            st.stable_streak = 0
            return LiveEvent(
                kind="still_writing",
                distance=dist,
                notes="change detected, awaiting stability",
            )
        return LiveEvent(kind="no_change", distance=dist)
