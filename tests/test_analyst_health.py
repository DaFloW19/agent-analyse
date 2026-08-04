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


def test_attribution_endpoint_defaults_to_campaign_grouping():
    client = TestClient(app)

    response = client.get("/attribution")

    body = response.json()
    assert response.status_code == 200
    assert body["group_by"] == "campaign"
    assert body["client_id"]
    assert "unattributed" in body["by_group"] or body["by_group"]


def test_attribution_endpoint_accepts_ad_set_grouping():
    client = TestClient(app)

    response = client.get("/attribution", params={"group_by": "ad_set"})

    body = response.json()
    assert response.status_code == 200
    assert body["group_by"] == "ad_set"
    assert "adset_retarget_bad" in body["by_group"]


def test_landing_pages_endpoint_flags_the_underperforming_page():
    client = TestClient(app)

    response = client.get("/landing-pages")

    body = response.json()
    assert response.status_code == 200
    pages_by_name = {page["landing_page"]: page for page in body["pages"]}
    assert pages_by_name["lp_buyers_v1"]["below_threshold"] is True


def test_alerts_endpoint_returns_a_list():
    client = TestClient(app)

    response = client.get("/alerts")

    body = response.json()
    assert response.status_code == 200
    assert isinstance(body["alerts"], list)


def test_weekly_report_endpoint_returns_report_text():
    client = TestClient(app)

    response = client.get("/weekly-report")

    body = response.json()
    assert response.status_code == 200
    assert "Rapport hebdomadaire d'optimisation" in body["report"]


def test_status_endpoint_reports_configuration_and_reachability():
    client = TestClient(app)

    response = client.get("/status")

    body = response.json()
    assert response.status_code == 200
    assert body["agent_name"] == "analyst"
    # Live agent calls are mocked to unreachable by default in the test suite
    # (see tests/conftest.py::_disable_live_agent_calls).
    assert body["crm_keeper_reachable"] is False
    assert body["media_buyer_reachable"] is False
    assert isinstance(body["database_reachable"], bool)
    assert "llm_model" in body
    assert isinstance(body["llm_configured"], bool)
    assert isinstance(body["langfuse_configured"], bool)
