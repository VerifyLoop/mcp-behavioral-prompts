"""Logging setup is idempotent and writes to the configured file."""
from __future__ import annotations

from brainer_stem_tutor.shared.logging_config import (
    get_logger,
    setup_logging,
)
from brainer_stem_tutor.shared.settings import TutorSettings


class TestLogging:
    def test_setup_returns_brainer_logger(self, tmp_path) -> None:
        logfile = tmp_path / "out.log"
        s = TutorSettings(LOG_FILE=logfile, LOG_LEVEL="DEBUG")
        log = setup_logging(s)
        assert log.name == "brainer_stem_tutor"
        log.warning("hello")
        for h in log.handlers:
            h.flush()
        assert logfile.exists()
        assert "hello" in logfile.read_text()

    def test_setup_is_idempotent(self, tmp_path, caplog) -> None:
        logfile = tmp_path / "out.log"
        s = TutorSettings(LOG_FILE=logfile)
        log1 = setup_logging(s)
        n1 = len(log1.handlers)
        log2 = setup_logging(s)
        n2 = len(log2.handlers)
        assert log1 is log2
        assert n1 == n2  # handlers not duplicated

    def test_get_logger_namespacing(self) -> None:
        log = get_logger("brainer_stem_tutor.solver.agent")
        assert log.name.startswith("brainer_stem_tutor")
        # Logger for an unrelated module gets folded under the brainer tree.
        log2 = get_logger("third_party.x")
        assert log2.name.startswith("brainer_stem_tutor.")
