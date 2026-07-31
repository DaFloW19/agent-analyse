"""Canonical KPI and statistical helpers for the Analyst system.

This module is the only place where project KPIs should be calculated. It is intentionally
side-effect free: no database calls, API calls, file reads, file writes, logging, or network access.
Callers must fetch and shape source data before passing it here.

Ambiguity resolutions:
    - A "day" is defined by the client's configured timezone before data reaches this module.
      Functions here operate on already-filtered rows and do not perform timezone bucketing.
    - A re-scored lead counts once for CPQ and CPQL, using the latest score supplied by the caller.
    - Spend means media spend only and excludes platform fees, agency fees, taxes, and tooling costs.
    - Divide-by-zero returns a metric result with value `None`, never 0.
    - KPI rate values are returned as percentages from 0 to 100.
    - ROAS is returned as a ratio, e.g. 3.0 means 3x.
    - For composite metrics, `data_as_of` is the oldest contributing source timestamp supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt
from typing import Any

MetricRow = dict[str, Any]


@dataclass(frozen=True)
class MetricResult:
    """Structured KPI result showing the calculation inputs.

    Args:
        value: Calculated KPI value, or None when the denominator is zero.
        numerator: Numerator used in the calculation.
        denominator: Denominator used in the calculation.
        data_as_of: Oldest contributing source timestamp, when available.
    """

    value: float | None
    numerator: float
    denominator: float
    data_as_of: str | None

    def as_dict(self) -> dict[str, float | str | None]:
        """Return the result as the API-friendly shape required by the work plan.

        Returns:
            dict[str, float | str | None]: Serializable metric result.
        """

        return {
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "data_as_of": self.data_as_of,
        }


def cpl(spend_rows: list[MetricRow], lead_rows: list[MetricRow]) -> dict[str, float | str | None]:
    """Calculate cost per lead.

    Args:
        spend_rows: Rows containing media spend in `spend`.
        lead_rows: Lead rows representing total form submissions.

    Returns:
        dict[str, float | str | None]: Total spend divided by total form submissions.
    """

    return _divide(
        numerator=_sum_field(spend_rows, "spend"),
        denominator=len(lead_rows),
        data_as_of=_oldest_data_as_of(spend_rows, lead_rows),
    )


def cpq(spend_rows: list[MetricRow], lead_rows: list[MetricRow]) -> dict[str, float | str | None]:
    """Calculate cost per qualified lead using score >= 31.

    Args:
        spend_rows: Rows containing media spend in `spend`.
        lead_rows: Lead rows containing a numeric `score`.

    Returns:
        dict[str, float | str | None]: Total spend divided by MQL-or-better leads.
    """

    qualified_count = _count_leads_at_or_above_score(lead_rows, 31)
    return _divide(_sum_field(spend_rows, "spend"), qualified_count, _oldest_data_as_of(spend_rows, lead_rows))


def cpql(spend_rows: list[MetricRow], lead_rows: list[MetricRow]) -> dict[str, float | str | None]:
    """Calculate cost per SQL using score >= 61.

    Args:
        spend_rows: Rows containing media spend in `spend`.
        lead_rows: Lead rows containing a numeric `score`.

    Returns:
        dict[str, float | str | None]: Total spend divided by SQL leads.
    """

    sql_count = _count_leads_at_or_above_score(lead_rows, 61)
    return _divide(_sum_field(spend_rows, "spend"), sql_count, _oldest_data_as_of(spend_rows, lead_rows))


def cpbd(spend_rows: list[MetricRow], booking_rows: list[MetricRow]) -> dict[str, float | str | None]:
    """Calculate cost per booked appointment.

    Args:
        spend_rows: Rows containing media spend in `spend`.
        booking_rows: Appointment rows where `booked` marks successful booking.

    Returns:
        dict[str, float | str | None]: Total spend divided by successfully booked appointments.
    """

    booked_count = sum(1 for row in booking_rows if row.get("booked") is True)
    return _divide(_sum_field(spend_rows, "spend"), booked_count, _oldest_data_as_of(spend_rows, booking_rows))


def roas(spend_rows: list[MetricRow], deal_rows: list[MetricRow]) -> dict[str, float | str | None]:
    """Calculate return on ad spend from closed-won contract value.

    Args:
        spend_rows: Rows containing media spend in `spend`.
        deal_rows: Deal rows containing `status` and `contract_value`.

    Returns:
        dict[str, float | str | None]: Closed-won contract value divided by total spend.
    """

    closed_won_value = sum(
        _as_float(row.get("contract_value"))
        for row in deal_rows
        if row.get("status") == "closed_won"
    )
    return _divide(closed_won_value, _sum_field(spend_rows, "spend"), _oldest_data_as_of(spend_rows, deal_rows))


def stage_conversion_rate(
    transition_rows: list[MetricRow],
    from_stage: str,
    to_stage: str,
) -> dict[str, float | str | None]:
    """Calculate stage-to-stage conversion rate as a percentage.

    Args:
        transition_rows: Rows with `from_stage` and `to_stage` transition fields.
        from_stage: Stage where the transition starts.
        to_stage: Stage considered a successful next step.

    Returns:
        dict[str, float | str | None]: Percentage of transitions from `from_stage` to `to_stage`.
    """

    denominator = sum(1 for row in transition_rows if row.get("from_stage") == from_stage)
    numerator = sum(
        1
        for row in transition_rows
        if row.get("from_stage") == from_stage and row.get("to_stage") == to_stage
    )
    return _percentage(numerator, denominator, _oldest_data_as_of(transition_rows))


def time_to_first_contact(contact_rows: list[MetricRow]) -> dict[str, float | str | None]:
    """Calculate average minutes from form submission to first Closer message.

    Args:
        contact_rows: Rows containing `submitted_at` and `first_contact_at` ISO timestamps.

    Returns:
        dict[str, float | str | None]: Average first-contact delay in minutes.
    """

    durations = [
        _minutes_between(row.get("submitted_at"), row.get("first_contact_at"))
        for row in contact_rows
        if row.get("submitted_at") and row.get("first_contact_at")
    ]
    durations = [duration for duration in durations if duration is not None]
    return _divide(sum(durations), len(durations), _oldest_data_as_of(contact_rows))


def response_rate(contact_rows: list[MetricRow]) -> dict[str, float | str | None]:
    """Calculate first-contact response rate within 48 hours as a percentage.

    Args:
        contact_rows: Rows containing `first_contact_at` and optional `replied_at` ISO timestamps.

    Returns:
        dict[str, float | str | None]: Percentage of first-contact messages replied to within 48 hours.
    """

    eligible_rows = [row for row in contact_rows if row.get("first_contact_at")]
    replies_within_window = sum(1 for row in eligible_rows if _replied_within_hours(row, 48))
    return _percentage(replies_within_window, len(eligible_rows), _oldest_data_as_of(contact_rows))


def meeting_show_rate(meeting_rows: list[MetricRow]) -> dict[str, float | str | None]:
    """Calculate meeting show rate as a percentage.

    Args:
        meeting_rows: Rows containing `booked` and `showed` booleans.

    Returns:
        dict[str, float | str | None]: Percentage of booked meetings where the lead showed up.
    """

    booked_rows = [row for row in meeting_rows if row.get("booked") is True]
    showed_count = sum(1 for row in booked_rows if row.get("showed") is True)
    return _percentage(showed_count, len(booked_rows), _oldest_data_as_of(meeting_rows))


def two_proportion_z_test(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
) -> dict[str, float | None]:
    """Run a two-sided two-proportion z-test.

    Args:
        successes_a: Success count for variant A.
        total_a: Observation count for variant A.
        successes_b: Success count for variant B.
        total_b: Observation count for variant B.

    Returns:
        dict[str, float | None]: z-score, p-value, and observed rates.
    """

    if total_a == 0 or total_b == 0:
        return {"z_score": None, "p_value": None, "rate_a": None, "rate_b": None}

    rate_a = successes_a / total_a
    rate_b = successes_b / total_b
    pooled = (successes_a + successes_b) / (total_a + total_b)
    standard_error = sqrt(pooled * (1 - pooled) * ((1 / total_a) + (1 / total_b)))
    if standard_error == 0:
        return {"z_score": None, "p_value": None, "rate_a": rate_a, "rate_b": rate_b}

    z_score = (rate_a - rate_b) / standard_error
    p_value = 2 * (1 - _normal_cdf(abs(z_score)))
    return {"z_score": z_score, "p_value": p_value, "rate_a": rate_a, "rate_b": rate_b}


def confidence_interval_on_rate(
    successes: int,
    total: int,
    confidence_level: float = 0.95,
) -> dict[str, float | None]:
    """Calculate a normal-approximation confidence interval for a rate.

    Args:
        successes: Success count.
        total: Observation count.
        confidence_level: Confidence level. Currently supports 0.90, 0.95, and 0.99.

    Returns:
        dict[str, float | None]: Rate and lower/upper bounds.

    Raises:
        ValueError: If the confidence level is unsupported.
    """

    if confidence_level not in Z_SCORES:
        raise ValueError(f"Unsupported confidence level: {confidence_level}")

    if total == 0:
        return {"rate": None, "lower": None, "upper": None}

    rate = successes / total
    margin = Z_SCORES[confidence_level] * sqrt((rate * (1 - rate)) / total)
    return {
        "rate": rate,
        "lower": max(0.0, rate - margin),
        "upper": min(1.0, rate + margin),
    }


Z_SCORES = {
    0.90: 1.6448536269514722,
    0.95: 1.959963984540054,
    0.99: 2.5758293035489004,
}


def _divide(numerator: float, denominator: float, data_as_of: str | None) -> dict[str, float | str | None]:
    """Divide with project-standard zero-denominator behaviour."""

    value = None if denominator == 0 else numerator / denominator
    return MetricResult(value=value, numerator=numerator, denominator=float(denominator), data_as_of=data_as_of).as_dict()


def _percentage(numerator: float, denominator: float, data_as_of: str | None) -> dict[str, float | str | None]:
    """Return a percentage with project-standard zero-denominator behaviour."""

    result = _divide(float(numerator), float(denominator), data_as_of)
    if result["value"] is not None:
        result["value"] = result["value"] * 100
    return result


def _sum_field(rows: list[MetricRow], field_name: str) -> float:
    """Sum a numeric field from a list of metric rows."""

    return sum(_as_float(row.get(field_name)) for row in rows)


def _count_leads_at_or_above_score(lead_rows: list[MetricRow], score_floor: int) -> int:
    """Count leads with a numeric score at or above a floor."""

    return sum(1 for row in lead_rows if _is_number(row.get("score")) and row["score"] >= score_floor)


def _oldest_data_as_of(*row_groups: list[MetricRow]) -> str | None:
    """Return the oldest `data_as_of` timestamp from provided source rows."""

    values = [
        row["data_as_of"]
        for rows in row_groups
        for row in rows
        if isinstance(row.get("data_as_of"), str) and row["data_as_of"]
    ]
    return min(values) if values else None


def _minutes_between(start: Any, end: Any) -> float | None:
    """Return whole or fractional minutes between two ISO timestamps."""

    from datetime import datetime

    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (end_dt - start_dt).total_seconds() / 60


def _replied_within_hours(row: MetricRow, hours: int) -> bool:
    """Check whether a reply happened within a fixed number of hours."""

    minutes = _minutes_between(row.get("first_contact_at"), row.get("replied_at"))
    return minutes is not None and 0 <= minutes <= hours * 60


def _as_float(value: Any) -> float:
    """Convert numeric values to float and treat non-numeric values as 0."""

    if _is_number(value):
        return float(value)
    return 0.0


def _is_number(value: Any) -> bool:
    """Return whether a value is an int or float, excluding booleans."""

    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normal_cdf(value: float) -> float:
    """Return the standard normal cumulative distribution function."""

    return (1 + erf(value / sqrt(2))) / 2

