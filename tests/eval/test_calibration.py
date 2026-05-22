"""Brier Skill Score, quantile bins, bootstrap CI."""
from __future__ import annotations

import math

from brainer_stem_tutor.eval.metrics.calibration import (
    bootstrap_brier_ci,
    brier,
    compute_calibration,
    quantile_bins,
)


class TestBrier:
    def test_empty(self) -> None:
        assert brier([]) == 0.0

    def test_perfect(self) -> None:
        assert brier([(1.0, True), (0.0, False)]) == 0.0

    def test_worst(self) -> None:
        assert brier([(0.0, True), (1.0, False)]) == 1.0


class TestQuantileBins:
    def test_five_bins_across_uniform_confidence(self) -> None:
        pairs = [(i / 10, i % 2 == 0) for i in range(10)]
        bins = quantile_bins(pairs, n_bins=5)
        assert len(bins) == 5
        assert all(b.n >= 1 for b in bins)
        assert bins[0].mean_confidence < bins[-1].mean_confidence

    def test_empty_input(self) -> None:
        assert quantile_bins([]) == []


class TestBootstrapCI:
    def test_ci_contains_point_estimate(self) -> None:
        pairs = [(0.8, True)] * 30 + [(0.2, False)] * 20
        lo, hi = bootstrap_brier_ci(pairs, iterations=200, seed=0)
        point = brier(pairs)
        assert lo <= point <= hi

    def test_empty_returns_zero_interval(self) -> None:
        assert bootstrap_brier_ci([]) == (0.0, 0.0)

    def test_ci_shrinks_with_more_samples(self) -> None:
        small = [(0.7, True)] * 10 + [(0.3, False)] * 10
        big = small * 10
        lo_s, hi_s = bootstrap_brier_ci(small, iterations=200, seed=1)
        lo_b, hi_b = bootstrap_brier_ci(big, iterations=200, seed=1)
        assert (hi_b - lo_b) <= (hi_s - lo_s) + 1e-9


class TestCalibrationReport:
    def test_well_calibrated_positive_bss(self) -> None:
        # 80% confidence with 80% accuracy
        pairs = [(0.8, True)] * 80 + [(0.8, False)] * 20
        rep = compute_calibration(pairs, bootstrap_iterations=200)
        # Brier of constant 0.8 with 80% pos = 0.8*(0.8-1)^2 + 0.2*(0.8-0)^2 = 0.16
        # baseline = 0.8*0.2 = 0.16 -> BSS ~= 0
        assert math.isclose(rep.brier, 0.16, abs_tol=1e-6)
        assert math.isclose(rep.brier_baseline, 0.16, abs_tol=1e-6)
        assert abs(rep.brier_skill_score) < 1e-6

    def test_perfect_calibration_bss_one(self) -> None:
        pairs = [(1.0, True)] * 50 + [(0.0, False)] * 50
        rep = compute_calibration(pairs, bootstrap_iterations=100)
        assert rep.brier == 0.0
        assert rep.brier_skill_score == 1.0

    def test_zero_variance_bss_zero(self) -> None:
        pairs = [(0.5, True)] * 10
        rep = compute_calibration(pairs, bootstrap_iterations=50)
        # baseline = 0 -> BSS defined as 0 (avoid div by zero)
        assert rep.brier_skill_score == 0.0
