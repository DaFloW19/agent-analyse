"""Best-effort notification to Content Strategist about underperforming pages.

Content Strategist's real `/cro-analysis` endpoint (verified against its
actual code, not just its docs) accepts only `{"conversion_rate": float}` --
no page identifier, no `client_id`. There is structurally no way for this
call to tell Content Strategist *which* page is underperforming; the
recommendations it returns are generic, threshold-based advice. This is a
known gap on their side, not something this module can work around -- it
calls the endpoint anyway (per team decision), logs the response itself so
the flagged page and the advice are at least correlated on our end, and
documents the limitation rather than pretending it's a real integration.
"""

from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from common.logging import log_action
from config.settings import settings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def _post_cro_analysis(base_url: str, conversion_rate: float) -> dict:
    """POST one conversion rate to Content Strategist's `/cro-analysis`."""

    import httpx

    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{base_url}/cro-analysis", json={"conversion_rate": conversion_rate}
        )
        response.raise_for_status()
        return response.json()


def notify_content_strategist_of_flagged_pages(
    flagged_pages: list[dict], client_id: str
) -> list[dict]:
    """Notify Content Strategist (best-effort) about every flagged page.

    Args:
        flagged_pages: Pages from `landing_page_performance` where
            `below_threshold` is True.
        client_id: Client identifier, used only for our own logging --
            Content Strategist's endpoint doesn't accept one.

    Returns:
        list[dict]: One `{page, issue, recommendations}` entry per page
        that was successfully notified. Pages skipped because Content
        Strategist was unreachable are omitted, not raised as an error.
    """

    base_url = settings.get("CONTENT_STRATEGIST_URL")
    if not base_url:
        return []

    results = []
    for page in flagged_pages:
        try:
            response = _post_cro_analysis(base_url, page["conversion_rate_pct"])
            results.append(
                {
                    "page": page["landing_page"],
                    "issue": response.get("issue"),
                    "recommendations": response.get("recommendations", []),
                }
            )
            log_action(
                agent_name="analyst",
                action_type="notify_content_strategist",
                input_summary=(
                    f"Flagged {page['landing_page']} at "
                    f"{page['conversion_rate_pct']:.2f}% conversion"
                ),
                output_summary=(
                    f"issue={response.get('issue')}; "
                    f"{len(response.get('recommendations', []))} recommendation(s) returned "
                    "(Content Strategist's API has no page identifier -- this correlation "
                    "only exists on our side)"
                ),
                lead_id=None,
                client_id=client_id,
                model_used="rule-based",
                latency_ms=0,
            )
        except Exception as exc:  # noqa: BLE001 - unreachable Content Strategist must never crash caller
            log_action(
                agent_name="analyst",
                action_type="notify_content_strategist_failed",
                input_summary=(
                    f"Attempted to notify Content Strategist about {page['landing_page']}"
                ),
                output_summary="Continuing without a response for this page.",
                lead_id=None,
                client_id=client_id,
                model_used="rule-based",
                latency_ms=0,
                extra_fields={"error_type": type(exc).__name__, "error_message": str(exc)},
            )
    return results
