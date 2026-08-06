"""Cohort analysis for the Analyst (Phase C, C3).

Groups leads by acquisition week or campaign and compares each cohort's SQL
rate and closed-won rate, to identify which sources produce the best
long-term outcomes. Needs no data from any other agent -- entirely derivable
from the Analyst's own seed dataset (or, in future, a live-sourced
equivalent with the same shape).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from agents.analyst.seed_data import SeedDataset
from config.settings import settings

CohortKey = Literal["week", "campaign"]
UNATTRIBUTED = "unattributed"


def cohort_breakdown(dataset: SeedDataset, group_by: CohortKey = "campaign") -> dict:
    """Break lead quality and closed-won outcomes down by cohort.

    Args:
        dataset: Seed dataset supplying leads and deal outcomes.
        group_by: Cohort dimension -- acquisition `"week"` (ISO calendar
            week of `created_at`) or `"campaign"` (unattributed leads
            grouped under an explicit `"unattributed"` key, never dropped).

    Returns:
        dict: `{group_by, cohorts: {key: {lead_count, sql_rate_pct,
        closed_won_rate_pct}}, ranked, insufficient}`. `ranked` lists cohort
        keys at or above `settings.analyst.anomaly_min_denominator` leads,
        best-to-worst by closed-won rate. `insufficient` lists cohort keys
        below that floor -- still present in `cohorts` for transparency, but
        never ranked, per ANA-03's volume floor.
    """

    min_volume = settings.analyst.anomaly_min_denominator
    closed_won_lead_ids = {
        row["lead_id"] for row in dataset.deal_rows if row["status"] == "closed_won"
    }

    cohorts: dict[str, list[dict]] = {}
    for lead in dataset.leads:
        key = _cohort_key(lead, group_by)
        cohorts.setdefault(key, []).append(lead)

    results: dict[str, dict] = {}
    insufficient: list[str] = []
    for key, leads in cohorts.items():
        lead_count = len(leads)
        sql_count = sum(
            1 for lead in leads if lead.get("score") is not None and lead["score"] >= 61
        )
        closed_won_count = sum(1 for lead in leads if lead["lead_id"] in closed_won_lead_ids)
        results[key] = {
            "lead_count": lead_count,
            "sql_rate_pct": round(sql_count / lead_count * 100, 2) if lead_count else None,
            "closed_won_rate_pct": (
                round(closed_won_count / lead_count * 100, 2) if lead_count else None
            ),
        }
        if lead_count < min_volume:
            insufficient.append(key)

    ranked = sorted(
        (key for key in results if key not in insufficient),
        key=lambda key: results[key]["closed_won_rate_pct"] or 0.0,
        reverse=True,
    )

    return {
        "group_by": group_by,
        "cohorts": results,
        "ranked": ranked,
        "insufficient": sorted(insufficient),
    }


def _cohort_key(lead: dict, group_by: CohortKey) -> str:
    """Return a lead's cohort key for the given dimension."""

    if group_by == "campaign":
        return lead.get("campaign") or UNATTRIBUTED

    created_at = datetime.fromisoformat(lead["created_at"].replace("Z", "+00:00"))
    return created_at.strftime("%G-W%V")
