"""Weekly optimisation report and its scheduler bootstrap (B6).

Generates a report with concrete recommended actions (scale a campaign,
pause an ad set, rewrite an asset) each backed by supporting figures. The
Analyst never executes anything — the report is only ever sent, standing in
for "sent to the Commander" until a real Commander agent exists.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from agents.analyst import content_strategist_notify
from agents.analyst.attribution import attribution_breakdown
from agents.analyst.data_pull import pull_kpi_report
from agents.analyst.landing_pages import landing_page_performance
from agents.analyst.reporting import (
    build_phase_a_alerts,
    format_alerts_for_telegram,
    save_kpi_snapshots,
)
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
    flagged_pages = [page for page in landing_pages if page["below_threshold"]]

    lines = [
        f"WEEKLY OPTIMISATION REPORT - {active_client_id}",
        "The Analyst only recommends. Nothing below has been executed automatically.",
        "",
    ]
    lines.extend(_scale_recommendations(campaign_attribution))
    lines.extend(_pause_recommendations(ad_set_attribution))
    lines.extend(_rewrite_recommendations(landing_pages))

    if flagged_pages:
        notified = content_strategist_notify.notify_content_strategist_of_flagged_pages(
            flagged_pages, active_client_id
        )
        lines.append("CONTENT STRATEGIST NOTIFICATION")
        lines.append(
            f"- {len(notified)} of {len(flagged_pages)} flagged page(s) acknowledged "
            "(best-effort - their system has no page identifier yet, so this match only "
            "exists in our own logs)"
        )
        lines.append("")

    overall_roas = report["roas"]["value"]
    lines.append("OVERALL PERFORMANCE")
    if overall_roas is not None:
        lines.append(
            f"- ROAS (Return on Ad Spend): {overall_roas:.2f}x "
            f"- every 1 unit of ad spend returned {overall_roas:.2f}"
        )
    else:
        lines.append("- ROAS (Return on Ad Spend): no data")
    lines.append("")

    summary = _generate_plain_language_summary(
        client_id=active_client_id,
        scale_key=_best_attributed_key(campaign_attribution),
        pause_key=_worst_attributed_key(ad_set_attribution),
        flagged_pages=flagged_pages,
        overall_roas=overall_roas,
    )
    from common.llm import active_model

    lines.append(f"AI SUMMARY ({active_model()})")
    lines.append(summary or "unavailable (LLM not configured or unreachable)")

    return "\n".join(lines)


def _generate_plain_language_summary(
    *,
    client_id: str,
    scale_key: str | None,
    pause_key: str | None,
    flagged_pages: list[dict],
    overall_roas: float | None,
) -> str | None:
    """Ask the active LLM for a short plain-language summary of this week's report.

    The provider is whatever `common.llm.active_model()` resolves to
    (DeepSeek by default, overridable via `LLM_MODEL`).

    Args:
        client_id: Client identifier.
        scale_key: Best-attributed campaign key, or None.
        pause_key: Worst-attributed ad set key, or None.
        flagged_pages: Landing pages below the 15% conversion threshold.
        overall_roas: Overall ROAS value, or None when there is no data.

    Returns:
        str | None: A 2-3 sentence summary, or None when the active
        provider is not configured or unreachable -- the caller must treat
        this exactly like "no data", never crash or block on it.
    """

    from common.llm import generate_text

    system_prompt = (
        "You are the Analyst agent's reporting assistant. Summarise this week's "
        "optimisation report in 2 to 3 concise sentences for a non-technical "
        "operator. Only reference the campaign, ad set, pages, and figures given "
        "below -- never invent one that is not explicitly provided."
    )
    rewrite_text = ", ".join(page["landing_page"] for page in flagged_pages) or "none"
    roas_text = f"{overall_roas:.2f}x" if overall_roas is not None else "no data"
    user_prompt = (
        f"Client: {client_id}\n"
        f"Recommended to scale: {scale_key or 'none'}\n"
        f"Recommended to pause: {pause_key or 'none'}\n"
        f"Landing pages to rewrite: {rewrite_text}\n"
        f"Overall ROAS: {roas_text}"
    )
    return generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        agent_name="analyst",
        client_id=client_id,
        phase="phase_b_weekly_summary",
    )


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
        return [
            "SCALE UP - increase budget on this campaign",
            "- No campaign has enough SQL volume yet to recommend scaling.",
            "",
        ]

    cpql_value = campaign_attribution["by_group"][key]["cpql"]["value"]
    return [
        "SCALE UP - increase budget on this campaign",
        f"- Campaign: {key}",
        f"- Cost per SQL (CPQL): {cpql_value:.2f}",
        "- Why: the lowest cost per qualified sale across all attributed campaigns",
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
        return [
            "PAUSE - stop spending on this ad set",
            "- No attributed ad set stands out as underperforming.",
            "",
        ]

    group = ad_set_attribution["by_group"][key]
    cpql_value = group["cpql"]["value"]
    cpql_text = "no SQL leads yet" if cpql_value is None else f"{cpql_value:.2f}"
    return [
        "PAUSE - stop spending on this ad set",
        f"- Ad set: {key}",
        f"- Cost per SQL (CPQL): {cpql_text}",
        f"- Cost per lead (CPL): {group['cpl']['value']:.2f}",
        "- Why: the highest cost per qualified sale across all attributed ad sets",
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
        return [
            "REWRITE - underperforming landing pages",
            "- No landing page is below the 15% visitor-to-form threshold.",
            "",
        ]

    lines = ["REWRITE - these landing pages are underperforming"]
    for page in flagged:
        lines.append(f"- Page: {page['landing_page']}")
        lines.append(
            f"  Conversion rate: {page['conversion_rate_pct']:.2f}% "
            f"({page['form_submissions']} form submissions out of {page['visitors']} visitors) "
            "- below the 15% minimum threshold"
        )
    lines.append("")
    return lines


async def run_weekly_report_job(send: SendCallable, client_id: str | None = None) -> None:
    """Build the weekly report, snapshot this week's KPIs, then send.

    Extracted from `start_scheduler` so it can be called and tested
    directly, without needing a running `AsyncIOScheduler`.

    Args:
        send: Async callable that delivers the report text.
        client_id: Client identifier. Defaults to `settings.analyst.client_id`.
    """

    active_client_id = client_id or settings.analyst.client_id
    report_text = build_weekly_optimisation_report(client_id)
    report = pull_kpi_report(load_seed_dataset(), client_id=active_client_id)
    save_kpi_snapshots(report, datetime.now(UTC), active_client_id)
    await send(report_text)


async def run_anomaly_watch_job(send: SendCallable, client_id: str | None = None) -> None:
    """Check for conversion-drop anomalies and push an alert if any fire.

    Unlike `/alerts` (pull, on operator request), this job pushes
    automatically -- but only when there is something to say, never an
    empty "all clear" message on every run.

    Args:
        send: Async callable that delivers the alert text.
        client_id: Client identifier. Defaults to `settings.analyst.client_id`.
    """

    active_client_id = client_id or settings.analyst.client_id
    alerts = build_phase_a_alerts(active_client_id)
    if alerts:
        await send(format_alerts_for_telegram(alerts))


def start_scheduler(send: SendCallable, client_id: str | None = None) -> object:
    """Start the Analyst's two background jobs: weekly report and anomaly watch.

    Args:
        send: Async callable that delivers report/alert text (e.g. a
            Telegram send-message coroutine).
        client_id: Client identifier passed through to both jobs.

    Returns:
        object: The running `AsyncIOScheduler` instance, so the caller can
        shut it down.
    """

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: run_weekly_report_job(send, client_id),
        CronTrigger(day_of_week="mon", hour=8, minute=0),
    )
    scheduler.add_job(
        lambda: run_anomaly_watch_job(send, client_id),
        IntervalTrigger(hours=6),
    )
    scheduler.start()
    return scheduler
