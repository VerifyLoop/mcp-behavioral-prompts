"""Integration test for the optional FastAPI shim.

Skipped if fastapi isn't installed (so test runs work in slim environments).
"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from brainer_stem_tutor.orchestrator.fastapi_app import create_app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(create_app())


class TestFastAPIShim:
    def test_healthz(self, client) -> None:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_problem_then_message_flow(self, client) -> None:
        sid = "api-1"
        r = client.post(
            f"/sessions/{sid}/problem",
            json={"session_id": sid, "problem_text": "What is 7*8?"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["solved_summary"]["confidence"] > 0.5

        r2 = client.post(
            f"/sessions/{sid}/message",
            json={"session_id": sid, "text": "where do I start?"},
        )
        assert r2.status_code == 200
        turn = r2.json()["turn"]
        assert turn is not None
        # internal_notes must NOT be in the API response
        assert "internal_notes" not in turn
        # safety: no leak of 56 in the message
        assert "56" not in turn["student_facing_message"]

    def test_session_id_mismatch_rejected(self, client) -> None:
        r = client.post(
            "/sessions/A/problem",
            json={"session_id": "B", "problem_text": "?"},
        )
        assert r.status_code == 400

    def test_step_and_error_endpoints(self, client) -> None:
        sid = "api-2"
        client.post(
            f"/sessions/{sid}/problem",
            json={"session_id": sid, "problem_text": "What is 1+1?"},
        )
        r = client.post(
            f"/sessions/{sid}/step", json={"session_id": sid, "step_n": 1}
        )
        assert r.status_code == 200
        r = client.post(
            f"/sessions/{sid}/error", json={"session_id": sid, "kind": "sign"}
        )
        assert r.status_code == 200
