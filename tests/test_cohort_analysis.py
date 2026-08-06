import dataclasses

from agents.analyst.cohort_analysis import cohort_breakdown
from agents.analyst.seed_data import STRONG_CAMPAIGN, load_seed_dataset


def test_cohort_breakdown_by_campaign_identifies_the_deliberately_strong_cohort():
    result = cohort_breakdown(load_seed_dataset(), group_by="campaign")

    assert result["ranked"][0] == STRONG_CAMPAIGN
    assert STRONG_CAMPAIGN not in result["insufficient"]


def test_cohort_breakdown_by_campaign_never_drops_unattributed_leads():
    result = cohort_breakdown(load_seed_dataset(), group_by="campaign")

    assert "unattributed" in result["cohorts"]


def test_cohort_breakdown_flags_thin_cohorts_as_insufficient_not_ranked():
    dataset = load_seed_dataset()
    thin_dataset = dataclasses.replace(dataset, leads=dataset.leads[:5])

    result = cohort_breakdown(thin_dataset, group_by="campaign")

    assert set(result["ranked"]).isdisjoint(result["insufficient"])
    assert len(result["insufficient"]) > 0
