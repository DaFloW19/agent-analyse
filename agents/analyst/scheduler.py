"""Weekly optimisation report and its scheduler bootstrap (B6).

Generates a report with concrete recommended actions (scale a campaign,
pause an ad set, rewrite an asset) each backed by supporting figures. The
Analyst never executes anything — the report is only ever sent, standing in
for "sent to the Commander" until a real Commander agent exists.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from agents.analyst import content_strategist_notify
from agents.analyst.attribution import attribution_breakdown
from agents.analyst.data_pull import pull_kpi_report
from agents.analyst.landing_pages import landing_page_performance
from agents.analyst.reporting import (
    attach_week_over_week,
    build_phase_a_alerts,
    format_alerts_for_telegram,
    format_report_for_telegram,
    save_kpi_snapshots,
)
from agents.analyst.seed_data import load_seed_dataset
from config.settings import settings

SendCallable = Callable[[str], Awaitable[None]]


def build_weekly_optimisation_report(client_id: str | None = None) -> str:
    """Build the weekly optimisation report: KPI dashboard + concrete recommendations.

    Merges the same boxed, grouped French KPI dashboard `/report` shows
    (`reporting.format_report_for_telegram`) with the Analyst's own
    evidence-backed recommendations (scale/pause/rewrite) -- richer than a
    KPI-only report, but just as readable.

    Args:
        client_id: Client identifier shown in the report header. Defaults
            to `settings.analyst.client_id`.

    Returns:
        str: Telegram-ready report. The Analyst never executes any of
        these recommendations.
    """

    active_client_id = client_id or settings.analyst.client_id
    dataset = load_seed_dataset()
    report = attach_week_over_week(pull_kpi_report(dataset), datetime.now(UTC), active_client_id)

    ad_set_attribution = attribution_breakdown(dataset.spend_rows, dataset.leads, "ad_set")
    campaign_attribution = attribution_breakdown(dataset.spend_rows, dataset.leads, "campaign")
    landing_pages = landing_page_performance(dataset.landing_page_rows)
    flagged_pages = [page for page in landing_pages if page["below_threshold"]]

    now = datetime.now(UTC)
    period_start = now - timedelta(days=7)
    lines = [
        "📊 Rapport hebdomadaire d'optimisation - Agent Analyst",
        f"📅 Période : {period_start.date()} → {now.date()}",
        "",
    ]
    lines.extend(format_report_for_telegram(report).splitlines()[1:])
    lines.append("")
    lines.append(
        "💡 L'Analyst ne fait que recommander. "
        "Rien ci-dessous n'a été exécuté automatiquement."
    )
    lines.append("")
    lines.extend(_scale_recommendations(campaign_attribution))
    lines.extend(_pause_recommendations(ad_set_attribution))
    lines.extend(_rewrite_recommendations(landing_pages))

    if flagged_pages:
        notified = content_strategist_notify.notify_content_strategist_of_flagged_pages(
            flagged_pages, active_client_id
        )
        lines.append("📣 NOTIFICATION CONTENT STRATEGIST")
        lines.append(
            f"- {len(notified)}/{len(flagged_pages)} page(s) signalée(s) acquittée(s) "
            "(best-effort - leur système n'a pas encore d'identifiant de page, donc cette "
            "correspondance n'existe que dans nos propres logs)"
        )
        lines.append("")

    summary = _generate_plain_language_summary(
        client_id=active_client_id,
        scale_key=_best_attributed_key(campaign_attribution),
        pause_key=_worst_attributed_key(ad_set_attribution),
        flagged_pages=flagged_pages,
        overall_roas=report["roas"]["value"],
    )
    from common.llm import active_model

    lines.append(f"💡 Résumé IA ({active_model()})")
    lines.append(summary or "indisponible (LLM non configuré ou injoignable)")

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
        "Tu es l'assistant de reporting de l'agent Analyst. Résume le rapport "
        "d'optimisation de cette semaine en 2 à 3 phrases concises, en français, "
        "pour un opérateur non technique. Ne mentionne que la campagne, l'ad set, "
        "les pages et les chiffres donnés ci-dessous -- n'en invente jamais."
    )
    rewrite_text = ", ".join(page["landing_page"] for page in flagged_pages) or "aucune"
    roas_text = f"{overall_roas:.2f}x" if overall_roas is not None else "pas de données"
    user_prompt = (
        f"Client : {client_id}\n"
        f"Campagne à augmenter : {scale_key or 'aucune'}\n"
        f"Ad set à mettre en pause : {pause_key or 'aucun'}\n"
        f"Pages à réécrire : {rewrite_text}\n"
        f"ROAS global : {roas_text}"
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
            "⬆️ AUGMENTER - le budget de cette campagne",
            "- Aucune campagne n'a encore assez de volume SQL pour recommander une hausse.",
            "",
        ]

    cpql_value = campaign_attribution["by_group"][key]["cpql"]["value"]
    return [
        "⬆️ AUGMENTER - le budget de cette campagne",
        f"- Campagne : {key}",
        f"- Coût par SQL (CPQL) : {cpql_value:.2f}",
        "- Pourquoi : le coût par vente qualifiée le plus bas parmi les campagnes suivies",
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
            "⏸️ METTRE EN PAUSE - cet ad set",
            "- Aucun ad set attribué ne se distingue comme sous-performant.",
            "",
        ]

    group = ad_set_attribution["by_group"][key]
    cpql_value = group["cpql"]["value"]
    cpql_text = "aucun lead SQL encore" if cpql_value is None else f"{cpql_value:.2f}"
    return [
        "⏸️ METTRE EN PAUSE - cet ad set",
        f"- Ad set : {key}",
        f"- Coût par SQL (CPQL) : {cpql_text}",
        f"- Coût par lead (CPL) : {group['cpl']['value']:.2f}",
        "- Pourquoi : le coût par vente qualifiée le plus élevé parmi les ad sets suivis",
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
            "✏️ RÉÉCRIRE - pages sous-performantes",
            "- Aucune landing page n'est sous le seuil de 15% visiteur-vers-formulaire.",
            "",
        ]

    lines = ["✏️ RÉÉCRIRE - ces landing pages sous-performent"]
    for page in flagged:
        lines.append(f"- Page : {page['landing_page']}")
        lines.append(
            f"  Taux de conversion : {page['conversion_rate_pct']:.2f}% "
            f"({page['form_submissions']} formulaires soumis sur {page['visitors']} visiteurs) "
            "- sous le seuil minimum de 15%"
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
