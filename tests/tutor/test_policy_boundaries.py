"""Boundary tests for FollowPolicy — covers the off-by-one fix."""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.schemas import StudentSignals
from brainer_stem_tutor.tutor.policy import FollowPolicy


@pytest.fixture
def policy() -> FollowPolicy:
    return FollowPolicy()


class TestPolicyBoundaries:
    def test_target_step_never_exceeds_total(self, policy) -> None:
        d = policy.decide(StudentSignals(last_correct_step=10), total_steps=4)
        assert d.target_step == 4

    def test_target_step_when_at_boundary(self, policy) -> None:
        d = policy.decide(StudentSignals(last_correct_step=4), total_steps=4)
        assert d.target_step == 4
        assert "completed" in d.reason

    def test_target_step_one_past_returns_total(self, policy) -> None:
        d = policy.decide(StudentSignals(last_correct_step=3), total_steps=4)
        # Student finished step 3; next target is step 4 — must not be 5.
        assert d.target_step == 4

    def test_negative_total_steps_normalised(self, policy) -> None:
        # Defensive: zero/negative shouldn't crash, target floor is 1.
        d = policy.decide(StudentSignals(last_correct_step=0), total_steps=0)
        assert d.target_step == 1

    def test_zero_signals_default_strategy(self, policy) -> None:
        d = policy.decide(StudentSignals(), total_steps=4)
        assert d.strategy == "confirm_and_advance"
        assert d.target_step == 1
