"""A/B test conclusions for the Analyst (Phase C, C5).

Decides the winner of a Content Strategist A/B test using the same
two-proportion z-test already built in `common/metrics.py` -- the ticket
explicitly says not to reimplement it. Winner requires 95% confidence AND at
least 30 conversions per variant; below that, "insufficient data". Exactly
CCS-03's decision rule.

Content Strategist's real `content_assets` table (their own ticket, CCS-03)
doesn't exist in their repo yet, so `seed_data.py::_build_content_variant_rows`
stands in for it. This module's logic is data-shape-agnostic: point it at
the real table once CCS-03 exists and it works unchanged.
"""

from __future__ import annotations

from agents.analyst.seed_data import SeedDataset
from common.metrics import confidence_interval_on_rate, two_proportion_z_test

MIN_CONVERSIONS_PER_VARIANT = 30
CONFIDENCE_LEVEL = 0.95
SIGNIFICANCE_THRESHOLD = 1 - CONFIDENCE_LEVEL


def evaluate_ab_tests(dataset: SeedDataset) -> list[dict]:
    """Evaluate every A/B variant group for a statistically significant winner.

    Args:
        dataset: Seed dataset supplying `content_variant_rows`.

    Returns:
        list[dict]: One result per `variant_group_id`, sorted by group id:
        `{variant_group_id, status, ...}`. `status` is `"insufficient_data"`
        (below 30 conversions on either variant), `"no_winner"` (both
        variants at or above 30 conversions but the difference is not
        significant at 95% confidence -- carries each variant's
        `confidence_interval_on_rate`), or `"winner"` (carries the winning
        `winner_asset_id`/`winner_variant` and the test's `p_value`).
    """

    groups: dict[str, list[dict]] = {}
    for row in dataset.content_variant_rows:
        groups.setdefault(row["variant_group_id"], []).append(row)

    return [_evaluate_group(group_id, rows) for group_id, rows in sorted(groups.items())]


def _evaluate_group(group_id: str, rows: list[dict]) -> dict:
    """Evaluate one `variant_group_id`'s two variants against CCS-03's rule."""

    variant_a, variant_b = sorted(rows, key=lambda row: row["variant"])[:2]

    if (
        variant_a["conversions"] < MIN_CONVERSIONS_PER_VARIANT
        or variant_b["conversions"] < MIN_CONVERSIONS_PER_VARIANT
    ):
        return {"variant_group_id": group_id, "status": "insufficient_data"}

    test = two_proportion_z_test(
        variant_a["conversions"],
        variant_a["impressions"],
        variant_b["conversions"],
        variant_b["impressions"],
    )
    if test["p_value"] is not None and test["p_value"] < SIGNIFICANCE_THRESHOLD:
        winner = variant_a if test["rate_a"] > test["rate_b"] else variant_b
        return {
            "variant_group_id": group_id,
            "status": "winner",
            "winner_asset_id": winner["asset_id"],
            "winner_variant": winner["variant"],
            "p_value": test["p_value"],
        }

    return {
        "variant_group_id": group_id,
        "status": "no_winner",
        "variant_a": {
            "asset_id": variant_a["asset_id"],
            **confidence_interval_on_rate(
                variant_a["conversions"], variant_a["impressions"], CONFIDENCE_LEVEL
            ),
        },
        "variant_b": {
            "asset_id": variant_b["asset_id"],
            **confidence_interval_on_rate(
                variant_b["conversions"], variant_b["impressions"], CONFIDENCE_LEVEL
            ),
        },
    }
