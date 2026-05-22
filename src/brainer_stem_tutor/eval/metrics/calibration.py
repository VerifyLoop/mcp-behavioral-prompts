"""Calibration metrics tuned for small-N evaluation runs.

Research basis:
- Brier Skill Score normalises Brier against the climatology baseline
  p_bar*(1-p_bar) so a positive BSS means we beat constant-prediction.
- For small N (50-500), equal-width binning is unstable; equal-frequency
  (quantile) bins of 5 buckets is the recommended fallback.
- Reporting bootstrap CIs on Brier is more robust than vanilla ECE at small N.

References:
- Murphy, A. H. (1973). A new vector partition of the probability score.
- Naeini, M. P. et al. (2015). Obtaining well calibrated probabilities ...
- ICLR 2025 blog "Calibration pitfalls in deep learning".
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class QuantileBin:
    n: int
    mean_confidence: float
    empirical_accuracy: float


@dataclass
class CalibrationReport:
    n: int
    brier: float
    brier_baseline: float        # base rate p*(1-p)
    brier_skill_score: float     # 1 - brier / baseline; >0 beats baseline
    brier_ci_low: float
    brier_ci_high: float
    bins: list[QuantileBin]


def brier(pairs: Sequence[tuple[float, bool]]) -> float:
    if not pairs:
        return 0.0
    return sum((p - (1.0 if t else 0.0)) ** 2 for p, t in pairs) / len(pairs)


def baseline_brier(pairs: Sequence[tuple[float, bool]]) -> float:
    """Climatology baseline = p_bar*(1-p_bar) where p_bar = empirical accuracy."""
    if not pairs:
        return 0.0
    correct = sum(1 for _, t in pairs if t)
    p_bar = correct / len(pairs)
    return p_bar * (1.0 - p_bar)


def quantile_bins(
    pairs: Sequence[tuple[float, bool]], n_bins: int = 5
) -> list[QuantileBin]:
    """Equal-frequency bins on predicted confidence."""
    if not pairs:
        return []
    sorted_pairs = sorted(pairs, key=lambda x: x[0])
    n = len(sorted_pairs)
    size = max(1, n // n_bins)
    bins: list[QuantileBin] = []
    for i in range(0, n, size):
        chunk = sorted_pairs[i : i + size]
        if not chunk:
            continue
        mc = sum(p for p, _ in chunk) / len(chunk)
        acc = sum(1 for _, t in chunk if t) / len(chunk)
        bins.append(
            QuantileBin(n=len(chunk), mean_confidence=mc, empirical_accuracy=acc)
        )
    return bins


def bootstrap_brier_ci(
    pairs: Sequence[tuple[float, bool]],
    iterations: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the Brier score.

    Returns (low, high) at the given two-sided confidence level. Returns
    (brier, brier) for empty / single-item inputs so the report still has
    a defined range.
    """
    if not pairs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    samples: list[float] = []
    n = len(pairs)
    for _ in range(iterations):
        resample = [pairs[rng.randrange(n)] for _ in range(n)]
        samples.append(brier(resample))
    samples.sort()
    alpha = (1.0 - confidence) / 2.0
    lo_idx = max(0, math.floor(alpha * iterations) - 1)
    hi_idx = min(iterations - 1, math.ceil((1 - alpha) * iterations) - 1)
    return (samples[lo_idx], samples[hi_idx])


def compute_calibration(
    pairs: Iterable[tuple[float, bool]],
    n_bins: int = 5,
    bootstrap_iterations: int = 500,
    seed: int = 0,
) -> CalibrationReport:
    items = list(pairs)
    b = brier(items)
    base = baseline_brier(items)
    bss = (1.0 - b / base) if base > 0 else 0.0
    lo, hi = bootstrap_brier_ci(items, iterations=bootstrap_iterations, seed=seed)
    return CalibrationReport(
        n=len(items),
        brier=b,
        brier_baseline=base,
        brier_skill_score=bss,
        brier_ci_low=lo,
        brier_ci_high=hi,
        bins=quantile_bins(items, n_bins=n_bins),
    )
