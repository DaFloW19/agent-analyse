from agents.analyst.attribution import attribution_breakdown
from agents.analyst.seed_data import load_seed_dataset


def test_deliberately_bad_ad_set_is_bottom_performer():
    dataset = load_seed_dataset()

    result = attribution_breakdown(dataset.spend_rows, dataset.leads, "ad_set")

    assert result["bottom_performer"]["key"] == "adset_retarget_bad"


def test_unattributed_leads_appear_in_explicit_bucket_not_dropped():
    dataset = load_seed_dataset()

    result = attribution_breakdown(dataset.spend_rows, dataset.leads, "campaign")

    assert "unattributed" in result["by_group"]
    unattributed_leads = [lead for lead in dataset.leads if lead["campaign"] is None]
    assert len(unattributed_leads) > 0


def test_ranked_excludes_nothing_and_orders_best_to_worst():
    dataset = load_seed_dataset()

    result = attribution_breakdown(dataset.spend_rows, dataset.leads, "campaign")

    assert set(result["ranked"]) == set(result["by_group"])
    assert result["ranked"][0] == result["top_performer"]["key"]
    assert result["ranked"][-1] == result["bottom_performer"]["key"]


def test_group_with_no_sql_leads_ranks_worst():
    spend_rows = [{"spend": 100, "campaign": "a", "data_as_of": "2026-07-29T10:00:00Z"}]
    lead_rows = [
        {"lead_id": "lead-1", "score": 80, "campaign": "b", "data_as_of": "2026-07-29T10:00:00Z"},
        {"lead_id": "lead-2", "score": 20, "campaign": "a", "data_as_of": "2026-07-29T10:00:00Z"},
    ]
    spend_rows.append({"spend": 100, "campaign": "b", "data_as_of": "2026-07-29T10:00:00Z"})

    result = attribution_breakdown(spend_rows, lead_rows, "campaign")

    assert result["by_group"]["a"]["cpql"]["value"] is None
    assert result["bottom_performer"]["key"] == "a"
    assert result["top_performer"]["key"] == "b"
