import dataclasses

from agents.analyst.predictive_roas import project_roas
from agents.analyst.seed_data import load_seed_dataset


def test_project_roas_returns_a_range_from_seeded_data():
    result = project_roas(load_seed_dataset())

    assert result["sufficient_data"] is True
    assert result["pipeline_volume"] > 0
    assert result["projected_revenue_low"] <= result["projected_revenue_high"]
    assert result["projected_revenue_low"] >= 0
    assert len(result["assumptions"]) > 0


def test_project_roas_returns_insufficient_data_for_thin_pipeline():
    dataset = load_seed_dataset()
    thin_dataset = dataclasses.replace(dataset, leads=dataset.leads[:5])

    result = project_roas(thin_dataset)

    assert result["sufficient_data"] is False
    assert "projected_revenue_low" not in result
