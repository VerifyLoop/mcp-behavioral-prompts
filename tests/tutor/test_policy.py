"""Follow policy decision-table tests."""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.schemas import StudentSignals
from brainer_stem_tutor.shared.settings import TutorSettings
from brainer_stem_tutor.tutor.policy import FollowPolicy


@pytest.fixture
def policy() -> FollowPolicy:
    return FollowPolicy(
        TutorSettings(
            POLICY_STUCK_SECONDS=60.0,
            POLICY_FRUSTRATION_THRESHOLD=0.6,
        )
    )


class TestFollowPolicy:
    def test_default_confirm_and_advance(self, policy) -> None:
        d = policy.decide(StudentSignals(last_correct_step=1), total_steps=4)
        assert d.strategy == "confirm_and_advance"
        assert d.target_step == 2

    def test_frustration_overrides_everything(self, policy) -> None:
        d = policy.decide(
            StudentSignals(
                frustration_score=0.9,
                time_on_step_seconds=300,
                attempts_count=10,
            ),
            total_steps=3,
        )
        assert d.strategy == "encourage_pause"

    def test_stuck_triggers_direct_hint(self, policy) -> None:
        d = policy.decide(
            StudentSignals(time_on_step_seconds=120, last_correct_step=2),
            total_steps=5,
        )
        assert d.strategy == "direct_hint"
        assert d.target_step == 3

    def test_concept_error_triggers_quiz(self, policy) -> None:
        d = policy.decide(
            StudentSignals(last_error_kind="concept"), total_steps=3
        )
        assert d.strategy == "concept_quiz"

    def test_sign_error_triggers_targeted_hint(self, policy) -> None:
        d = policy.decide(
            StudentSignals(last_error_kind="sign"), total_steps=3
        )
        assert d.strategy == "targeted_hint"

    def test_unit_error_triggers_targeted_hint(self, policy) -> None:
        d = policy.decide(StudentSignals(last_error_kind="unit"), total_steps=3)
        assert d.strategy == "targeted_hint"

    def test_many_attempts_triggers_soft_hint(self, policy) -> None:
        d = policy.decide(StudentSignals(attempts_count=5), total_steps=3)
        assert d.strategy == "soft_hint"

    def test_target_step_capped_at_total(self, policy) -> None:
        d = policy.decide(StudentSignals(last_correct_step=10), total_steps=4)
        assert d.target_step == 4
