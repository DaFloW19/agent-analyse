"""Landing page performance for the Analyst (B3).

Calculates visitor-to-form conversion rate per landing page and flags any
page below the 15% threshold for the Content & Conversion Strategist.
"""

from __future__ import annotations

BELOW_THRESHOLD_PCT = 15.0


def landing_page_performance(landing_page_rows: list[dict]) -> list[dict]:
    """Calculate visitor-to-form conversion rate per landing page.

    Args:
        landing_page_rows: Rows with `landing_page`, `visitors`,
            `form_submissions`, and `data_as_of`.

    Returns:
        list[dict]: One result per page: `{landing_page, conversion_rate_pct,
        visitors, form_submissions, below_threshold, data_as_of}`.
        `conversion_rate_pct` is `None` when `visitors` is zero.
    """

    results = []
    for row in landing_page_rows:
        visitors = row["visitors"]
        submissions = row["form_submissions"]
        rate = (submissions / visitors * 100) if visitors else None
        results.append(
            {
                "landing_page": row["landing_page"],
                "conversion_rate_pct": rate,
                "visitors": visitors,
                "form_submissions": submissions,
                "below_threshold": rate is not None and rate < BELOW_THRESHOLD_PCT,
                "data_as_of": row["data_as_of"],
            }
        )
    return results
