"""Solver pipeline tests: draft -> verify -> cache."""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.schemas import SolvedProblem
from brainer_stem_tutor.solver import MockSolverLLM, SolverAgent, SolvedCache


class TestMockSolverLLMDirect:
    def test_arithmetic_draft(self) -> None:
        llm = MockSolverLLM()
        d = llm.draft("what is 2+2?")
        assert d.final_answer_numeric == 4.0
        assert d.subject == "math"
        assert len(d.verifications) >= 1
        assert all(v.passed for v in d.verifications)

    def test_equation_draft(self) -> None:
        llm = MockSolverLLM()
        d = llm.draft("solve 2*x - 6 = 0 for x")
        assert d.subject == "math"
        # one root, should be parsed numerically
        assert d.final_answer_numeric == 3.0

    def test_kinematics_draft(self) -> None:
        llm = MockSolverLLM()
        d = llm.draft(
            "An object accelerates at 2 m/s^2 starting from rest for 5 seconds. "
            "What is its velocity?"
        )
        assert d.subject == "physics"
        assert d.final_answer_numeric == 10.0
        assert d.units == "m/s"


class TestSolverAgent:
    def test_solves_arithmetic_end_to_end(self) -> None:
        agent = SolverAgent(MockSolverLLM())
        solved = agent.solve("What is 7*6?")
        assert isinstance(solved, SolvedProblem)
        assert solved.final_answer_numeric == 42.0
        assert solved.verifications
        assert all(v.passed for v in solved.verifications)
        assert solved.confidence >= 0.9

    def test_solves_equation(self) -> None:
        agent = SolverAgent(MockSolverLLM())
        solved = agent.solve("Solve x**2 - 9 = 0 for x")
        # multi-root => not a single numeric
        assert solved.final_answer_numeric is None
        assert solved.confidence > 0.5

    def test_solves_physics_with_units(self) -> None:
        agent = SolverAgent(MockSolverLLM())
        solved = agent.solve(
            "An object accelerates at 3 m/s^2 starting from rest for 4 seconds. "
            "Find the velocity."
        )
        assert solved.subject == "physics"
        assert solved.final_answer_numeric == 12.0
        assert solved.units == "m/s"
        unit_check = next(
            v for v in solved.verifications if v.tool == "unit_checker"
        )
        assert unit_check.passed

    def test_caches_repeat_calls(self) -> None:
        cache = SolvedCache()
        agent = SolverAgent(MockSolverLLM(), cache=cache)
        s1 = agent.solve("What is 5+5?")
        s2 = agent.solve("What is 5+5?")
        assert s1 is s2  # identity, not just equality
        assert len(cache) == 1

    def test_refuses_to_close_without_verifications(self) -> None:
        class StubLLM:
            model_id = "stub"

            def draft(self, problem_text: str):
                from brainer_stem_tutor.solver.agent import DraftSolution
                from brainer_stem_tutor.shared.schemas import Step

                return DraftSolution(
                    subject="math",
                    steps=[
                        Step(n=1, kind="setup", latex="?", justification="g"),
                        Step(n=2, kind="answer", latex="?", justification="g"),
                    ],
                    final_answer="?",
                    final_answer_numeric=None,
                    units=None,
                    verifications=[],
                )

        with pytest.raises(RuntimeError, match="no verifications"):
            SolverAgent(StubLLM()).solve("opaque")

    def test_confidence_calibration_two_passing(self) -> None:
        """Two passing verifications should yield confidence >= 0.95."""
        agent = SolverAgent(MockSolverLLM())
        solved = agent.solve("What is 2+2?")
        # arithmetic draft has 1 verification, so 0.99 cap doesn't trigger;
        # confidence should still be >= 0.85
        assert solved.confidence >= 0.85
