"""Runner integration tests."""
from __future__ import annotations

from brainer_stem_tutor.eval.datasets import load_problems
from brainer_stem_tutor.eval.runners import SolverRunner, TutorRunner
from brainer_stem_tutor.orchestrator import Orchestrator
from brainer_stem_tutor.solver import MockSolverLLM, SolverAgent
from brainer_stem_tutor.tutor import MockTutorLLM, TutorAgent
from brainer_stem_tutor.tutor.moderator import LeakModerator
from brainer_stem_tutor.vision import MockVisionLLM, VisionAgent


class TestSolverRunner:
    def test_runs_smoke(self) -> None:
        runner = SolverRunner(SolverAgent(MockSolverLLM()), config_name="C0")
        result = runner.run(load_problems("smoke"))
        m = result.metrics
        # Mock solver hits arithmetic, equation, kinematic patterns -> all 5
        # smoke problems should be solved correctly.
        assert m.n == 5
        assert m.correct == 5
        assert m.accuracy == 1.0
        assert m.accuracy_with_verification == 1.0
        # Calibration should be near-zero since we always pass at high confidence.
        assert m.brier < 0.1

    def test_runs_italian_liceo_partial(self) -> None:
        runner = SolverRunner(SolverAgent(MockSolverLLM()))
        result = runner.run(load_problems("italian_liceo"))
        # Italian phrasing isn't fully supported by the mock — but the runner
        # must surface failures cleanly via metrics rather than crashing.
        m = result.metrics
        assert m.n == 2
        assert m.correct + m.failure_count == 2


class TestTutorRunner:
    def test_no_leaks_on_smoke(self) -> None:
        orch = Orchestrator(
            solver=SolverAgent(MockSolverLLM()),
            tutor=TutorAgent(MockTutorLLM()),
            vision=VisionAgent(MockVisionLLM()),
        )
        moderator = LeakModerator()
        runner = TutorRunner(orch, moderator)
        result = runner.run(load_problems("smoke"))
        # Mock tutor passes moderator by construction; even extractor /
        # shortcut personas should never get a leak.
        m = result.metrics
        assert m.leak_count == 0
        assert m.n > 0
