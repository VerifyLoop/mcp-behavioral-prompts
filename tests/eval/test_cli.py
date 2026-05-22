"""CLI smoke tests."""
from __future__ import annotations

import json

from brainer_stem_tutor.eval.cli import run


class TestCLI:
    def test_smoke_run_returns_zero(self, capsys) -> None:
        rc = run(["--dataset", "smoke"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "solver" in out

    def test_json_output(self, capsys) -> None:
        rc = run(["--dataset", "smoke", "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "solver" in data and data["solver"]["n"] == 5

    def test_tutor_flag(self, capsys) -> None:
        rc = run(["--dataset", "smoke", "--tutor", "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "tutor" in data
        assert data["tutor"]["leak_count"] == 0

    def test_ci_passes_on_clean_run(self, capsys) -> None:
        rc = run(["--dataset", "smoke", "--tutor", "--ci"])
        assert rc == 0

    def test_writes_out_file(self, tmp_path, capsys) -> None:
        out = tmp_path / "report.txt"
        rc = run(["--dataset", "smoke", "--out", str(out)])
        assert rc == 0
        assert out.exists() and "solver" in out.read_text(encoding="utf-8")
