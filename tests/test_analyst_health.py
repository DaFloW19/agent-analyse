import json

from fastapi.testclient import TestClient

from agents.analyst.data_pull import pull_kpi_report
from agents.analyst.main import app


def test_health_endpoint_returns_agent_identity():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["agent_name"] == "analyst"
    assert response.json()["client_id"]


def test_observe_endpoint_flags_media_buyer_low_volume(tmp_path):
    previous_log_path = app.state.log_path
    app.state.log_path = tmp_path / "analyst.jsonl"
    client = TestClient(app)

    try:
        response = client.post(
            "/observe",
            json={
                "client_id": "demo-real-estate",
                "agent_name": "media_buyer",
                "task_type": "pause_ad_set",
                "input_summary": "Ad set CPL is above target.",
                "expected_output": "Pause the ad set.",
                "lead_id": None,
                "data_points": {"conversions": 6, "dry_run": True},
            },
        )
    finally:
        app.state.log_path = previous_log_path

    body = response.json()
    assert response.status_code == 200
    assert body["agent_name"] == "analyst"
    assert body["observed_agent"] == "media_buyer"
    assert "cpl" in body["affected_kpis"]
    assert "insufficient_conversion_volume" in body["risks"]
    assert body["safe_to_continue"] is False


def test_observe_endpoint_writes_local_json_log(tmp_path):
    previous_log_path = app.state.log_path
    app.state.log_path = tmp_path / "analyst.jsonl"
    client = TestClient(app)

    try:
        response = client.post(
            "/observe",
            json={
                "client_id": "demo-real-estate",
                "agent_name": "closer",
                "task_type": "send_first_contact",
                "input_summary": "Closer is preparing first contact.",
                "lead_id": "lead-123",
                "data_points": {"do_not_contact": False},
            },
        )
    finally:
        app.state.log_path = previous_log_path

    assert response.status_code == 200
    lines = (tmp_path / "analyst.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["agent_name"] == "analyst"
    assert entry["action_type"] == "observe_task"
    assert entry["lead_id"] == "lead-123"
    assert entry["model_used"] == "rule-based"


def test_report_endpoint_returns_all_nine_phase_a_kpis():
    client = TestClient(app)

    response = client.get("/report")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert set(body["metrics"]) == {
        "cpl",
        "cpq",
        "cpql",
        "cpbd",
        "roas",
        "stage_conversion_rate",
        "time_to_first_contact",
        "response_rate",
        "meeting_show_rate",
    }
    assert body["metrics"]["cpl"]["value"] == pull_kpi_report()["cpl"]["value"]
