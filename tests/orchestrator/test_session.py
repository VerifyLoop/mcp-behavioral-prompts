"""SessionState and InMemorySessionStore behaviour."""
from __future__ import annotations

import time

from brainer_stem_tutor.orchestrator import InMemorySessionStore, SessionState
from brainer_stem_tutor.shared.schemas import StudentTurn


class TestSessionState:
    def test_attempts_increment_on_student_turns(self) -> None:
        s = SessionState(session_id="abc")
        s.append_student(StudentTurn(text="?", ts=0.0))
        s.append_student(StudentTurn(text="!", ts=0.0))
        assert s.attempts_count == 2

    def test_mark_step_completed_resets_attempts(self) -> None:
        s = SessionState(session_id="abc")
        s.append_student(StudentTurn(text="?", ts=0.0))
        s.append_student(StudentTurn(text="?", ts=0.0))
        ts = time.time()
        s.mark_step_completed(2, ts=ts)
        assert s.last_correct_step == 2
        assert s.attempts_count == 0
        assert s.last_step_change_ts == ts

    def test_mark_step_completed_only_moves_forward(self) -> None:
        s = SessionState(session_id="abc")
        s.mark_step_completed(3)
        s.mark_step_completed(2)
        assert s.last_correct_step == 3

    def test_mark_error(self) -> None:
        s = SessionState(session_id="abc")
        s.mark_error("sign")
        assert s.last_error_kind == "sign"


class TestInMemoryStore:
    def test_get_or_create(self) -> None:
        store = InMemorySessionStore()
        s = store.get_or_create("u1")
        assert s.session_id == "u1"
        assert store.get_or_create("u1") is s
        assert len(store) == 1

    def test_put_overwrites(self) -> None:
        store = InMemorySessionStore()
        s = store.get_or_create("u1")
        s.attempts_count = 7
        store.put(s)
        assert store.get("u1").attempts_count == 7
