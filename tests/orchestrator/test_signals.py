"""SignalComputer tests — pure heuristic, no LLM."""
from __future__ import annotations

import time

from brainer_stem_tutor.orchestrator import SessionState, SignalComputer
from brainer_stem_tutor.shared.schemas import StudentTurn


class TestSignalComputer:
    def test_no_history_zero_signals(self) -> None:
        state = SessionState(session_id="s")
        sigs = SignalComputer().compute(state)
        assert sigs.frustration_score == 0.0
        assert sigs.attempts_count == 0

    def test_time_on_step(self) -> None:
        state = SessionState(session_id="s")
        state.last_step_change_ts = time.time() - 30
        sigs = SignalComputer().compute(state)
        assert sigs.time_on_step_seconds >= 29

    def test_high_frustration_lexicon(self) -> None:
        state = SessionState(session_id="s")
        state.student_turns.append(StudentTurn(text="I hate this", ts=0))
        sigs = SignalComputer().compute(state)
        assert sigs.frustration_score >= 0.5

    def test_medium_frustration_lexicon(self) -> None:
        state = SessionState(session_id="s")
        state.student_turns.append(StudentTurn(text="I am stuck", ts=0))
        sigs = SignalComputer().compute(state)
        assert 0.0 < sigs.frustration_score < 0.5

    def test_repeated_punctuation_adds_signal(self) -> None:
        state = SessionState(session_id="s")
        state.student_turns.append(StudentTurn(text="what now??!!", ts=0))
        sigs = SignalComputer().compute(state)
        assert sigs.frustration_score > 0.0

    def test_score_capped_at_one(self) -> None:
        state = SessionState(session_id="s")
        for word in ["hate", "stupid", "impossible", "frustrated"]:
            state.student_turns.append(StudentTurn(text=word, ts=0))
        sigs = SignalComputer().compute(state)
        assert sigs.frustration_score <= 1.0
