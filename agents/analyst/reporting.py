"""Phase A hardcoded reporting helpers for the Analyst."""

from agents.analyst import demo_data
from common import metrics


KPI_LABELS = {
    "cpl": "CPL",
    "cpq": "CPQ",
    "cpql": "CPQL",
    "cpbd": "CPBD",
    "roas": "ROAS",
    "stage_conversion_rate": "Stage conversion",
    "time_to_first_contact": "Time to first contact",
    "response_rate": "Response rate",
    "meeting_show_rate": "Meeting show rate",
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


def build_phase_a_report() -> dict[str, dict[str, float | str | None]]:
    """Build the Phase A KPI report from hardcoded local demo data.

    Returns:
        dict[str, dict[str, float | str | None]]: Nine canonical KPI results.
    """

    return {
        "cpl": metrics.cpl(demo_data.SPEND_ROWS, demo_data.LEAD_ROWS),
        "cpq": metrics.cpq(demo_data.SPEND_ROWS, demo_data.LEAD_ROWS),
        "cpql": metrics.cpql(demo_data.SPEND_ROWS, demo_data.LEAD_ROWS),
        "cpbd": metrics.cpbd(demo_data.SPEND_ROWS, demo_data.BOOKING_ROWS),
        "roas": metrics.roas(demo_data.SPEND_ROWS, demo_data.DEAL_ROWS),
        "stage_conversion_rate": metrics.stage_conversion_rate(
            demo_data.TRANSITION_ROWS,
            from_stage="new",
            to_stage="mql",
        ),
        "time_to_first_contact": metrics.time_to_first_contact(demo_data.CONTACT_ROWS),
        "response_rate": metrics.response_rate(demo_data.CONTACT_ROWS),
        "meeting_show_rate": metrics.meeting_show_rate(demo_data.MEETING_ROWS),
    }


def format_report_for_telegram(report: dict[str, dict[str, float | str | None]]) -> str:
    """Format KPI report values for a compact Telegram response.

    Args:
        report: KPI report returned by `build_phase_a_report`.

    Returns:
        str: Human-readable report text.
    """

    lines = ["Analyst Phase A Report", "Client: demo-real-estate", ""]
    for metric_name, result in report.items():
        label = KPI_LABELS.get(metric_name, metric_name)
        rendered_value = _format_metric_value(metric_name, result["value"])
        lines.append(f"{label}: {rendered_value}")
    lines.append("")
    lines.append(f"Data as of: {_oldest_report_timestamp(report)}")
    return "\n".join(lines)


def build_conversion_drop_alerts(
    weekly_rows: list[dict[str, float | int | str]],
    threshold_pct: float = 50.0,
) -> list[dict[str, float | int | str]]:
    """Find stage conversion drops greater than the configured threshold.

    Args:
        weekly_rows: Rows with previous/current conversion rates and denominators.
        threshold_pct: Percentage drop threshold that triggers an alert.

    Returns:
        list[dict[str, float | int | str]]: Alert rows for transitions breaching the threshold.
    """

    alerts = []
    for row in weekly_rows:
        previous_rate = float(row["previous_rate"])
        current_rate = float(row["current_rate"])
        if previous_rate == 0:
            continue

        drop_pct = ((previous_rate - current_rate) / previous_rate) * 100
        if drop_pct > threshold_pct:
            alerts.append(
                {
                    "transition": row["transition"],
                    "label": row["label"],
                    "previous_rate": previous_rate,
                    "current_rate": current_rate,
                    "drop_pct": drop_pct,
                    "previous_denominator": int(row["previous_denominator"]),
                    "current_denominator": int(row["current_denominator"]),
                    "data_as_of": row["data_as_of"],
                }
            )
    return alerts


def build_phase_a_alerts() -> list[dict[str, float | int | str]]:
    """Build Phase A conversion-drop alerts from hardcoded weekly demo data.

    Returns:
        list[dict[str, float | int | str]]: Alerts for conversion drops above 50%.
    """

    return build_conversion_drop_alerts(demo_data.WEEKLY_STAGE_CONVERSION_ROWS)


def format_alerts_for_telegram(alerts: list[dict[str, float | int | str]]) -> str:
    """Format conversion-drop alerts for Telegram.

    Args:
        alerts: Alert rows returned by `build_phase_a_alerts`.

    Returns:
        str: Telegram-ready alert text.
    """

    if not alerts:
        return "Conversion Alerts\n\nNo conversion drop above 50% detected."

    lines = ["Conversion Alerts", ""]
    for alert in alerts:
        lines.extend(
            [
                f"Alert: {alert['label']}",
                f"Drop: {alert['previous_rate']:.2f}% -> {alert['current_rate']:.2f}%",
                f"Change: -{alert['drop_pct']:.2f}%",
                (
                    "Volume: "
                    f"{alert['previous_denominator']} leads previous week, "
                    f"{alert['current_denominator']} leads current week"
                ),
                f"Data as of: {alert['data_as_of']}",
                "Action: route to Commander for immediate review.",
                "",
            ]
        )
    return "\n".join(lines).strip()


def format_weekly_report_for_telegram(
    report: dict[str, dict[str, float | str | None]],
    alerts: list[dict[str, float | int | str]],
) -> str:
    """Format the weekly Analyst report with KPI dashboard and alerts.

    Args:
        report: KPI report returned by `build_phase_a_report`.
        alerts: Conversion-drop alerts.

    Returns:
        str: Telegram-ready weekly report.
    """

    kpi_lines = format_report_for_telegram(report).splitlines()
    kpi_lines[0] = "Weekly Analyst Report"
    alert_summary = (
        "Immediate alerts: none"
        if not alerts
        else f"Immediate alerts: {len(alerts)} conversion drop detected"
    )
    return "\n".join([*kpi_lines, "", alert_summary, "", format_alerts_for_telegram(alerts)])


def _format_metric_value(metric_name: str, value: float | str | None) -> str:
    """Render a KPI value with the expected Phase A unit.

    Args:
        metric_name: Canonical KPI key.
        value: Raw KPI value.

    Returns:
        str: Telegram-ready KPI value.
    """

    if value is None or isinstance(value, str):
        return "no data"

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
