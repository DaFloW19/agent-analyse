import agents.analyst.live_data as live_data_module
from agents.analyst.data_pull import pull_kpi_report
from agents.analyst.seed_data import load_seed_dataset
from common import metrics


def _force_simulated(monkeypatch):
    """Force both live sources unreachable so pull_kpi_report falls back to seed data."""

    monkeypatch.setattr(live_data_module, "fetch_crm_keeper_leads", lambda client_id: None)
    monkeypatch.setattr(live_data_module, "fetch_media_buyer_spend", lambda: None)


def test_pull_kpi_report_matches_direct_metrics_calls_when_simulated(monkeypatch):
    """B1 test spec: every KPI must match a direct call to `common.metrics`
    with the exact same source rows — no arithmetic may live outside it."""

    _force_simulated(monkeypatch)
    dataset = load_seed_dataset()
    report = pull_kpi_report(dataset)

    assert report["cpl"] == {
        **metrics.cpl(dataset.spend_rows, dataset.leads),
        "source": "simulated",
    }
    assert report["cpq"] == {
        **metrics.cpq(dataset.spend_rows, dataset.leads),
        "source": "simulated",
    }
    assert report["cpql"] == {
        **metrics.cpql(dataset.spend_rows, dataset.leads),
        "source": "simulated",
    }
    assert report["cpbd"] == {
        **metrics.cpbd(dataset.spend_rows, dataset.booking_rows),
        "source": "simulated",
    }
    assert report["roas"] == {
        **metrics.roas(dataset.spend_rows, dataset.deal_rows),
        "source": "simulated",
    }
    assert report["stage_conversion_rate"] == {
        **metrics.stage_conversion_rate(dataset.transition_rows, from_stage="new", to_stage="mql"),
        "source": "simulated",
    }
    assert report["time_to_first_contact"] == {
        **metrics.time_to_first_contact(dataset.contact_rows),
        "source": "simulated",
    }
    assert report["response_rate"] == {
        **metrics.response_rate(dataset.contact_rows),
        "source": "simulated",
    }
    assert report["meeting_show_rate"] == {
        **metrics.meeting_show_rate(dataset.meeting_rows),
        "source": "simulated",
    }


def test_pull_kpi_report_defaults_to_cached_seed_dataset(monkeypatch):
    _force_simulated(monkeypatch)

    default_report = pull_kpi_report()
    explicit_report = pull_kpi_report(load_seed_dataset())

    assert default_report == explicit_report


def test_pull_kpi_report_uses_live_data_when_both_sources_reachable(monkeypatch):
    live_leads = [
        {"lead_id": "ld_1", "score": 80, "lead_stage": "sql", "data_as_of": "2026-08-01T00:00:00Z"},
        {"lead_id": "ld_2", "score": 20, "lead_stage": "new", "data_as_of": "2026-08-01T00:00:00Z"},
    ]
    monkeypatch.setattr(live_data_module, "fetch_crm_keeper_leads", lambda client_id: live_leads)
    monkeypatch.setattr(
        live_data_module,
        "fetch_media_buyer_spend",
        lambda: {"spend": 100.0, "data_as_of": "2026-08-01T00:00:00Z"},
    )

    report = pull_kpi_report()

    assert report["cpl"]["source"] == "live"
    assert report["cpl"]["value"] == 50.0  # 100 spend / 2 leads
    assert report["stage_conversion_rate"]["source"] == "live"
    # ROAS and CPBD have no live equivalent -- always simulated regardless of the above.
    assert report["roas"]["source"] == "simulated"
    assert report["cpbd"]["source"] == "simulated"


def test_pull_kpi_report_falls_back_to_simulated_when_only_one_live_source_available(monkeypatch):
    """Partial live data (e.g. CRM Keeper up, Media Buyer down) must not mix
    real and fake numbers -- fall back to fully simulated instead."""

    monkeypatch.setattr(live_data_module, "fetch_crm_keeper_leads", lambda client_id: [])
    monkeypatch.setattr(live_data_module, "fetch_media_buyer_spend", lambda: None)

    report = pull_kpi_report()

    assert report["cpl"]["source"] == "simulated"
