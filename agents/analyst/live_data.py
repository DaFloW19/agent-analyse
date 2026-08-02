"""Best-effort live HTTP clients for CRM Keeper and Media Buyer.

Both fetch functions return `None` on any failure (unreachable service,
timeout, malformed response) -- an outage in a colleague's agent must never
crash the Analyst or block a report. `data_pull.py` falls back to the seed
dataset whenever either returns `None`.

Verified against the colleagues' actual FastAPI code (not just their
README): CRM Keeper's `LeadResponse` carries no deal/contract-value field,
and Media Buyer's `/performance/last-7-days` is a single account-level
aggregate, not broken down by campaign/ad set/creative asset. ROAS and the
B2 attribution breakdown therefore cannot be derived from these two
endpoints and stay on the seed dataset -- see `data_pull.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tenacity import retry, stop_after_attempt, wait_exponential

from common.logging import log_action
from config.settings import settings

CRM_KEEPER_STAGES = [
    "new",
    "mql",
    "sql",
    "contacted",
    "meeting_booked",
    "closed_won",
    "closed_lost",
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def _get_json(url: str, *, params: dict | None = None) -> object:
    """GET a URL and return its parsed JSON body, retrying transient failures.

    Args:
        url: Full request URL.
        params: Optional query parameters.

    Returns:
        The parsed JSON response body.

    Raises:
        Exception: Whatever `httpx` raises, after 3 failed attempts. Callers
            catch this and fall back to `None` -- an unreachable colleague
            service must never crash the Analyst.
    """

    import httpx

    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def fetch_crm_keeper_leads(client_id: str) -> list[dict] | None:
    """Pull every lead from CRM Keeper across all 7 pipeline stages.

    Calls `GET /crm/leads/stage/{stage_name}` once per stage (CRM Keeper
    has no "all leads" endpoint) and reshapes each `LeadResponse` into the
    row format `common.metrics` expects: `score` (from
    `qualification_score`), `lead_stage`, and `data_as_of` (from
    `created_at`).

    Args:
        client_id: Client identifier passed through as the `client_id`
            query parameter CRM Keeper expects.

    Returns:
        list[dict] | None: All leads across every stage, or `None` if CRM
        Keeper is unreachable. Never raises.
    """

    base_url = settings.get("CRM_KEEPER_URL")
    if not base_url:
        return None

    leads: list[dict] = []
    try:
        for stage in CRM_KEEPER_STAGES:
            payload = _get_json(
                f"{base_url}/crm/leads/stage/{stage}", params={"client_id": client_id}
            )
            for raw_lead in payload:
                leads.append(
                    {
                        "lead_id": raw_lead.get("lead_id"),
                        "score": raw_lead.get("qualification_score"),
                        "lead_stage": raw_lead.get("lead_stage"),
                        "data_as_of": raw_lead.get("created_at"),
                    }
                )
        return leads
    except Exception as exc:  # noqa: BLE001 - an unreachable CRM Keeper must never crash the caller
        _log_fetch_failure("crm_keeper", client_id, exc)
        return None


def fetch_media_buyer_spend() -> dict | None:
    """Pull the last-7-days account-level spend aggregate from Media Buyer.

    Media Buyer's own code silently returns an all-zero payload with HTTP
    200 when its internal Meta Ads client call fails, so a zero-spend
    result here is ambiguous between "genuinely no spend" and "the call
    failed upstream" -- treat it as best-effort, same as any other figure.

    Returns:
        dict | None: `{"spend": float, "data_as_of": <now, ISO 8601>}`, or
        `None` if Media Buyer is unreachable. Never raises.
    """

    base_url = settings.get("MEDIA_BUYER_URL")
    if not base_url:
        return None

    try:
        payload = _get_json(f"{base_url}/performance/last-7-days")
        data = payload.get("data", {})
        return {
            "spend": data.get("spend"),
            "data_as_of": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001 - an unreachable Media Buyer must never crash the caller
        _log_fetch_failure("media_buyer", "global", exc)
        return None


def _log_fetch_failure(source_agent: str, client_id: str, exc: Exception) -> None:
    """Log a live-data fetch failure without raising it to the caller."""

    log_action(
        agent_name="analyst",
        action_type="live_data_fetch_failed",
        input_summary=f"Attempted to fetch live data from {source_agent}",
        output_summary="Falling back to the seed dataset for this report.",
        lead_id=None,
        client_id=client_id,
        model_used="rule-based",
        latency_ms=0,
        extra_fields={"error_type": type(exc).__name__, "error_message": str(exc)},
    )
