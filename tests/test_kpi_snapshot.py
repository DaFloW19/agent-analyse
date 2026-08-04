from datetime import UTC, datetime, timedelta

from agents.analyst.reporting import (
    attach_week_over_week,
    format_report_for_telegram,
    save_kpi_snapshots,
)
from common.db import get_closest_kpi_snapshot, write_kpi_snapshot


def test_write_and_read_closest_kpi_snapshot():
    captured_at = datetime(2026, 7, 25, 8, 0, tzinfo=UTC)
    write_kpi_snapshot("test-client-snapshot", "cpl", 42.5, captured_at)

    target = datetime(2026, 7, 25, 9, 0, tzinfo=UTC)
    assert get_closest_kpi_snapshot("test-client-snapshot", "cpl", target) == 42.5


def test_get_closest_kpi_snapshot_returns_none_when_no_snapshot_exists():
    assert get_closest_kpi_snapshot("never-seen-client", "cpl", datetime.now(UTC)) is None


def test_save_kpi_snapshots_writes_one_row_per_metric():
    now = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
    report = {
        "cpl": {"value": 10.0, "numerator": 100.0, "denominator": 10.0, "data_as_of": "x"},
        "roas": {"value": None, "numerator": 0.0, "denominator": 0.0, "data_as_of": None},
    }

    save_kpi_snapshots(report, now, client_id="test-client-save")

    assert get_closest_kpi_snapshot("test-client-save", "cpl", now) == 10.0
    assert get_closest_kpi_snapshot("test-client-save", "roas", now) is None


def test_attach_week_over_week_adds_previous_value_from_a_week_old_snapshot():
    now = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
    a_week_ago = now - timedelta(days=7)
    write_kpi_snapshot("test-client-wow", "cpl", 40.0, a_week_ago)

    report = {"cpl": {"value": 46.72, "numerator": 0.0, "denominator": 0.0, "data_as_of": "x"}}
    enriched = attach_week_over_week(report, now, client_id="test-client-wow")

    assert enriched["cpl"]["previous_value"] == 40.0
    assert enriched["cpl"]["value"] == 46.72


def test_attach_week_over_week_none_when_no_prior_snapshot():
    report = {"cpl": {"value": 46.72, "numerator": 0.0, "denominator": 0.0, "data_as_of": "x"}}

    enriched = attach_week_over_week(
        report, datetime.now(UTC), client_id="never-snapshotted-client"
    )

    assert enriched["cpl"]["previous_value"] is None


def test_format_report_shows_week_over_week_delta():
    report = {
        "cpl": {
            "value": 46.72,
            "numerator": 0.0,
            "denominator": 0.0,
            "data_as_of": "2026-08-03T08:00:00Z",
            "previous_value": 40.0,
        }
    }

    text = format_report_for_telegram(report)

    assert "⬆️ +6.72" in text


def test_format_report_shows_no_prior_snapshot_when_previous_value_is_none():
    report = {
        "cpl": {
            "value": 46.72,
            "numerator": 0.0,
            "denominator": 0.0,
            "data_as_of": "2026-08-03T08:00:00Z",
            "previous_value": None,
        }
    }

    text = format_report_for_telegram(report)

    assert "(pas de référence précédente)" in text


def test_format_report_flags_simulated_source():
    report = {
        "roas": {
            "value": 1.6,
            "numerator": 0.0,
            "denominator": 0.0,
            "data_as_of": "2026-08-03T08:00:00Z",
            "source": "simulated",
        }
    }

    text = format_report_for_telegram(report)

    assert "(simulé)" in text
