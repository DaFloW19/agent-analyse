import json

import pytest

from agents.analyst.data_pull import pull_kpi_report
from agents.analyst.telegram_commands import handle_text_command, parse_observe_command


def test_parse_observe_command_coerces_key_values():
    parsed = parse_observe_command(
        "/observe media_buyer pause_ad_set conversions=6 dry_run=true cpl_multiplier=2.4"
    )

    assert parsed.agent_name == "media_buyer"
    assert parsed.task_type == "pause_ad_set"
    assert parsed.data_points == {
        "conversions": 6,
        "dry_run": True,
        "cpl_multiplier": 2.4,
    }


def test_parse_observe_command_accepts_agent_only():
    parsed = parse_observe_command("/observe media_buyer")

    assert parsed.agent_name == "media_buyer"
    assert parsed.task_type == "general_observation"
    assert parsed.data_points == {}


def test_parse_observe_command_rejects_unknown_agent():
    with pytest.raises(ValueError, match="Unknown agent"):
        parse_observe_command("/observe unknown pause_ad_set conversions=6")


def test_handle_report_command_returns_phase_a_report():
    response = handle_text_command("/report", client_id="demo-real-estate")
    expected = pull_kpi_report()

    assert "Analyst Phase B Report" in response
    assert f"CPL: {expected['cpl']['value']:.2f}" in response
    assert f"ROAS: {expected['roas']['value']:.2f}x" in response
    assert f"Response rate: {expected['response_rate']['value']:.2f}%" in response


def test_handle_start_command_lists_commands_and_agents():
    response = handle_text_command("/start", client_id="demo-real-estate")

    assert "Commands:" in response
    assert "/weekly_report" in response
    assert "/alerts" in response
    assert "/observe <agent_name>" in response
    assert "Agents:" in response
    assert "media_buyer" in response
    assert "content_strategist" in response


def test_handle_alerts_command_returns_conversion_drop_alert():
    response = handle_text_command("/alerts", client_id="demo-real-estate")

    assert "Conversion Alerts" in response
    assert "Alert: New to MQL" in response
    assert "Drop: 70.00% -> 30.00%" in response
    assert "Action: route to Commander for immediate review." in response


def test_handle_optimisation_report_command_returns_recommendations():
    response = handle_text_command("/optimisation_report", client_id="demo-real-estate")

    assert "Weekly Optimisation Report" in response
    assert "Scale:" in response
    assert "Pause:" in response
    assert "Rewrite:" in response


def test_handle_weekly_report_command_returns_kpis_and_alerts():
    response = handle_text_command("/weekly_report", client_id="demo-real-estate")
    expected = pull_kpi_report()

    assert "Weekly Analyst Report" in response
    assert f"CPL: {expected['cpl']['value']:.2f}" in response
    assert "Immediate alerts: 1 conversion drop detected" in response
    assert "Alert: New to MQL" in response


def test_handle_observe_command_writes_log(tmp_path):
    log_path = tmp_path / "analyst.jsonl"

    response = handle_text_command(
        "/observe media_buyer pause_ad_set conversions=6 dry_run=true",
        client_id="demo-real-estate",
        log_path=str(log_path),
    )

    assert "Observation Report" in response
    assert "Agent: Media Buyer" in response
    assert "Decision: Review required" in response
    assert "Insufficient conversion volume" in response

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["agent_name"] == "analyst"
    assert entry["action_type"] == "telegram_observe"
    assert entry["client_id"] == "demo-real-estate"
