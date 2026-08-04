import asyncio

import agents.analyst.scheduler as scheduler_module
import common.llm as llm_module
from agents.analyst.scheduler import (
    build_weekly_optimisation_report,
    run_anomaly_watch_job,
    run_weekly_report_job,
)


def test_weekly_report_shows_unavailable_summary_when_llm_unconfigured(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "", raising=False)

    report = build_weekly_optimisation_report()

    assert "AI SUMMARY (deepseek/deepseek-chat)" in report
    assert "unavailable (LLM not configured or unreachable)" in report


def test_weekly_report_includes_generated_summary_when_llm_configured(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(
        llm_module, "generate_text", lambda **kwargs: "Scale the top campaign this week."
    )

    report = build_weekly_optimisation_report()

    assert "AI SUMMARY (deepseek/deepseek-chat)" in report
    assert "Scale the top campaign this week." in report


def test_weekly_report_labels_the_summary_with_the_active_model(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "LLM_MODEL", "gemini/gemini-1.5-flash", raising=False)
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "gm-test", raising=False)
    monkeypatch.setattr(
        llm_module, "generate_text", lambda **kwargs: "Gemini's take on this week."
    )

    report = build_weekly_optimisation_report()

    assert "AI SUMMARY (gemini/gemini-1.5-flash)" in report
    assert "Gemini's take on this week." in report


def test_weekly_report_has_one_recommendation_per_category():
    report = build_weekly_optimisation_report()

    assert "SCALE UP" in report
    assert "PAUSE" in report
    assert "REWRITE" in report


def test_weekly_report_names_the_deliberately_bad_ad_set_to_pause():
    report = build_weekly_optimisation_report()

    assert "- Ad set: adset_retarget_bad" in report


def test_weekly_report_names_the_underperforming_landing_page():
    report = build_weekly_optimisation_report()

    assert "- Page: lp_buyers_v1" in report


def test_weekly_report_states_it_never_executes():
    report = build_weekly_optimisation_report()

    assert "nothing below has been executed automatically" in report.lower()


def test_weekly_report_scale_and_pause_never_recommend_unattributed():
    report = build_weekly_optimisation_report()

    assert "Campaign: unattributed" not in report
    assert "Ad set: unattributed" not in report


def test_weekly_report_mentions_content_strategist_best_effort_notification():
    report = build_weekly_optimisation_report()

    assert "CONTENT STRATEGIST NOTIFICATION" in report
    assert "acknowledged (best-effort" in report


def test_weekly_report_labels_are_plain_language_not_raw_kpi_jargon():
    """The report must spell out what CPQL/CPL/ROAS mean, not just the acronym,
    so an operator with no technical background can read it unaided."""

    report = build_weekly_optimisation_report()

    assert "Cost per SQL (CPQL)" in report
    assert "Cost per lead (CPL)" in report
    assert "ROAS (Return on Ad Spend)" in report


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
    assert "WEEKLY OPTIMISATION REPORT" in sent["text"]


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
