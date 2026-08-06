"""Deterministic seed dataset generator for the Analyst (SETUP-03).

Produces a reproducible dataset for one fictional real-estate client so that
reporting, attribution, and landing-page code can be built and tested
against realistic volume. For a given `ANCHOR_AT`, the same `seed` always
produces byte-identical output; `ANCHOR_AT` itself is pinned to process
start time (see below) so the simulated data's `data_as_of` never looks
stale in a long-running report, at the cost of the dataset shifting by a
few hours/days between one process run and the next.

Landing-page visitor and submission counts are aggregate web-analytics
numbers and are intentionally not reconciled 1:1 with the per-lead
`landing_page` attribution field below, mirroring how CRM lead counts and
web-analytics visitor counts come from two different systems in practice.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# Pinned once at import time (not recomputed per call) so a single process
# run stays internally consistent/deterministic, while still keeping the
# simulated data looking current across restarts -- unlike a hardcoded date,
# which drifts further into the past every day the server keeps running.
ANCHOR_AT = datetime.now(UTC)
WEEKS_OF_HISTORY = 8
LEAD_COUNT = 400

CAMPAIGN_AD_SETS = {
    "meta_lookalike_buyers": ["adset_lookalike_a", "adset_lookalike_b"],
    "google_search_intent": ["adset_search_exact", "adset_search_broad"],
    "meta_retargeting_warm": ["adset_retarget_hot", "adset_retarget_bad"],
}
CREATIVE_ASSETS = ["asset_hero_video", "asset_testimonial_carousel", "asset_listing_grid"]
LANDING_PAGES = ["lp_buyers_v1", "lp_buyers_v2"]
BAD_AD_SET = "adset_retarget_bad"
ZERO_SPEND_DAY_INDEX = 10

# Deliberately the best-performing campaign (higher score floor below), so
# cohort analysis (C3) has a reproducible best performer instead of relying
# on incidental RNG luck -- same convention as BAD_AD_SET.
STRONG_CAMPAIGN = "google_search_intent"
CLICK_ID_CAPTURE_RATE = 0.85
SCORING_DIMENSION_WEIGHTS = {
    "budget_fit": 0.25,
    "urgency": 0.15,
    "engagement": 0.25,
    # Deliberately the highest-weighted dimension despite being uncorrelated
    # with actually closing (see _build_scoring_run_rows) -- gives C4's
    # calibration-feedback logic a real, deterministic miscalibration to find.
    "contactability": 0.35,
}


@dataclass(frozen=True)
class SeedDataset:
    """Deterministic seed dataset for one fictional real-estate client.

    Args:
        leads: Per-lead attribution and scoring rows.
        spend_rows: Daily media spend rows per campaign and ad set.
        booking_rows: Booking attempt outcomes for SQL leads.
        deal_rows: Closed-deal outcomes for booked leads.
        transition_rows: Stage transitions from `new` to the scored stage.
        contact_rows: First-contact and reply timing for MQL/SQL leads.
        meeting_rows: Meeting show/no-show outcomes for booked leads.
        landing_page_rows: Visitor and submission counts per landing page.
        weekly_stage_conversion_rows: Week-on-week conversion rate snapshots.
        scoring_run_rows: Simulated Qualifier scoring runs for SQL+ leads
            (Phase C, C4 -- stands in for the Qualifier's real `scoring_runs`
            table, which doesn't exist yet in their repo).
        content_variant_rows: Simulated Content Strategist A/B variant
            conversion rows (Phase C, C5 -- stands in for their real
            `content_assets` table, which doesn't exist yet in their repo).
    """

    leads: list[dict]
    spend_rows: list[dict]
    booking_rows: list[dict]
    deal_rows: list[dict]
    transition_rows: list[dict]
    contact_rows: list[dict]
    meeting_rows: list[dict]
    landing_page_rows: list[dict]
    weekly_stage_conversion_rows: list[dict]
    scoring_run_rows: list[dict]
    content_variant_rows: list[dict]


def generate_seed_dataset(seed: int = 42) -> SeedDataset:
    """Generate the deterministic Analyst seed dataset.

    Args:
        seed: Random seed. The same seed always produces identical output.

    Returns:
        SeedDataset: ~400 leads over 8 weeks with spend, bookings, deals,
        stage transitions, contact timing, meetings, and landing pages.
    """

    rng = random.Random(seed)
    leads = _generate_leads(rng)
    spend_rows = _generate_spend_rows(rng)
    transition_rows = _build_transition_rows(leads)
    contact_rows = _build_contact_rows(rng, leads)
    booking_rows = _build_booking_rows(rng, leads)
    deal_rows = _build_deal_rows(rng, booking_rows)
    meeting_rows = _build_meeting_rows(rng, booking_rows)

    return SeedDataset(
        leads=leads,
        spend_rows=spend_rows,
        booking_rows=booking_rows,
        deal_rows=deal_rows,
        transition_rows=transition_rows,
        contact_rows=contact_rows,
        meeting_rows=meeting_rows,
        landing_page_rows=_build_landing_page_rows(),
        weekly_stage_conversion_rows=_build_weekly_stage_conversion_rows(),
        scoring_run_rows=_build_scoring_run_rows(rng, leads, deal_rows),
        content_variant_rows=_build_content_variant_rows(),
    )


_CACHED_DATASET: SeedDataset | None = None


def load_seed_dataset() -> SeedDataset:
    """Return the module-level cached seed dataset, generating it once.

    Returns:
        SeedDataset: The default (seed=42) Analyst seed dataset.
    """

    global _CACHED_DATASET
    if _CACHED_DATASET is None:
        _CACHED_DATASET = generate_seed_dataset()
    return _CACHED_DATASET


def _iso(moment: datetime) -> str:
    """Render a timezone-aware datetime as an ISO 8601 string."""

    return moment.isoformat().replace("+00:00", "Z")


def _classify(score: int) -> str:
    """Classify a score into the mandatory pipeline stage name."""

    if score <= 30:
        return "disqualified"
    if score <= 60:
        return "mql"
    return "sql"


def _generate_leads(rng: random.Random) -> list[dict]:
    """Generate lead rows with attribution and scoring.

    Args:
        rng: Seeded random generator.

    Returns:
        list[dict]: Lead rows including a deliberately unattributed slice
        (no campaign/ad_set/creative_asset) and a deliberately low-quality
        ad set (`adset_retarget_bad`) that is expensive but rarely qualifies.
    """

    campaigns = list(CAMPAIGN_AD_SETS.keys())
    leads = []
    for index in range(1, LEAD_COUNT + 1):
        created_at = ANCHOR_AT - timedelta(days=rng.uniform(0, WEEKS_OF_HISTORY * 7))

        if rng.random() < 0.10:
            campaign = ad_set = creative_asset = None
        else:
            campaign = rng.choice(campaigns)
            ad_set = rng.choice(CAMPAIGN_AD_SETS[campaign])
            creative_asset = rng.choice(CREATIVE_ASSETS)

        if rng.random() < 0.03:
            score = None
        elif ad_set == BAD_AD_SET:
            score = rng.randint(0, 35)
        elif campaign == STRONG_CAMPAIGN:
            score = rng.randint(25, 97)
        else:
            score = rng.randint(5, 97)

        if rng.random() < CLICK_ID_CAPTURE_RATE:
            click_id_platform = rng.choice(["meta", "google"])
            prefix = "fb" if click_id_platform == "meta" else "gclid"
            click_id = f"{prefix}.{index}.{rng.randint(10**9, 10**10 - 1)}"
        else:
            click_id_platform = None
            click_id = None

        leads.append(
            {
                "lead_id": f"lead-{index:04d}",
                "score": score,
                "campaign": campaign,
                "ad_set": ad_set,
                "creative_asset": creative_asset,
                "landing_page": rng.choice(LANDING_PAGES),
                "click_id": click_id,
                "click_id_platform": click_id_platform,
                "created_at": _iso(created_at),
                "data_as_of": _iso(ANCHOR_AT),
            }
        )
    return leads


def _generate_spend_rows(rng: random.Random) -> list[dict]:
    """Generate daily media spend rows per campaign and ad set.

    Args:
        rng: Seeded random generator.

    Returns:
        list[dict]: Daily spend rows, including one deliberate zero-spend
        day across every ad set and elevated spend on the deliberately bad
        ad set (`adset_retarget_bad`), which is expensive despite poor
        conversion quality.
    """

    rows = []
    total_days = WEEKS_OF_HISTORY * 7
    for day_index in range(total_days):
        day = ANCHOR_AT - timedelta(days=total_days - day_index)
        for campaign, ad_sets in CAMPAIGN_AD_SETS.items():
            for ad_set in ad_sets:
                for creative_asset in CREATIVE_ASSETS:
                    if day_index == ZERO_SPEND_DAY_INDEX:
                        spend = 0.0
                    elif ad_set == BAD_AD_SET:
                        spend = round(rng.uniform(20.0, 40.0), 2)
                    else:
                        spend = round(rng.uniform(6.0, 27.0), 2)
                    rows.append(
                        {
                            "spend": spend,
                            "campaign": campaign,
                            "ad_set": ad_set,
                            "creative_asset": creative_asset,
                            "date": _iso(day),
                            "data_as_of": _iso(ANCHOR_AT),
                        }
                    )
    return rows


def _build_transition_rows(leads: list[dict]) -> list[dict]:
    """Build `new -> <classification>` stage transitions for scored leads.

    Args:
        leads: Lead rows produced by `_generate_leads`.

    Returns:
        list[dict]: One transition row per scored lead. Unscored leads
        (score is None) produce no transition yet.
    """

    rows = []
    for lead in leads:
        if lead["score"] is None:
            continue
        rows.append(
            {
                "lead_id": lead["lead_id"],
                "from_stage": "new",
                "to_stage": _classify(lead["score"]),
                "data_as_of": lead["data_as_of"],
            }
        )
    return rows


def _build_contact_rows(rng: random.Random, leads: list[dict]) -> list[dict]:
    """Build first-contact and reply timing rows for MQL and SQL leads.

    Args:
        rng: Seeded random generator.
        leads: Lead rows produced by `_generate_leads`.

    Returns:
        list[dict]: Contact timing rows. Roughly 60% of leads reply within
        the tracked window; the rest omit `replied_at` entirely.
    """

    rows = []
    for lead in leads:
        if lead["score"] is None or lead["score"] < 31:
            continue
        submitted_at = datetime.fromisoformat(lead["created_at"].replace("Z", "+00:00"))
        delay_minutes = rng.gauss(4, 3) if rng.random() > 0.1 else rng.uniform(10, 60)
        first_contact_at = submitted_at + timedelta(minutes=max(delay_minutes, 0.5))

        row = {
            "lead_id": lead["lead_id"],
            "submitted_at": _iso(submitted_at),
            "first_contact_at": _iso(first_contact_at),
            "data_as_of": lead["data_as_of"],
        }
        if rng.random() < 0.6:
            reply_delay_minutes = rng.uniform(10, 40 * 60)
            row["replied_at"] = _iso(first_contact_at + timedelta(minutes=reply_delay_minutes))
        rows.append(row)
    return rows


def _build_booking_rows(rng: random.Random, leads: list[dict]) -> list[dict]:
    """Build booking attempt outcomes for SQL leads (score >= 61).

    Args:
        rng: Seeded random generator.
        leads: Lead rows produced by `_generate_leads`.

    Returns:
        list[dict]: One booking outcome row per SQL lead, booked or not.
    """

    rows = []
    for lead in leads:
        if lead["score"] is None or lead["score"] < 61:
            continue
        rows.append(
            {
                "lead_id": lead["lead_id"],
                "booked": rng.random() < 0.65,
                "data_as_of": lead["data_as_of"],
            }
        )
    return rows


def _build_deal_rows(rng: random.Random, booking_rows: list[dict]) -> list[dict]:
    """Build closed-deal outcomes for booked leads.

    Args:
        rng: Seeded random generator.
        booking_rows: Booking rows produced by `_build_booking_rows`.

    Returns:
        list[dict]: Closed-won or closed-lost deal rows. Some booked leads
        deliberately have no deal row yet (still open).
    """

    rows = []
    for booking in booking_rows:
        if not booking["booked"] or rng.random() < 0.15:
            continue
        won = rng.random() < 0.55
        rows.append(
            {
                "lead_id": booking["lead_id"],
                "status": "closed_won" if won else "closed_lost",
                "contract_value": round(rng.uniform(300.0, 1200.0), 2),
                "data_as_of": booking["data_as_of"],
            }
        )
    return rows


def _build_meeting_rows(rng: random.Random, booking_rows: list[dict]) -> list[dict]:
    """Build meeting show/no-show outcomes for booked leads.

    Args:
        rng: Seeded random generator.
        booking_rows: Booking rows produced by `_build_booking_rows`.

    Returns:
        list[dict]: One meeting row per booked lead.
    """

    rows = []
    for booking in booking_rows:
        if not booking["booked"]:
            continue
        rows.append(
            {
                "lead_id": booking["lead_id"],
                "booked": True,
                "showed": rng.random() < 0.75,
                "data_as_of": booking["data_as_of"],
            }
        )
    return rows


def _build_landing_page_rows() -> list[dict]:
    """Build landing-page visitor and submission aggregates.

    Returns:
        list[dict]: One deliberately underperforming page (~8.8%, below the
        15% visitor-to-form threshold) and one healthy page (~22.1%).
    """

    data_as_of = _iso(ANCHOR_AT)
    return [
        {
            "landing_page": "lp_buyers_v1",
            "visitors": 1000,
            "form_submissions": 88,
            "data_as_of": data_as_of,
        },
        {
            "landing_page": "lp_buyers_v2",
            "visitors": 480,
            "form_submissions": 106,
            "data_as_of": data_as_of,
        },
    ]


def _build_weekly_stage_conversion_rows() -> list[dict]:
    """Build week-on-week stage conversion snapshots for anomaly alerts.

    Returns:
        list[dict]: A genuine above-floor drop (new_to_mql), a drop below
        the alert threshold (mql_to_sql), and a drop above the threshold
        but below the volume floor (sql_to_booked) that must be suppressed.
    """

    data_as_of = _iso(ANCHOR_AT)
    return [
        {
            "transition": "new_to_mql",
            "label": "New to MQL",
            "previous_rate": 70.0,
            "current_rate": 30.0,
            "previous_denominator": 100,
            "current_denominator": 90,
            "data_as_of": data_as_of,
        },
        {
            "transition": "mql_to_sql",
            "label": "MQL to SQL",
            "previous_rate": 50.0,
            "current_rate": 35.0,
            "previous_denominator": 80,
            "current_denominator": 75,
            "data_as_of": data_as_of,
        },
        {
            "transition": "sql_to_booked",
            "label": "SQL to Booked",
            "previous_rate": 40.0,
            "current_rate": 15.0,
            "previous_denominator": 6,
            "current_denominator": 3,
            "data_as_of": data_as_of,
        },
    ]


def _build_scoring_run_rows(
    rng: random.Random, leads: list[dict], deal_rows: list[dict]
) -> list[dict]:
    """Build simulated Qualifier scoring runs for SQL+ leads (Phase C, C4).

    Stands in for the Qualifier's real `scoring_runs` table (QUA-01), which
    doesn't exist in their repo yet. `contactability` is deliberately the
    highest-weighted dimension (`SCORING_DIMENSION_WEIGHTS`) yet scored with
    no relationship to whether the lead actually closed; `urgency` is
    lower-weighted but scored to strongly track the real outcome. This gives
    `scoring_feedback.py` a real, deterministic miscalibration to detect
    (high weight, low outcome correlation) instead of relying on noise.

    Args:
        rng: Seeded random generator.
        leads: Lead rows produced by `_generate_leads`.
        deal_rows: Deal rows produced by `_build_deal_rows`, used to know
            which leads actually closed won.

    Returns:
        list[dict]: One scoring run per SQL+ lead (score >= 61): `{lead_id,
        scoring_model_version, weights_used, dimension_scores, total_score,
        classification, created_at}`.
    """

    closed_won_lead_ids = {row["lead_id"] for row in deal_rows if row["status"] == "closed_won"}

    rows = []
    for lead in leads:
        if lead["score"] is None or lead["score"] < 61:
            continue

        is_closed_won = lead["lead_id"] in closed_won_lead_ids
        dimension_scores = {
            "budget_fit": rng.randint(30, 90),
            "urgency": rng.randint(70, 95) if is_closed_won else rng.randint(20, 55),
            "engagement": rng.randint(30, 90),
            # Deliberately uncorrelated with the real outcome -- same range
            # regardless of is_closed_won.
            "contactability": rng.randint(40, 90),
        }
        total_score = round(
            sum(
                SCORING_DIMENSION_WEIGHTS[dimension] * value
                for dimension, value in dimension_scores.items()
            ),
            1,
        )
        rows.append(
            {
                "lead_id": lead["lead_id"],
                "scoring_model_version": "1.0.0",
                "weights_used": dict(SCORING_DIMENSION_WEIGHTS),
                "dimension_scores": dimension_scores,
                "total_score": total_score,
                "classification": "sql",
                "created_at": lead["created_at"],
            }
        )
    return rows


def _build_content_variant_rows() -> list[dict]:
    """Build simulated Content Strategist A/B variant conversion rows (Phase C, C5).

    Stands in for their real `content_assets` table (CCS-03), which doesn't
    exist in their repo yet. Static, not RNG-derived, so the exact counts
    below deterministically exercise CCS-03's three decision-rule branches.

    Returns:
        list[dict]: Three `variant_group_id` pairs -- a real 95%-confidence
        winner at 40 conversions/variant, a marginal (non-significant) pair
        also at 40 conversions/variant, and a pair at 20 conversions/variant
        (below the 30-conversion floor, insufficient data regardless of its
        rates).
    """

    data_as_of = _iso(ANCHOR_AT)
    return [
        {
            "variant_group_id": "vg_hero_copy",
            "asset_id": "asset_hero_copy_a",
            "variant": "a",
            "impressions": 200,
            "conversions": 40,
            "data_as_of": data_as_of,
        },
        {
            "variant_group_id": "vg_hero_copy",
            "asset_id": "asset_hero_copy_b",
            "variant": "b",
            "impressions": 200,
            "conversions": 70,
            "data_as_of": data_as_of,
        },
        {
            "variant_group_id": "vg_cta_button",
            "asset_id": "asset_cta_button_a",
            "variant": "a",
            "impressions": 200,
            "conversions": 40,
            "data_as_of": data_as_of,
        },
        {
            "variant_group_id": "vg_cta_button",
            "asset_id": "asset_cta_button_b",
            "variant": "b",
            "impressions": 200,
            "conversions": 48,
            "data_as_of": data_as_of,
        },
        {
            "variant_group_id": "vg_headline",
            "asset_id": "asset_headline_a",
            "variant": "a",
            "impressions": 100,
            "conversions": 20,
            "data_as_of": data_as_of,
        },
        {
            "variant_group_id": "vg_headline",
            "asset_id": "asset_headline_b",
            "variant": "b",
            "impressions": 100,
            "conversions": 22,
            "data_as_of": data_as_of,
        },
    ]
