"""Phase B reporting helpers for the Analyst: KPI report and anomaly alerts."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from agents.analyst.data_pull import pull_kpi_report
from agents.analyst.seed_data import load_seed_dataset
from common.logging import log_action
from config.settings import settings

KPI_LABELS = {
    "cpl": "CPL (coût par lead)",
    "cpq": "CPQ (coût par lead qualifié)",
    "cpql": "CPQL (coût par vente qualifiée)",
    "cpbd": "CPBD (coût par rendez-vous réservé)",
    "roas": "ROAS (retour sur investissement publicitaire)",
    "stage_conversion_rate": "Taux de conversion",
    "time_to_first_contact": "Temps 1er contact",
    "response_rate": "Taux de réponse",
    "meeting_show_rate": "Taux de présence",
}

KPI_UNITS = {
    "cpl": "cost",
    "cpq": "cost",
    "cpql": "cost",
    "cpbd": "cost",
    "roas": "ratio",
    "stage_conversion_rate": "percent",
    "time_to_first_contact": "minutes",
    "response_rate": "percent",
    "meeting_show_rate": "percent",
}

# Grouping used by format_report_for_telegram's two boxed sections.
PERFORMANCE_KPIS = ["cpl", "cpq", "cpql", "cpbd", "roas"]
CONVERSION_KPIS = [
    "stage_conversion_rate",
    "time_to_first_contact",
    "response_rate",
    "meeting_show_rate",
]


def build_phase_a_report() -> dict[str, dict[str, float | str | None]]:
    """Build the Phase B KPI report from the Analyst seed dataset.

    Returns:
        dict[str, dict[str, float | str | None]]: Nine canonical KPI results.
    """

    return pull_kpi_report()


def mark_stale(
    report: dict[str, dict[str, float | str | None]],
    now: datetime,
    stale_after_hours: int | None = None,
) -> dict[str, dict[str, float | str | None]]:
    """Flag KPI results whose source data is older than the freshness window.

    Args:
        report: KPI report returned by `build_phase_a_report`.
        now: Reference timestamp to compare each `data_as_of` against.
            Passed in explicitly so this function stays pure and testable
            (never calls `datetime.now()` itself).
        stale_after_hours: Hours after which a figure is considered stale.
            Defaults to `settings.analyst.stale_after_hours`.

    Returns:
        dict[str, dict[str, float | str | None]]: The same report with a
        `stale` boolean added to every KPI result. A result with no
        `data_as_of` (no data at all) is never marked stale.
    """

    window = timedelta(hours=stale_after_hours or settings.analyst.stale_after_hours)
    marked = {}
    for metric_name, result in report.items():
        data_as_of = result.get("data_as_of")
        stale = False
        if isinstance(data_as_of, str) and data_as_of:
            source_time = datetime.fromisoformat(data_as_of.replace("Z", "+00:00"))
            stale = (now - source_time) > window
        marked[metric_name] = {**result, "stale": stale}
    return marked


def attach_week_over_week(
    report: dict[str, dict[str, float | str | None]],
    now: datetime,
    client_id: str | None = None,
) -> dict[str, dict[str, float | str | None]]:
    """Attach each KPI's value from ~7 days ago, from stored snapshots.

    Snapshots are written once a week by the Monday scheduler job
    (`scheduler.py`), never on every manual `/report` call. A database
    outage or a metric with no prior snapshot both degrade to "no prior
    snapshot" shown in the report, never a crash.

    Args:
        report: KPI report returned by `build_phase_a_report`.
        now: Reference timestamp to look ~7 days back from. Passed in
            explicitly so this function stays pure and testable (never
            calls `datetime.now()` itself).
        client_id: Client identifier. Defaults to
            `settings.analyst.client_id`.

    Returns:
        dict[str, dict[str, float | str | None]]: The same report with a
        `previous_value` key added to every KPI result (`None` when no
        snapshot exists for that metric yet).
    """

    from common.db import get_closest_kpi_snapshot

    active_client_id = client_id or settings.analyst.client_id
    target_time = now - timedelta(days=7)

    enriched = {}
    for metric_name, result in report.items():
        try:
            previous_value = get_closest_kpi_snapshot(active_client_id, metric_name, target_time)
        except Exception:  # noqa: BLE001 - a snapshot lookup failure must never block the report
            previous_value = None
        enriched[metric_name] = {**result, "previous_value": previous_value}
    return enriched


def save_kpi_snapshots(
    report: dict[str, dict[str, float | str | None]],
    captured_at: datetime,
    client_id: str | None = None,
) -> None:
    """Persist one snapshot row per KPI for future week-on-week comparison.

    Called once a week by the Monday scheduler job, never on every manual
    `/report` call, to avoid noisy near-duplicate rows.

    Args:
        report: KPI report returned by `build_phase_a_report`.
        captured_at: Timestamp to record against every snapshot row.
        client_id: Client identifier. Defaults to
            `settings.analyst.client_id`.
    """

    from common.db import write_kpi_snapshot

    active_client_id = client_id or settings.analyst.client_id
    for metric_name, result in report.items():
        try:
            write_kpi_snapshot(active_client_id, metric_name, result.get("value"), captured_at)
        except Exception as exc:  # noqa: BLE001 - a DB outage must never stop the weekly job
            log_action(
                agent_name="analyst",
                action_type="kpi_snapshot_write_failed",
                input_summary=f"Attempted to save a snapshot for {metric_name}",
                output_summary="Continuing without this snapshot.",
                lead_id=None,
                client_id=active_client_id,
                model_used="rule-based",
                latency_ms=0,
                extra_fields={"error_type": type(exc).__name__, "error_message": str(exc)},
            )


def format_report_for_telegram(report: dict[str, dict[str, float | str | None]]) -> str:
    """Format the KPI report as a boxed, grouped, French Telegram message.

    Args:
        report: KPI report returned by `build_phase_a_report`, optionally
            passed through `mark_stale` and/or `attach_week_over_week` first.

    Returns:
        str: Human-readable French report text, grouped into "KPIs de
        performance" (CPL/CPQ/CPQL/CPBD/ROAS) and "KPIs de conversion"
        (the four rate/timing metrics), each line showing the working
        (numerator/denominator) and, when present, the week-on-week delta.
        Stale/simulated figures are flagged inline.
    """

    lines = [
        "📊 Rapport KPI - Agent Analyst",
        "",
        "┌─────────────────────────",
        "│ KPIs de performance",
        "├─────────────────────────",
    ]
    lines.extend(
        _format_kpi_line(name, report[name]) for name in PERFORMANCE_KPIS if name in report
    )
    lines.append("")
    lines.append("├─────────────────────────")
    lines.append("│ KPIs de conversion")
    lines.append("├─────────────────────────")
    lines.extend(
        _format_kpi_line(name, report[name]) for name in CONVERSION_KPIS if name in report
    )
    lines.append("")
    lines.append("└─────────────────────────")
    lines.append(f"🕐 Données du {_oldest_report_timestamp(report)}")
    return "\n".join(lines)


def _format_kpi_line(metric_name: str, result: dict[str, float | str | None]) -> str:
    """Render one KPI as a single French report line.

    Args:
        metric_name: Canonical KPI key.
        result: KPI result, optionally carrying `stale`/`source`/
            `previous_value` keys added by other reporting functions.

    Returns:
        str: `"{label}: {valeur}{delta}{alertes} (basé sur {num} / {denom})"`.
    """

    label = KPI_LABELS.get(metric_name, metric_name)
    rendered_value = _format_metric_value(metric_name, result["value"])
    delta_suffix = _format_delta_suffix(metric_name, result)
    stale_suffix = " ⚠️ [périmé]" if result.get("stale") else ""
    simulated_suffix = " (simulé)" if result.get("source") == "simulated" else ""
    working_suffix = _format_working_suffix(result)
    return (
        f"{label}: {rendered_value}{delta_suffix}{stale_suffix}{simulated_suffix}{working_suffix}"
    )


def _format_delta_suffix(metric_name: str, result: dict[str, float | str | None]) -> str:
    """Render the week-on-week delta suffix for one KPI result, if present.

    Args:
        metric_name: Canonical KPI key.
        result: KPI result, optionally carrying a `previous_value` key added
            by `attach_week_over_week` (None or absent = no prior snapshot).

    Returns:
        str: A ` (⬆️/⬇️/➡️ +delta%)`-style suffix, or an empty string when
        no prior snapshot exists or the current value itself is unavailable.
    """

    if "previous_value" not in result:
        return ""

    value = result.get("value")
    previous_value = result.get("previous_value")
    if value is None or previous_value is None:
        return " (pas de référence précédente)"

    delta = value - previous_value
    arrow = "⬆️" if delta > 0 else "⬇️" if delta < 0 else "➡️"
    sign = "+" if delta >= 0 else ""
    unit = KPI_UNITS.get(metric_name)
    if unit == "percent":
        return f" ({arrow} {sign}{delta:.1f}%)"
    return f" ({arrow} {sign}{delta:.2f})"


def _format_working_suffix(result: dict[str, float | str | None]) -> str:
    """Render the "(basé sur numérateur / dénominateur)" transparency suffix.

    Args:
        result: KPI result carrying `numerator`/`denominator`, as every
            `common.metrics` function returns.

    Returns:
        str: `"  (basé sur X / Y)"`, or an empty string when the
        denominator is zero or missing (nothing meaningful to show).
    """

    numerator = result.get("numerator")
    denominator = result.get("denominator")
    if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)):
        return ""
    if denominator == 0:
        return ""
    return f"  (basé sur {numerator:.1f} / {denominator:.0f})"


def build_conversion_drop_alerts(
    weekly_rows: list[dict[str, float | int | str]],
    threshold_pct: float | None = None,
    min_denominator: int | None = None,
    *,
    client_id: str | None = None,
    log_path: str | Path = "logs/analyst.jsonl",
) -> list[dict[str, float | int | str]]:
    """Find stage conversion drops greater than the configured threshold.

    An alert fires only when BOTH conditions hold (ANA-03): the drop exceeds
    `threshold_pct`, AND both the previous and current period's denominator
    are at or above `min_denominator`. A drop below the volume floor is
    suppressed rather than alerted, and the suppression is logged with the
    counts so it is still visible in the audit trail.

    Args:
        weekly_rows: Rows with previous/current conversion rates and
            denominators.
        threshold_pct: Percentage drop threshold that triggers an alert.
            Defaults to `settings.analyst.anomaly_threshold_pct`.
        min_denominator: Minimum sample size required in both periods.
            Defaults to `settings.analyst.anomaly_min_denominator`.
        client_id: Client identifier for suppression logs. Defaults to
            `settings.analyst.client_id`.
        log_path: JSONL destination for suppression log entries.

    Returns:
        list[dict[str, float | int | str]]: Alert rows for transitions
        breaching the threshold at or above the volume floor.
    """

    active_threshold = (
        threshold_pct if threshold_pct is not None else settings.analyst.anomaly_threshold_pct
    )
    active_floor = (
        min_denominator if min_denominator is not None else settings.analyst.anomaly_min_denominator
    )
    active_client_id = client_id or settings.analyst.client_id

    alerts = []
    for row in weekly_rows:
        previous_rate = float(row["previous_rate"])
        current_rate = float(row["current_rate"])
        previous_denominator = int(row["previous_denominator"])
        current_denominator = int(row["current_denominator"])
        if previous_rate == 0:
            continue

        drop_pct = ((previous_rate - current_rate) / previous_rate) * 100
        if drop_pct <= active_threshold:
            continue

        if previous_denominator < active_floor or current_denominator < active_floor:
            log_action(
                agent_name="analyst",
                action_type="suppress_anomaly_alert",
                input_summary=(
                    f"{row['transition']}: drop {drop_pct:.2f}% exceeds threshold "
                    f"but below volume floor {active_floor}"
                ),
                output_summary=(
                    f"previous_denominator={previous_denominator}, "
                    f"current_denominator={current_denominator}"
                ),
                lead_id=None,
                client_id=active_client_id,
                model_used="rule-based",
                latency_ms=0,
                path=log_path,
            )
            continue

        alerts.append(
            {
                "transition": row["transition"],
                "label": row["label"],
                "previous_rate": previous_rate,
                "current_rate": current_rate,
                "drop_pct": drop_pct,
                "previous_denominator": previous_denominator,
                "current_denominator": current_denominator,
                "data_as_of": row["data_as_of"],
            }
        )
    return alerts


def build_phase_a_alerts(client_id: str | None = None) -> list[dict[str, float | int | str]]:
    """Build Phase B conversion-drop alerts from the Analyst seed dataset.

    Args:
        client_id: Client identifier for suppression logs. Defaults to
            `settings.analyst.client_id`.

    Returns:
        list[dict[str, float | int | str]]: Alerts above the drop threshold
        and at or above the ANA-03 volume floor.
    """

    dataset = load_seed_dataset()
    return build_conversion_drop_alerts(dataset.weekly_stage_conversion_rows, client_id=client_id)


def format_alerts_for_telegram(alerts: list[dict[str, float | int | str]]) -> str:
    """Format conversion-drop alerts for Telegram, in French.

    Args:
        alerts: Alert rows returned by `build_phase_a_alerts`.

    Returns:
        str: Telegram-ready alert text.
    """

    if not alerts:
        return (
            "🔔 Alertes de conversion\n\n"
            "Aucune chute de conversion au-dessus du seuil et du plancher de volume."
        )

    lines = ["🔔 Alertes de conversion", ""]
    for alert in alerts:
        lines.extend(
            [
                f"⚠️ Alerte : {alert['label']}",
                f"Chute : {alert['previous_rate']:.2f}% → {alert['current_rate']:.2f}%",
                f"Variation : -{alert['drop_pct']:.2f}%",
                (
                    "Volume : "
                    f"{alert['previous_denominator']} leads la semaine précédente, "
                    f"{alert['current_denominator']} leads cette semaine"
                ),
                f"Données du : {alert['data_as_of']}",
                "Action : à transmettre au Commander pour revue immédiate.",
                "",
            ]
        )
    return "\n".join(lines).strip()


def format_weekly_report_for_telegram(
    report: dict[str, dict[str, float | str | None]],
    alerts: list[dict[str, float | int | str]],
) -> str:
    """Format the weekly Analyst report with KPI dashboard and alerts, in French.

    Args:
        report: KPI report returned by `build_phase_a_report`.
        alerts: Conversion-drop alerts.

    Returns:
        str: Telegram-ready weekly report.
    """

    kpi_lines = format_report_for_telegram(report).splitlines()
    kpi_lines[0] = "📊 Rapport hebdomadaire - Agent Analyst"
    alert_summary = (
        "🔔 Alertes immédiates : aucune"
        if not alerts
        else f"🔔 Alertes immédiates : {len(alerts)} chute(s) de conversion détectée(s)"
    )
    return "\n".join([*kpi_lines, "", alert_summary, "", format_alerts_for_telegram(alerts)])


def _format_metric_value(metric_name: str, value: float | str | None) -> str:
    """Render a KPI value with the expected Phase B unit.

    Args:
        metric_name: Canonical KPI key.
        value: Raw KPI value.

    Returns:
        str: Telegram-ready KPI value.
    """

    if value is None or isinstance(value, str):
        return "Pas de données"

    unit = KPI_UNITS.get(metric_name)
    if unit == "cost":
        return f"{value:.2f}"
    if unit == "ratio":
        return f"{value:.2f}x"
    if unit == "percent":
        return f"{value:.2f}%"
    if unit == "minutes":
        return f"{value:.2f} min"
    return f"{value:.2f}"


def _oldest_report_timestamp(report: dict[str, dict[str, float | str | None]]) -> str:
    """Return the oldest timestamp across KPI results for report-level freshness.

    Args:
        report: KPI report returned by `build_phase_a_report`.

    Returns:
        str: Oldest `data_as_of` value, or `unknown`.
    """

    timestamps = [
        str(result["data_as_of"])
        for result in report.values()
        if isinstance(result.get("data_as_of"), str) and result["data_as_of"]
    ]
    return min(timestamps) if timestamps else "unknown"
