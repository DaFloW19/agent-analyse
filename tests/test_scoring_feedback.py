import dataclasses

from agents.analyst.scoring_feedback import build_calibration_proposals
from agents.analyst.seed_data import load_seed_dataset


def test_build_calibration_proposals_names_the_deliberately_overweighted_dimension():
    proposals = build_calibration_proposals(load_seed_dataset())

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["dimension"] == "contactability"
    assert proposal["suggested_direction"] == "decrease"
    assert proposal["evidence"]["sample_size_closed_won"] > 0
    assert proposal["evidence"]["sample_size_other"] > 0


def test_build_calibration_proposals_returns_empty_list_with_no_scoring_runs():
    dataset = load_seed_dataset()
    empty_dataset = dataclasses.replace(dataset, scoring_run_rows=[])

    assert build_calibration_proposals(empty_dataset) == []
