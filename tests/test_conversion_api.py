import dataclasses

from agents.analyst.conversion_api import (
    build_conversion_api_payload,
    run_conversion_api_push_job,
)
from agents.analyst.seed_data import load_seed_dataset


def test_build_conversion_api_payload_only_includes_deals_with_a_click_id():
    payload = build_conversion_api_payload(load_seed_dataset())

    assert payload["dry_run"] is True
    assert len(payload["pushed"]) > 0
    for row in payload["pushed"]:
        assert row["click_id"]
        assert row["contract_value"] > 0


def test_build_conversion_api_payload_excludes_and_counts_deals_without_a_click_id():
    dataset = load_seed_dataset()
    leads_without_click_ids = [
        {**lead, "click_id": None, "click_id_platform": None} for lead in dataset.leads
    ]
    stripped_dataset = dataclasses.replace(dataset, leads=leads_without_click_ids)

    payload = build_conversion_api_payload(stripped_dataset)

    assert payload["pushed"] == []
    assert payload["excluded_no_click_id"] == sum(
        1 for row in dataset.deal_rows if row["status"] == "closed_won"
    )


def test_run_conversion_api_push_job_returns_the_same_payload_shape():
    result = run_conversion_api_push_job(load_seed_dataset(), client_id="test-conversion-api")

    assert result["client_id"] == "test-conversion-api"
    assert result["dry_run"] is True
    assert "pushed" in result and "excluded_no_click_id" in result
