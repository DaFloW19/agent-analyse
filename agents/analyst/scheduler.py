"""Weekly optimisation report and its scheduler bootstrap (B6).

Generates a report with concrete recommended actions (scale a campaign,
pause an ad set, rewrite an asset) each backed by supporting figures. The
Analyst never executes anything — the report is only ever sent, standing in
for "sent to the Commander" until a real Commander agent exists.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from agents.analyst.attribution import attribution_breakdown
from agents.analyst.data_pull import pull_kpi_report
from agents.analyst.landing_pages import landing_page_performance
from agents.analyst.seed_data import load_seed_dataset
from config.settings import settings

SendCallable = Callable[[str], Awaitable[None]]


def build_weekly_optimisation_report(client_id: str | None = None) -> str:
    """Build the weekly optimisation report with concrete recommendations.

    Args:
        client_id: Client identifier shown in the report header. Defaults
            to `settings.analyst.client_id`.

    Returns:
        str: Telegram-ready report with one section per recommendation
        category (scale, pause, rewrite), each carrying its supporting
        figures. The Analyst never executes any of these recommendations.
    """

    active_client_id = client_id or settings.analyst.client_id
    dataset = load_seed_dataset()
    report = pull_kpi_report(dataset)

    ad_set_attribution = attribution_breakdown(dataset.spend_rows, dataset.leads, "ad_set")
    campaign_attribution = attribution_breakdown(dataset.spend_rows, dataset.leads, "campaign")
    landing_pages = landing_page_performance(dataset.landing_page_rows)

    lines = [
        "Weekly Optimisation Report (for Commander review)",
        f"Client: {active_client_id}",
        "The Analyst recommends only. No action below has been executed.",
        "",
    ]
    lines.extend(_scale_recommendations(campaign_attribution))
    lines.extend(_pause_recommendations(ad_set_attribution))
    lines.extend(_rewrite_recommendations(landing_pages))

    overall_roas = report["roas"]["value"]
    roas_line = (
        f"Overall ROAS this period: {overall_roas:.2f}x"
        if overall_roas is not None
        else "Overall ROAS: no data"
    )
    lines.append(roas_line)
    return "\n".join(lines)


def _scale_recommendations(campaign_attribution: dict) -> list[str]:
    """Build the 'scale' section from the best-performing attributed campaign.

    Args:
        campaign_attribution: Result of `attribution_breakdown(..., "campaign")`.

    Returns:
        list[str]: Report lines. `"unattributed"` is never recommended for
        scaling since there is no ad-platform lever to pull for it.
    """

    key = _best_attributed_key(campaign_attribution)
    if key is None:
        return ["Scale: no campaign has enough SQL volume yet to recommend scaling.", ""]

    cpql_value = campaign_attribution["by_group"][key]["cpql"]["value"]
    return [
        f"Scale: {key}",
        f"  CPQL {cpql_value:.2f} - lowest cost-per-SQL across attributed campaigns.",
        "",
    ]


def _pause_recommendations(ad_set_attribution: dict) -> list[str]:
    """Build the 'pause' section from the worst-performing attributed ad set.

    Args:
        ad_set_attribution: Result of `attribution_breakdown(..., "ad_set")`.

    Returns:
        list[str]: Report lines naming the worst attributed ad set and its
        figures. `"unattributed"` is never recommended for pausing.
    """

    key = _worst_attributed_key(ad_set_attribution)
    if key is None:
        return ["Pause: no attributed ad set stands out as underperforming.", ""]

    group = ad_set_attribution["by_group"][key]
    cpql_value = group["cpql"]["value"]
    cpql_text = "no SQL leads" if cpql_value is None else f"CPQL {cpql_value:.2f}"
    return [
        f"Pause: {key}",
        f"  {cpql_text}, CPL {group['cpl']['value']:.2f}"
        " - worst cost-per-SQL across attributed ad sets.",
        "",
    ]


def _best_attributed_key(attribution: dict) -> str | None:
    """Return the best-ranked attribution key, skipping `"unattributed"`."""

    for key in attribution["ranked"]:
        if key != "unattributed":
            return key
    return None


def _worst_attributed_key(attribution: dict) -> str | None:
    """Return the worst-ranked attribution key, skipping `"unattributed"`."""

    for key in reversed(attribution["ranked"]):
        if key != "unattributed":
            return key
    return None


def _rewrite_recommendations(landing_pages: list[dict]) -> list[str]:
    """Build the 'rewrite' section from underperforming landing pages.

    Args:
        landing_pages: Result of `landing_page_performance`.

    Returns:
        list[str]: Report lines, one per page below the 15% threshold.
    """

    flagged = [page for page in landing_pages if page["below_threshold"]]
    if not flagged:
        return ["Rewrite: no landing page is below the 15% visitor-to-form threshold.", ""]

    lines = []
    for page in flagged:
        lines.append(f"Rewrite: {page['landing_page']}")
        lines.append(
            f"  {page['conversion_rate_pct']:.2f}% visitor-to-form "
            f"({page['form_submissions']}/{page['visitors']}), below the 15% threshold."
        )
    lines.append("")
    return lines


def start_scheduler(send: SendCallable, client_id: str | None = None) -> object:
    """Start the APScheduler job that sends the weekly report every Monday.

    Args:
        send: Async callable that delivers the report text (e.g. a Telegram
            send-message coroutine).
        client_id: Client identifier passed through to the report builder.

    Returns:
        object: The running `AsyncIOScheduler` instance, so the caller can
        shut it down.
    """

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler()

    async def _job() -> None:
        """Build and send the weekly optimisation report."""

        await send(build_weekly_optimisation_report(client_id))

    scheduler.add_job(_job, CronTrigger(day_of_week="mon", hour=8, minute=0))
    scheduler.start()
    return scheduler
