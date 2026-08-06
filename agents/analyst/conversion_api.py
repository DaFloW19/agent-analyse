"""Conversion API payload builder for the Analyst (Phase C, C1).

Weekly: compiles closed-won deals with a click ID into the payload Media
Buyer would push to Meta/Google via Conversion API. Deals with no click ID
are excluded and counted, never silently dropped.

Media Buyer's real `/capi/push-conversion` endpoint keys by `email` +
`pixel_id`, not `click_id` (verified against their actual code earlier this
project) -- our seed data has neither. This module builds and logs the
payload the ticket actually asks the Analyst to produce ("The Analyst
produces the payload; the Media Buyer executes it"), but does not call
Media Buyer's real endpoint with a shape it doesn't accept: that would
silently produce wrong results if ever pointed at a real server, not a
working integration. See `agents/analyst/README.md`'s "Known limitations"
for the real fix needed on their side.
"""

from __future__ import annotations

from agents.analyst.seed_data import SeedDataset
from common.logging import log_action
from config.settings import settings


def build_conversion_api_payload(dataset: SeedDataset, client_id: str | None = None) -> dict:
    """Compile closed-won deals with a click ID into a Conversion API payload.

    Args:
        dataset: Seed dataset supplying leads and deal outcomes.
        client_id: Client identifier for the result payload. Defaults to
            `settings.analyst.client_id`.

    Returns:
        dict: `{client_id, pushed: [{lead_id, click_id, click_id_platform,
        contract_value, closed_at}], excluded_no_click_id, dry_run}`.
        `excluded_no_click_id` counts closed-won deals with no click ID,
        excluded from `pushed` rather than sent with a fabricated one.
    """

    active_client_id = client_id or settings.analyst.client_id
    leads_by_id = {lead["lead_id"]: lead for lead in dataset.leads}

    pushed = []
    excluded = 0
    for deal in dataset.deal_rows:
        if deal["status"] != "closed_won":
            continue
        lead = leads_by_id.get(deal["lead_id"])
        click_id = lead.get("click_id") if lead else None
        if not click_id:
            excluded += 1
            continue
        pushed.append(
            {
                "lead_id": deal["lead_id"],
                "click_id": click_id,
                "click_id_platform": lead.get("click_id_platform"),
                "contract_value": deal["contract_value"],
                "closed_at": deal["data_as_of"],
            }
        )

    return {
        "client_id": active_client_id,
        "pushed": pushed,
        "excluded_no_click_id": excluded,
        "dry_run": True,
    }


def run_conversion_api_push_job(dataset: SeedDataset, client_id: str | None = None) -> dict:
    """Build the weekly Conversion API payload and log it (dry-run only).

    Never calls Media Buyer's real endpoint -- see this module's docstring
    for why. This is the Analyst's own audit trail of what *would* be
    pushed, ready to wire up once a real click ID source and a matching
    Media Buyer endpoint both exist.

    Args:
        dataset: Seed dataset supplying leads and deal outcomes.
        client_id: Client identifier. Defaults to `settings.analyst.client_id`.

    Returns:
        dict: Same shape as `build_conversion_api_payload`.
    """

    active_client_id = client_id or settings.analyst.client_id
    payload = build_conversion_api_payload(dataset, active_client_id)

    log_action(
        agent_name="analyst",
        action_type="conversion_api_push",
        input_summary=f"Compiled closed-won deals with click IDs for {active_client_id}",
        output_summary=(
            f"{len(payload['pushed'])} deal(s) ready to push, "
            f"{payload['excluded_no_click_id']} excluded for missing a click ID"
        ),
        lead_id=None,
        client_id=active_client_id,
        model_used="rule-based",
        latency_ms=0,
        extra_fields={
            "dry_run": True,
            "note": (
                "Payload built and logged only -- Media Buyer's real "
                "/capi/push-conversion endpoint keys by email+pixel_id, not "
                "click_id, so it is not called here."
            ),
        },
    )
    return payload
