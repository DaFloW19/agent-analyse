from agents.analyst.data_pull import pull_kpi_report
from agents.analyst.seed_data import load_seed_dataset
from common import metrics


def test_pull_kpi_report_matches_direct_metrics_calls():
    """B1 test spec: every KPI must match a direct call to `common.metrics`
    with the exact same source rows — no arithmetic may live outside it."""

    dataset = load_seed_dataset()
    report = pull_kpi_report(dataset)

    assert report["cpl"] == metrics.cpl(dataset.spend_rows, dataset.leads)
    assert report["cpq"] == metrics.cpq(dataset.spend_rows, dataset.leads)
    assert report["cpql"] == metrics.cpql(dataset.spend_rows, dataset.leads)
    assert report["cpbd"] == metrics.cpbd(dataset.spend_rows, dataset.booking_rows)
    assert report["roas"] == metrics.roas(dataset.spend_rows, dataset.deal_rows)
    assert report["stage_conversion_rate"] == metrics.stage_conversion_rate(
        dataset.transition_rows, from_stage="new", to_stage="mql"
    )
    assert report["time_to_first_contact"] == metrics.time_to_first_contact(dataset.contact_rows)
    assert report["response_rate"] == metrics.response_rate(dataset.contact_rows)
    assert report["meeting_show_rate"] == metrics.meeting_show_rate(dataset.meeting_rows)


def test_pull_kpi_report_defaults_to_cached_seed_dataset():
    default_report = pull_kpi_report()
    explicit_report = pull_kpi_report(load_seed_dataset())

    assert default_report == explicit_report
