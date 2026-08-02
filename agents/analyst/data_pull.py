"""Phase B data pull layer for the Analyst (B1).

Shapes source-of-truth rows into the row formats `common.metrics` expects.
No KPI arithmetic lives here -- every number is computed by
`common.metrics`, the single canonical place KPIs are defined.

CPL, CPQ, CPQL, and stage_conversion_rate are pulled live from CRM Keeper
and Media Buyer when both are reachable (see `live_data.py`), falling back
to the seed dataset otherwise. CPBD, ROAS, time_to_first_contact,
response_rate, and meeting_show_rate always come from the seed dataset:
neither CRM Keeper's `LeadResponse` nor Media Buyer's
`/performance/last-7-days` expose deal value, booking outcomes, or contact
timing (verified against their actual code, not just their docs). Every
result carries a `source` field ("live" or "simulated") added at this
layer -- `common/metrics.py` stays pure and source-agnostic.
"""

from __future__ import annotations

from agents.analyst import live_data
from agents.analyst.seed_data import SeedDataset, load_seed_dataset
from common import metrics
from config.settings import settings

STAGE_RANK = {stage: index for index, stage in enumerate(live_data.CRM_KEEPER_STAGES)}


def pull_kpi_report(
    dataset: SeedDataset | None = None,
    client_id: str | None = None,
) -> dict[str, dict[str, float | str | None]]:
    """Pull the nine canonical KPIs, live where possible, seeded otherwise.

    Args:
        dataset: Seed dataset used as the fallback/simulated source, and as
            the sole source for the five metrics live data cannot supply.
            Defaults to the cached module-level seed dataset when omitted.
        client_id: Client identifier passed to CRM Keeper. Defaults to
            `settings.analyst.client_id`.

    Returns:
        dict[str, dict[str, float | str | None]]: Nine canonical KPI
        results, each shaped `{value, numerator, denominator, data_as_of,
        source}`.
    """

    data = dataset or load_seed_dataset()
    active_client_id = client_id or settings.analyst.client_id

    live_leads = live_data.fetch_crm_keeper_leads(active_client_id)
    live_spend = live_data.fetch_media_buyer_spend()

    if live_leads is not None and live_spend is not None:
        spend_rows = [{"spend": live_spend["spend"], "data_as_of": live_spend["data_as_of"]}]
        cpl = metrics.cpl(spend_rows, live_leads)
        cpq = metrics.cpq(spend_rows, live_leads)
        cpql = metrics.cpql(spend_rows, live_leads)
        stage_conversion_rate = metrics.stage_conversion_rate(
            _approximate_transitions(live_leads), from_stage="new", to_stage="mql"
        )
        hybrid_source = "live"
    else:
        cpl = metrics.cpl(data.spend_rows, data.leads)
        cpq = metrics.cpq(data.spend_rows, data.leads)
        cpql = metrics.cpql(data.spend_rows, data.leads)
        stage_conversion_rate = metrics.stage_conversion_rate(
            data.transition_rows, from_stage="new", to_stage="mql"
        )
        hybrid_source = "simulated"

    return {
        "cpl": {**cpl, "source": hybrid_source},
        "cpq": {**cpq, "source": hybrid_source},
        "cpql": {**cpql, "source": hybrid_source},
        "cpbd": {**metrics.cpbd(data.spend_rows, data.booking_rows), "source": "simulated"},
        "roas": {**metrics.roas(data.spend_rows, data.deal_rows), "source": "simulated"},
        "stage_conversion_rate": {**stage_conversion_rate, "source": hybrid_source},
        "time_to_first_contact": {
            **metrics.time_to_first_contact(data.contact_rows),
            "source": "simulated",
        },
        "response_rate": {**metrics.response_rate(data.contact_rows), "source": "simulated"},
        "meeting_show_rate": {
            **metrics.meeting_show_rate(data.meeting_rows),
            "source": "simulated",
        },
    }


def _approximate_transitions(live_leads: list[dict]) -> list[dict]:
    """Approximate new->mql transition rows from CRM Keeper's current stages.

    CRM Keeper only exposes each lead's current stage, not its transition
    history. Since CRM Keeper enforces forward-only stage progression (its
    own `stage_order` config), a lead's current stage is a reliable lower
    bound on every stage it has passed through: any lead at `mql` or beyond
    has, by construction, passed through `mql`.

    Args:
        live_leads: Rows from `live_data.fetch_crm_keeper_leads`, each with
            a `lead_stage` field.

    Returns:
        list[dict]: One `{from_stage, to_stage, data_as_of}` row per lead,
        `to_stage="mql"` when the lead reached `mql` or beyond.
    """

    mql_rank = STAGE_RANK["mql"]
    rows = []
    for lead in live_leads:
        stage = lead.get("lead_stage")
        reached_mql = STAGE_RANK.get(stage, -1) >= mql_rank
        rows.append(
            {
                "from_stage": "new",
                "to_stage": "mql" if reached_mql else (stage or "new"),
                "data_as_of": lead.get("data_as_of"),
            }
        )
    return rows
