"""Schemas used by the Analyst API and core agent."""

from typing import Any, Literal

from pydantic import BaseModel, Field


KnownAgentName = Literal[
    "commander",
    "crm_keeper",
    "qualifier",
    "content_strategist",
    "media_buyer",
    "closer",
    "analyst",
]


class ObservationRequest(BaseModel):
    """Task context sent to the Analyst when it acts as an observation binome."""

    client_id: str = Field(min_length=1)
    agent_name: KnownAgentName
    task_type: str = Field(min_length=1)
    input_summary: str = Field(min_length=1, max_length=500)
    expected_output: str | None = Field(default=None, max_length=500)
    lead_id: str | None = None
    data_points: dict[str, Any] = Field(default_factory=dict)


class ObservationResponse(BaseModel):
    """Analyst observation returned to the active agent and Commander."""

    agent_name: str
    observed_agent: KnownAgentName
    task_type: str
    affected_kpis: list[str]
    guardrails_to_check: list[str]
    required_log_fields: list[str]
    risks: list[str]
    recommendation: str
    safe_to_continue: bool


class ReportResponse(BaseModel):
    """Phase B KPI report response using local demo data."""

    agent_name: str
    status: str
    client_id: str
    metrics: dict[str, dict[str, float | str | None]]
    message: str


class AttributionResponse(BaseModel):
    """CPL/CPQ/CPQL breakdown by campaign, ad set, or creative asset (B2).

    `top_performer`/`bottom_performer` carry the winning/losing key plus
    its KPIs (`{"key": str, "cpl": {...}, "cpq": {...}, "cpql": {...}}`),
    or `None` when there is nothing to rank.
    """

    agent_name: str
    client_id: str
    group_by: str
    by_group: dict[str, dict[str, dict[str, float | str | None]]]
    ranked: list[str]
    top_performer: dict[str, Any] | None
    bottom_performer: dict[str, Any] | None


class LandingPageResult(BaseModel):
    """One landing page's visitor-to-form conversion result (B3)."""

    landing_page: str
    conversion_rate_pct: float | None
    visitors: int
    form_submissions: int
    below_threshold: bool
    data_as_of: str


class LandingPagesResponse(BaseModel):
    """Landing page performance response (B3)."""

    agent_name: str
    client_id: str
    pages: list[LandingPageResult]


class AlertResult(BaseModel):
    """One conversion-drop alert above the threshold and volume floor (B5/ANA-03)."""

    transition: str
    label: str
    previous_rate: float
    current_rate: float
    drop_pct: float
    previous_denominator: int
    current_denominator: int
    data_as_of: str


class AlertsResponse(BaseModel):
    """Conversion-drop alerts response (B5/ANA-03)."""

    agent_name: str
    client_id: str
    alerts: list[AlertResult]


class WeeklyReportResponse(BaseModel):
    """Weekly optimisation report response (B6), as plain text."""

    agent_name: str
    client_id: str
    report: str


class StatusResponse(BaseModel):
    """Reachability/configuration status of every dependency the Analyst uses.

    `*_reachable` fields perform a live check (subject to the same
    retry/timeout behaviour as the underlying client); `*_configured`
    fields only check whether a key is set, no network call.
    """

    agent_name: str
    crm_keeper_reachable: bool
    media_buyer_reachable: bool
    database_reachable: bool
    llm_configured: bool
    llm_model: str
    langfuse_configured: bool


class PredictiveRoasResponse(BaseModel):
    """Predictive ROAS projection response (Phase C, C2).

    A range, never a single number -- `sufficient_data` is False (with only
    `pipeline_volume` populated below) when the current SQL pipeline is
    below the ANA-03 volume floor, rather than fabricating a projection.
    """

    agent_name: str
    client_id: str
    sufficient_data: bool
    pipeline_volume: int
    days: int
    booking_rate: dict[str, float | None] | None = None
    close_rate: dict[str, float | None] | None = None
    avg_contract_value: float | None = None
    projected_revenue_low: float | None = None
    projected_revenue_high: float | None = None
    assumptions: list[str] = Field(default_factory=list)


class CohortResult(BaseModel):
    """One cohort's lead volume and outcome rates (Phase C, C3)."""

    lead_count: int
    sql_rate_pct: float | None
    closed_won_rate_pct: float | None


class CohortsResponse(BaseModel):
    """Cohort analysis response (Phase C, C3).

    `insufficient` lists cohort keys below the ANA-03 volume floor -- still
    present in `cohorts` for transparency, but never in `ranked`.
    """

    agent_name: str
    client_id: str
    group_by: str
    cohorts: dict[str, CohortResult]
    ranked: list[str]
    insufficient: list[str]


class ConversionApiPayloadRow(BaseModel):
    """One closed-won deal ready for the Conversion API push (Phase C, C1)."""

    lead_id: str
    click_id: str
    click_id_platform: str | None
    contract_value: float
    closed_at: str


class ConversionApiResponse(BaseModel):
    """Conversion API payload preview response (Phase C, C1).

    Read-only preview of what the weekly job would build. `dry_run` is
    always True -- see `agents/analyst/conversion_api.py` for why this
    never calls Media Buyer's real endpoint.
    """

    agent_name: str
    client_id: str
    pushed: list[ConversionApiPayloadRow]
    excluded_no_click_id: int
    dry_run: bool


class ScoringProposal(BaseModel):
    """One scoring-dimension recalibration proposal (Phase C, C4). Never auto-applied."""

    dimension: str
    current_weight: float
    scoring_model_version: str | None
    evidence: dict[str, float | int]
    suggested_direction: str


class ScoringFeedbackResponse(BaseModel):
    """Scoring model feedback response (Phase C, C4)."""

    agent_name: str
    client_id: str
    proposals: list[ScoringProposal]


class AbTestResult(BaseModel):
    """One A/B variant group's evaluation result (Phase C, C5).

    `status` is `"insufficient_data"`, `"no_winner"` (see `variant_a`/
    `variant_b`), or `"winner"` (see `winner_asset_id`/`p_value`).
    """

    variant_group_id: str
    status: str
    winner_asset_id: str | None = None
    winner_variant: str | None = None
    p_value: float | None = None
    variant_a: dict[str, Any] | None = None
    variant_b: dict[str, Any] | None = None


class AbTestsResponse(BaseModel):
    """A/B test conclusions response (Phase C, C5)."""

    agent_name: str
    client_id: str
    results: list[AbTestResult]
