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

    roas_label = "ROAS (retour sur investissement publicitaire)"

    assert "Rapport KPI - Agent Analyst" in response
    assert f"CPL (coût par lead): {expected['cpl']['value']:.2f}" in response
    assert f"{roas_label}: {expected['roas']['value']:.2f}x" in response
    assert f"Taux de réponse: {expected['response_rate']['value']:.2f}%" in response


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

    assert "Alertes de conversion" in response
    assert "Alerte : New to MQL" in response
    assert "Chute : 70.00% → 30.00%" in response
    assert "Action : à transmettre au Commander pour revue immédiate." in response


def test_handle_optimisation_report_command_returns_recommendations():
    response = handle_text_command("/optimisation_report", client_id="demo-real-estate")

    assert "Rapport hebdomadaire d'optimisation" in response
    assert "AUGMENTER" in response
    assert "METTRE EN PAUSE" in response
    assert "RÉÉCRIRE" in response


def test_handle_weekly_report_command_returns_kpis_and_alerts():
    response = handle_text_command("/weekly_report", client_id="demo-real-estate")
    expected = pull_kpi_report()

    assert "Rapport hebdomadaire - Agent Analyst" in response
    assert f"CPL (coût par lead): {expected['cpl']['value']:.2f}" in response
    assert "Alertes immédiates : 1 chute(s) de conversion détectée(s)" in response
    assert "Alerte : New to MQL" in response


def test_handle_predictive_roas_command_returns_a_range():
    response = handle_text_command("/predictive_roas", client_id="demo-real-estate")

    assert "ROAS prédictif" in response
    assert "Revenu projeté" in response


def test_handle_cohorts_command_names_the_best_campaign():
    response = handle_text_command("/cohorts", client_id="demo-real-estate")

    assert "Analyse de cohortes" in response
    assert "1. google_search_intent" in response


def test_handle_conversion_api_command_is_always_dry_run():
    response = handle_text_command("/conversion_api", client_id="demo-real-estate")

    assert "Aperçu Conversion API" in response
    assert "Mode dry-run" in response


def test_handle_scoring_feedback_command_names_the_overweighted_dimension():
    response = handle_text_command("/scoring_feedback", client_id="demo-real-estate")

    assert "Feedback de scoring" in response
    assert "contactability" in response
    assert "diminuer ce poids" in response


def test_handle_ab_tests_command_shows_all_three_outcomes():
    response = handle_text_command("/ab_tests", client_id="demo-real-estate")

    assert "vg_hero_copy" in response
    assert "vg_cta_button" in response
    assert "vg_headline" in response
    assert "🏆" in response
    assert "données insuffisantes" in response


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
