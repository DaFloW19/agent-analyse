"""Scoring model feedback to the Qualifier (Phase C, C4).

Compares the Qualifier's scoring dimensions against actual closed-deal
outcomes to propose weight recalibrations -- never applied automatically,
only surfaced with evidence, per the ticket ("write them as proposals to a
calibration table -- never auto-apply").

The Qualifier's real `scoring_runs` table (QUA-01) doesn't exist in their
repo yet, so `seed_data.py::_build_scoring_run_rows` stands in for it with a
deliberately miscalibrated dimension (see its docstring). This module's
logic is data-shape-agnostic: point it at the real `scoring_runs` table once
QUA-01 exists and it works unchanged.
"""

from __future__ import annotations

from agents.analyst.seed_data import SeedDataset

# A dimension is proposed for recalibration only when it is the single most
# heavily weighted one AND its outcome lift ranks in the bottom half of all
# dimensions -- "the thing we trust most barely predicts the real outcome".
BOTTOM_HALF_LIFT_RANK = 2


def build_calibration_proposals(dataset: SeedDataset) -> list[dict]:
    """Propose scoring-dimension weight recalibrations from closed-deal outcomes.

    Args:
        dataset: Seed dataset supplying `scoring_run_rows` and `deal_rows`.

    Returns:
        list[dict]: Zero or one proposal (today's fixture has exactly one
        miscalibrated dimension; real data could surface more, or none), each
        `{dimension, current_weight, scoring_model_version, evidence:
        {avg_score_closed_won, avg_score_other, sample_size_closed_won,
        sample_size_other}, suggested_direction}`. Never applied -- purely
        informational, for a human to review.
    """

    closed_won_lead_ids = {
        row["lead_id"] for row in dataset.deal_rows if row["status"] == "closed_won"
    }

    won_scores: dict[str, list[float]] = {}
    other_scores: dict[str, list[float]] = {}
    weights: dict[str, float] = {}
    model_version: str | None = None

    for run in dataset.scoring_run_rows:
        model_version = run["scoring_model_version"]
        weights = run["weights_used"]
        bucket = won_scores if run["lead_id"] in closed_won_lead_ids else other_scores
        for dimension, score in run["dimension_scores"].items():
            bucket.setdefault(dimension, []).append(score)

    if not weights:
        return []

    dimensions = list(weights.keys())
    most_weighted = max(dimensions, key=lambda dimension: weights[dimension])
    lift_rank = sorted(
        dimensions,
        key=lambda dimension: abs(_lift(dimension, won_scores, other_scores)),
        reverse=True,
    )

    if lift_rank.index(most_weighted) < len(dimensions) - BOTTOM_HALF_LIFT_RANK:
        return []

    won = won_scores.get(most_weighted, [])
    other = other_scores.get(most_weighted, [])
    if not won or not other:
        return []

    return [
        {
            "dimension": most_weighted,
            "current_weight": weights[most_weighted],
            "scoring_model_version": model_version,
            "evidence": {
                "avg_score_closed_won": round(sum(won) / len(won), 1),
                "avg_score_other": round(sum(other) / len(other), 1),
                "sample_size_closed_won": len(won),
                "sample_size_other": len(other),
            },
            "suggested_direction": "decrease",
        }
    ]


def _lift(
    dimension: str,
    won_scores: dict[str, list[float]],
    other_scores: dict[str, list[float]],
) -> float:
    """Return a dimension's average-score gap between closed-won and other leads."""

    won = won_scores.get(dimension, [])
    other = other_scores.get(dimension, [])
    if not won or not other:
        return 0.0
    return (sum(won) / len(won)) - (sum(other) / len(other))
