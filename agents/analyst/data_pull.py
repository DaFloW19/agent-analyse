"""Phase B data pull layer for the Analyst (B1).

Shapes source-of-truth rows from the seed dataset into the row formats
`common.metrics` expects. No KPI arithmetic lives here — every number is
computed by `common.metrics`, the single canonical place KPIs are defined.
"""

from __future__ import annotations

from agents.analyst.seed_data import SeedDataset, load_seed_dataset
from common import metrics


def pull_kpi_report(
    dataset: SeedDataset | None = None,
) -> dict[str, dict[str, float | str | None]]:
    """Pull the nine canonical KPIs from the Analyst seed dataset.

    Args:
        dataset: Seed dataset to read from. Defaults to the cached
            module-level seed dataset when omitted.

    Returns:
        dict[str, dict[str, float | str | None]]: Nine canonical KPI results,
        each shaped `{value, numerator, denominator, data_as_of}`.
    """

    data = dataset or load_seed_dataset()
    return {
        "cpl": metrics.cpl(data.spend_rows, data.leads),
        "cpq": metrics.cpq(data.spend_rows, data.leads),
        "cpql": metrics.cpql(data.spend_rows, data.leads),
        "cpbd": metrics.cpbd(data.spend_rows, data.booking_rows),
        "roas": metrics.roas(data.spend_rows, data.deal_rows),
        "stage_conversion_rate": metrics.stage_conversion_rate(
            data.transition_rows, from_stage="new", to_stage="mql"
        ),
        "time_to_first_contact": metrics.time_to_first_contact(data.contact_rows),
        "response_rate": metrics.response_rate(data.contact_rows),
        "meeting_show_rate": metrics.meeting_show_rate(data.meeting_rows),
    }
