import asyncio

import agents.analyst.scheduler as scheduler_module
import common.llm as llm_module
from agents.analyst.scheduler import (
    build_weekly_optimisation_report,
    run_anomaly_watch_job,
    run_weekly_report_job,
)


def test_weekly_report_shows_unavailable_summary_when_deepseek_unconfigured(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "", raising=False)

    report = build_weekly_optimisation_report()

    assert "AI summary (DeepSeek):" in report
    assert "unavailable (DeepSeek not configured or unreachable)" in report


def test_weekly_report_includes_generated_summary_when_deepseek_configured(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "DEEPSEEK_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(
        llm_module, "generate_text", lambda **kwargs: "Scale the top campaign this week."
    )

    report = build_weekly_optimisation_report()

    assert "AI summary (DeepSeek):" in report
    assert "Scale the top campaign this week." in report


def test_weekly_report_has_one_recommendation_per_category():
    report = build_weekly_optimisation_report()

    assert "Scale:" in report
    assert "Pause:" in report
    assert "Rewrite:" in report


def test_weekly_report_names_the_deliberately_bad_ad_set_to_pause():
    report = build_weekly_optimisation_report()

    assert "Pause: adset_retarget_bad" in report


def test_weekly_report_names_the_underperforming_landing_page():
    report = build_weekly_optimisation_report()

    assert "Rewrite: lp_buyers_v1" in report


def test_weekly_report_states_it_never_executes():
    report = build_weekly_optimisation_report()

    assert "no action below has been executed" in report.lower()


def test_weekly_report_scale_and_pause_never_recommend_unattributed():
    report = build_weekly_optimisation_report()

    assert "Scale: unattributed" not in report
    assert "Pause: unattributed" not in report


def test_weekly_report_mentions_content_strategist_best_effort_notification():
    report = build_weekly_optimisation_report()

    assert "Content Strategist notified (best-effort)" in report


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
    assert "Weekly Optimisation Report" in sent["text"]


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
