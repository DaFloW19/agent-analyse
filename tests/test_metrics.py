import json
from pathlib import Path

import pytest

from common import metrics


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "metrics_fixture.json"


@pytest.fixture
def metrics_fixture():
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def assert_metric_matches(actual, expected):
    assert actual["value"] == pytest.approx(expected["value"])
    assert actual["numerator"] == pytest.approx(expected["numerator"])
    assert actual["denominator"] == pytest.approx(expected["denominator"])
    assert actual["data_as_of"] == expected["data_as_of"]


def test_all_canonical_kpis_match_hand_computed_fixture(metrics_fixture):
    expected = metrics_fixture["expected"]

    actual = {
        "cpl": metrics.cpl(metrics_fixture["spend_rows"], metrics_fixture["lead_rows"]),
        "cpq": metrics.cpq(metrics_fixture["spend_rows"], metrics_fixture["lead_rows"]),
        "cpql": metrics.cpql(metrics_fixture["spend_rows"], metrics_fixture["lead_rows"]),
        "cpbd": metrics.cpbd(metrics_fixture["spend_rows"], metrics_fixture["booking_rows"]),
        "roas": metrics.roas(metrics_fixture["spend_rows"], metrics_fixture["deal_rows"]),
        "stage_conversion_rate": metrics.stage_conversion_rate(
            metrics_fixture["transition_rows"],
            from_stage="new",
            to_stage="mql",
        ),
        "time_to_first_contact": metrics.time_to_first_contact(metrics_fixture["contact_rows"]),
        "response_rate": metrics.response_rate(metrics_fixture["contact_rows"]),
        "meeting_show_rate": metrics.meeting_show_rate(metrics_fixture["meeting_rows"]),
    }

    for metric_name, result in actual.items():
        assert_metric_matches(result, expected[metric_name])


def test_divide_by_zero_returns_no_data():
    result = metrics.cpl(spend_rows=[{"spend": 100, "data_as_of": "2026-07-29T09:00:00Z"}], lead_rows=[])

    assert result == {
        "value": None,
        "numerator": 100.0,
        "denominator": 0.0,
        "data_as_of": "2026-07-29T09:00:00Z",
    }


def test_two_proportion_z_test_reports_significant_difference():
    result = metrics.two_proportion_z_test(
        successes_a=40,
        total_a=100,
        successes_b=20,
        total_b=100,
    )

    assert result["rate_a"] == pytest.approx(0.4)
    assert result["rate_b"] == pytest.approx(0.2)
    assert result["z_score"] == pytest.approx(3.086, abs=0.001)
    assert result["p_value"] == pytest.approx(0.002, abs=0.001)


def test_confidence_interval_on_rate_returns_bounds():
    result = metrics.confidence_interval_on_rate(successes=40, total=100)

    assert result["rate"] == pytest.approx(0.4)
    assert result["lower"] == pytest.approx(0.304, abs=0.001)
    assert result["upper"] == pytest.approx(0.496, abs=0.001)

