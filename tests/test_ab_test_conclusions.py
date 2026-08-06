from agents.analyst.ab_test_conclusions import evaluate_ab_tests
from agents.analyst.seed_data import load_seed_dataset


def _result_for(results: list[dict], group_id: str) -> dict:
    return next(result for result in results if result["variant_group_id"] == group_id)


def test_evaluate_ab_tests_declares_a_winner_with_a_real_difference():
    results = evaluate_ab_tests(load_seed_dataset())
    result = _result_for(results, "vg_hero_copy")

    assert result["status"] == "winner"
    assert result["winner_asset_id"] == "asset_hero_copy_b"
    assert result["p_value"] < 0.05


def test_evaluate_ab_tests_reports_no_winner_when_marginal():
    results = evaluate_ab_tests(load_seed_dataset())
    result = _result_for(results, "vg_cta_button")

    assert result["status"] == "no_winner"
    assert result["variant_a"]["rate"] is not None
    assert result["variant_b"]["rate"] is not None


def test_evaluate_ab_tests_reports_insufficient_data_below_the_conversion_floor():
    results = evaluate_ab_tests(load_seed_dataset())
    result = _result_for(results, "vg_headline")

    assert result["status"] == "insufficient_data"
