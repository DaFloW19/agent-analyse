"""Predictive ROAS for the Analyst (Phase C, C2).

Projects expected closed-won revenue over the next N days from the current
SQL pipeline volume and historical booking/close rates. Always a range, never
a single number, with the assumptions used listed alongside it -- per the
ticket's explicit requirement ("Output a range, not a single number, and
state the assumptions used"). Needs no data from any other agent: entirely
derivable from the Analyst's own seed dataset (or, in future, a live-sourced
equivalent with the same shape).
"""

from __future__ import annotations

from agents.analyst.seed_data import SeedDataset
from common.metrics import confidence_interval_on_rate
from config.settings import settings

DEFAULT_PROJECTION_DAYS = 30
CONFIDENCE_LEVEL = 0.95


def project_roas(
    dataset: SeedDataset,
    days: int = DEFAULT_PROJECTION_DAYS,
    client_id: str | None = None,
) -> dict:
    """Project expected closed-won revenue over the next `days` days.

    Args:
        dataset: Seed dataset supplying current SQL leads, booking outcomes,
            and deal outcomes.
        days: Projection window in days.
        client_id: Client identifier for the result payload. Defaults to
            `settings.analyst.client_id`.

    Returns:
        dict: `{client_id, sufficient_data, pipeline_volume, days}`. When
        `sufficient_data` is True, also carries `booking_rate` and
        `close_rate` (each `{rate, lower, upper}` from
        `common.metrics.confidence_interval_on_rate`), `avg_contract_value`,
        `projected_revenue_low`, `projected_revenue_high`, and `assumptions`
        (list[str]). When False (pipeline volume below
        `settings.analyst.anomaly_min_denominator`, or no historical
        booking/deal data to build a rate from), only the first four keys --
        never a fabricated number for a thin pipeline.
    """

    active_client_id = client_id or settings.analyst.client_id
    min_volume = settings.analyst.anomaly_min_denominator

    sql_leads = [
        lead for lead in dataset.leads if lead.get("score") is not None and lead["score"] >= 61
    ]
    pipeline_volume = len(sql_leads)

    insufficient = {
        "client_id": active_client_id,
        "sufficient_data": False,
        "pipeline_volume": pipeline_volume,
        "days": days,
    }
    if pipeline_volume < min_volume or not dataset.booking_rows or not dataset.deal_rows:
        return insufficient

    booked_count = sum(1 for row in dataset.booking_rows if row["booked"])
    booking_ci = confidence_interval_on_rate(
        booked_count, len(dataset.booking_rows), CONFIDENCE_LEVEL
    )

    closed_won_count = sum(1 for row in dataset.deal_rows if row["status"] == "closed_won")
    close_ci = confidence_interval_on_rate(
        closed_won_count, len(dataset.deal_rows), CONFIDENCE_LEVEL
    )

    won_values = [
        row["contract_value"] for row in dataset.deal_rows if row["status"] == "closed_won"
    ]
    avg_contract_value = sum(won_values) / len(won_values) if won_values else None

    if booking_ci["rate"] is None or close_ci["rate"] is None or avg_contract_value is None:
        return insufficient

    projected_low = pipeline_volume * booking_ci["lower"] * close_ci["lower"] * avg_contract_value
    projected_high = pipeline_volume * booking_ci["upper"] * close_ci["upper"] * avg_contract_value

    return {
        "client_id": active_client_id,
        "sufficient_data": True,
        "pipeline_volume": pipeline_volume,
        "booking_rate": booking_ci,
        "close_rate": close_ci,
        "avg_contract_value": round(avg_contract_value, 2),
        "projected_revenue_low": round(projected_low, 2),
        "projected_revenue_high": round(projected_high, 2),
        "days": days,
        "assumptions": [
            f"{pipeline_volume} leads SQL actuellement dans le pipeline (score >= 61).",
            f"Taux de réservation historique {booking_ci['rate'] * 100:.1f}% "
            f"(IC 95% {booking_ci['lower'] * 100:.1f}-{booking_ci['upper'] * 100:.1f}%).",
            f"Taux de conclusion historique {close_ci['rate'] * 100:.1f}% "
            f"(IC 95% {close_ci['lower'] * 100:.1f}-{close_ci['upper'] * 100:.1f}%) "
            "des deals réservés conclus.",
            f"Valeur moyenne d'un contrat conclu : {avg_contract_value:.2f}.",
            f"Suppose que chaque lead SQL actuel dispose de {days} jours pour réserver "
            "et conclure (pas d'ajustement saisonnier ou de vélocité du pipeline).",
        ],
    }
