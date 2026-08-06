import asyncio

import agents.analyst.scheduler as scheduler_module
import common.llm as llm_module
from agents.analyst.scheduler import (
    build_weekly_optimisation_report,
    run_anomaly_watch_job,
    run_conversion_api_job,
    run_weekly_report_job,
)


def test_weekly_report_shows_unavailable_summary_when_llm_unconfigured(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "", raising=False)

    report = build_weekly_optimisation_report()

    assert "Résumé IA (deepseek/deepseek-chat)" in report
    assert "indisponible (LLM non configuré ou injoignable)" in report


def test_weekly_report_includes_generated_summary_when_llm_configured(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(
        llm_module, "generate_text", lambda **kwargs: "Scale the top campaign this week."
    )

    report = build_weekly_optimisation_report()

    assert "Résumé IA (deepseek/deepseek-chat)" in report
    assert "Scale the top campaign this week." in report


def test_weekly_report_labels_the_summary_with_the_active_model(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "LLM_MODEL", "gemini/gemini-1.5-flash", raising=False)
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "gm-test", raising=False)
    monkeypatch.setattr(
        llm_module, "generate_text", lambda **kwargs: "Gemini's take on this week."
    )

    report = build_weekly_optimisation_report()

    assert "Résumé IA (gemini/gemini-1.5-flash)" in report
    assert "Gemini's take on this week." in report


def test_weekly_report_has_one_recommendation_per_category():
    report = build_weekly_optimisation_report()

    assert "AUGMENTER" in report
    assert "METTRE EN PAUSE" in report
    assert "RÉÉCRIRE" in report


def test_weekly_report_names_the_deliberately_bad_ad_set_to_pause():
    report = build_weekly_optimisation_report()

    assert "- Ad set : adset_retarget_bad" in report


def test_weekly_report_names_the_underperforming_landing_page():
    report = build_weekly_optimisation_report()

    assert "- Page : lp_buyers_v1" in report


def test_weekly_report_states_it_never_executes():
    report = build_weekly_optimisation_report()

    assert "rien ci-dessous n'a été exécuté automatiquement" in report.lower()


def test_weekly_report_scale_and_pause_never_recommend_unattributed():
    report = build_weekly_optimisation_report()

    assert "Campagne : unattributed" not in report
    assert "Ad set : unattributed" not in report


def test_weekly_report_mentions_content_strategist_best_effort_notification():
    report = build_weekly_optimisation_report()

    assert "NOTIFICATION CONTENT STRATEGIST" in report
    assert "acquittée(s) (best-effort" in report


def test_weekly_report_labels_are_plain_language_not_raw_kpi_jargon():
    """The report must spell out what CPQL/CPL/ROAS mean, not just the acronym,
    so an operator with no technical background can read it unaided."""

    report = build_weekly_optimisation_report()

    assert "CPQL (coût par vente qualifiée)" in report
    assert "CPL (coût par lead)" in report
    assert "ROAS (retour sur investissement publicitaire)" in report


def test_run_weekly_report_job_saves_a_snapshot_and_sends_the_report(monkeypatch):
    saved = {}
    sent = {}

    monkeypatch.setattr(
        scheduler_module,
        "save_kpi_snapshots",
        lambda report, captured_at, client_id: saved.update(report=report, client_id=client_id),
    )

    async def _fake_send(text: str) -> None:
        sent["text"] = text

    asyncio.run(run_weekly_report_job(_fake_send, client_id="test-job-client"))

    assert saved["client_id"] == "test-job-client"
    assert "cpl" in saved["report"]
    assert "Rapport hebdomadaire d'optimisation" in sent["text"]


def test_run_anomaly_watch_job_sends_nothing_when_no_alerts(monkeypatch):
    monkeypatch.setattr(scheduler_module, "build_phase_a_alerts", lambda client_id: [])

    sent = {"called": False}

    async def _fake_send(text: str) -> None:
        sent["called"] = True

    asyncio.run(run_anomaly_watch_job(_fake_send))

    assert sent["called"] is False


def test_run_anomaly_watch_job_sends_when_alerts_fire(monkeypatch):
    import agents.analyst.scheduler as scheduler_module

    fake_alert = {
        "transition": "new_to_mql",
        "label": "New to MQL",
        "previous_rate": 70.0,
        "current_rate": 30.0,
        "drop_pct": 57.14,
        "previous_denominator": 100,
        "current_denominator": 90,
        "data_as_of": "2026-08-03T08:00:00Z",
    }
    monkeypatch.setattr(scheduler_module, "build_phase_a_alerts", lambda client_id: [fake_alert])

    sent = {}

    async def _fake_send(text: str) -> None:
        sent["text"] = text

    asyncio.run(run_anomaly_watch_job(_fake_send))

    assert "New to MQL" in sent["text"]


def test_run_conversion_api_job_calls_the_conversion_api_push_job(monkeypatch):
    calls = {}

    def fake_push(dataset, client_id):
        calls["client_id"] = client_id
        return {"pushed": [], "excluded_no_click_id": 0, "dry_run": True, "client_id": client_id}

    monkeypatch.setattr(scheduler_module.conversion_api, "run_conversion_api_push_job", fake_push)

    asyncio.run(run_conversion_api_job(client_id="test-conversion-job"))

    assert calls["client_id"] == "test-conversion-job"


def test_weekly_report_runs_the_c6_eval_job_on_the_generated_summary(monkeypatch):
    eval_calls = {}

    def fake_eval(summary_text, source_figures, client_id):
        eval_calls["summary_text"] = summary_text
        eval_calls["source_figures"] = source_figures
        eval_calls["client_id"] = client_id
        return {"score": 1.0}

    monkeypatch.setattr(scheduler_module, "run_weekly_eval_job", fake_eval)
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(llm_module, "generate_text", lambda **kwargs: "Résumé de test généré.")

    build_weekly_optimisation_report()

    assert eval_calls["summary_text"] == "Résumé de test généré."
    assert "roas" in eval_calls["source_figures"]
