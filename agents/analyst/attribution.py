"""Attribution breakdown for the Analyst (B2).

Breaks CPL, CPQ, and CPQL down by campaign, ad set, or creative asset, and
identifies the top and bottom performer at each level. Leads without an
attribution value are grouped under an explicit `"unattributed"` bucket —
they are never silently dropped.
"""

from __future__ import annotations

from typing import Literal

from common import metrics

UNATTRIBUTED = "unattributed"
AttributionKey = Literal["campaign", "ad_set", "creative_asset"]


def attribution_breakdown(
    spend_rows: list[dict],
    lead_rows: list[dict],
    group_by: AttributionKey,
) -> dict:
    """Break CPL, CPQ, and CPQL down by an attribution dimension.

    Args:
        spend_rows: Spend rows carrying `group_by` and `spend`.
        lead_rows: Lead rows carrying `group_by` and `score`.
        group_by: Attribution dimension to group by (`campaign`, `ad_set`,
            or `creative_asset`).

    Returns:
        dict: `{"group_by", "by_group": {key: {cpl, cpq, cpql}}, "ranked",
        "top_performer", "bottom_performer"}`. Groups are ranked by CPQL
        (cost per SQL), the strictest quality signal; a group with no SQL
        leads (CPQL value is `None`) always ranks worst rather than being
        treated as free of cost. `ranked` is every key best-to-worst,
        including `"unattributed"`, so callers that want to recommend an
        action against a real campaign/ad set/asset can skip it explicitly.
    """

    keys = _group_keys(spend_rows, lead_rows, group_by)
    by_group = {key: _kpis_for_key(spend_rows, lead_rows, group_by, key) for key in keys}

    ranked = _rank_by_cpql(by_group)
    top_key = ranked[0] if ranked else None
    bottom_key = ranked[-1] if ranked else None
    return {
        "group_by": group_by,
        "by_group": by_group,
        "ranked": ranked,
        "top_performer": {"key": top_key, **by_group[top_key]} if top_key else None,
        "bottom_performer": {"key": bottom_key, **by_group[bottom_key]} if bottom_key else None,
    }


def _key_of(row: dict, group_by: str) -> str:
    """Return a row's attribution key, or the unattributed bucket."""

    value = row.get(group_by)
    return value if value else UNATTRIBUTED


def _rows_for(rows: list[dict], group_by: str, key: str) -> list[dict]:
    """Filter rows to those matching an attribution key."""

    return [row for row in rows if _key_of(row, group_by) == key]


def _kpis_for_key(spend_rows: list[dict], lead_rows: list[dict], group_by: str, key: str) -> dict:
    """Calculate CPL, CPQ, and CPQL for a single attribution key."""

    group_spend = _rows_for(spend_rows, group_by, key)
    group_leads = _rows_for(lead_rows, group_by, key)
    return {
        "cpl": metrics.cpl(group_spend, group_leads),
        "cpq": metrics.cpq(group_spend, group_leads),
        "cpql": metrics.cpql(group_spend, group_leads),
    }


def _group_keys(spend_rows: list[dict], lead_rows: list[dict], group_by: str) -> list[str]:
    """Collect every distinct attribution key present across spend and leads."""

    keys = {_key_of(row, group_by) for row in spend_rows}
    keys |= {_key_of(row, group_by) for row in lead_rows}
    return sorted(keys)


def _rank_by_cpql(by_group: dict[str, dict]) -> list[str]:
    """Rank attribution keys from best (lowest CPQL) to worst (highest).

    Args:
        by_group: KPI results keyed by attribution key.

    Returns:
        list[str]: Attribution keys ordered from top to bottom performer.
    """

    def sort_key(key: str) -> tuple[int, float]:
        value = by_group[key]["cpql"]["value"]
        return (1, 0.0) if value is None else (0, value)

    return sorted(by_group, key=sort_key)
