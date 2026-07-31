import json
from datetime import UTC, datetime, timedelta

from agents.analyst.reporting import build_conversion_drop_alerts, build_phase_a_report, mark_stale


def test_small_sample_drop_is_suppressed_not_alerted(tmp_path):
    """ANA-03: 6 -> 3 leads is ordinary variance, not a signal."""

    log_path = tmp_path / "alerts.jsonl"
    rows = [
        {
            "transition": "sql_to_booked",
            "label": "SQL to Booked",
            "previous_rate": 40.0,
            "current_rate": 15.0,
            "previous_denominator": 6,
            "current_denominator": 3,
            "data_as_of": "2026-07-29T10:00:00Z",
        }
    ]

    alerts = build_conversion_drop_alerts(rows, client_id="demo-real-estate", log_path=log_path)

    assert alerts == []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["action_type"] == "suppress_anomaly_alert"
    assert "previous_denominator=6" in entry["output_summary"]
    assert "current_denominator=3" in entry["output_summary"]


def test_large_sample_drop_alerts_with_context(tmp_path):
    """ANA-03: 40 -> 18 leads is real signal, above the volume floor."""

    log_path = tmp_path / "alerts.jsonl"
    rows = [
        {
            "transition": "mql_to_sql",
            "label": "MQL to SQL",
            "previous_rate": 40.0,
            "current_rate": 18.0,
            "previous_denominator": 40,
            "current_denominator": 40,
            "data_as_of": "2026-07-29T10:00:00Z",
        }
    ]

    alerts = build_conversion_drop_alerts(rows, client_id="demo-real-estate", log_path=log_path)

    assert len(alerts) == 1
    assert alerts[0]["previous_denominator"] == 40
    assert alerts[0]["current_denominator"] == 40
    assert not log_path.exists()


def test_drop_below_threshold_is_neither_alerted_nor_logged(tmp_path):
    log_path = tmp_path / "alerts.jsonl"
    rows = [
        {
            "transition": "mql_to_sql",
            "label": "MQL to SQL",
            "previous_rate": 50.0,
            "current_rate": 35.0,
            "previous_denominator": 80,
            "current_denominator": 75,
            "data_as_of": "2026-07-29T10:00:00Z",
        }
    ]

    alerts = build_conversion_drop_alerts(rows, client_id="demo-real-estate", log_path=log_path)

    assert alerts == []
    assert not log_path.exists()


def test_mark_stale_flags_figures_older_than_the_window():
    report = build_phase_a_report()
    data_as_of = datetime.fromisoformat(report["cpl"]["data_as_of"].replace("Z", "+00:00"))
    now = data_as_of + timedelta(hours=7)

    marked = mark_stale(report, now=now, stale_after_hours=6)

    assert all(result["stale"] for result in marked.values())


def test_mark_stale_leaves_fresh_figures_unflagged():
    report = build_phase_a_report()
    data_as_of = datetime.fromisoformat(report["cpl"]["data_as_of"].replace("Z", "+00:00"))
    now = data_as_of + timedelta(hours=1)

    marked = mark_stale(report, now=now, stale_after_hours=6)

    assert all(result["stale"] is False for result in marked.values())


def test_mark_stale_never_flags_missing_data():
    report = {"cpl": {"value": None, "numerator": 0.0, "denominator": 0.0, "data_as_of": None}}

    marked = mark_stale(report, now=datetime.now(UTC), stale_after_hours=6)

    assert marked["cpl"]["stale"] is False
