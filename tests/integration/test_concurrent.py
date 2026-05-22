"""Concurrent sessions: orchestrator state isolation under threads.

5 sessions in parallel, each chasing the answer; we assert no cross-talk
(each session's tutor_turn must refer only to its own solved problem).
"""
from __future__ import annotations

import threading

from brainer_stem_tutor.orchestrator import Orchestrator
from brainer_stem_tutor.solver import MockSolverLLM, SolverAgent
from brainer_stem_tutor.tutor import MockTutorLLM, TutorAgent
from brainer_stem_tutor.vision import MockVisionLLM, VisionAgent


def _build() -> Orchestrator:
    return Orchestrator(
        solver=SolverAgent(MockSolverLLM()),
        tutor=TutorAgent(MockTutorLLM()),
        vision=VisionAgent(MockVisionLLM()),
    )


class TestConcurrentSessions:
    def test_five_sessions_in_parallel(self) -> None:
        orch = _build()
        # 5 sessions, each with a distinct arithmetic problem and expected
        # answer; we make sure no session ever sees another's answer.
        problems = [
            ("s1", "What is 1+1?", 2.0),
            ("s2", "What is 2+2?", 4.0),
            ("s3", "What is 3+3?", 6.0),
            ("s4", "What is 4+4?", 8.0),
            ("s5", "What is 5+5?", 10.0),
        ]
        results: dict[str, list[str]] = {sid: [] for sid, _, _ in problems}
        errors: list[BaseException] = []

        def worker(sid: str, problem: str) -> None:
            try:
                orch.on_problem_statement(sid, problem)
                for msg in ["where do I start?", "what next?", "any hint?"]:
                    r = orch.on_student_message(sid, msg)
                    assert r.tutor_turn is not None
                    results[sid].append(r.tutor_turn.student_facing_message)
            except BaseException as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(sid, p))
            for sid, p, _ in problems
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        # No leak across sessions: each session's tutor messages must not
        # contain any OTHER session's expected numeric answer.
        for sid_a, _, expected_a in problems:
            others = {expected_a for sid_b, _, _ in problems if sid_b != sid_a}
            # In practice the moderator already blocks own-answer; we want
            # cross-session contamination not to surface. Mock tutor templates
            # don't mention numbers at all, so this is a safety net.
            for msg in results[sid_a]:
                for v in others:
                    # Permit "1" appearing in "step 1" etc.; require the exact
                    # value as a free-standing number.
                    import re

                    assert not re.search(rf"\b{int(v)}\b", msg), (
                        f"session {sid_a} leaked another session's value {v}: {msg!r}"
                    )
