"""FastAPI entrypoint for the Analyst agent."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI
from pydantic import BaseModel

from agents.analyst import live_data
from agents.analyst.ab_test_conclusions import evaluate_ab_tests
from agents.analyst.agent import AnalystAgent
from agents.analyst.attribution import AttributionKey, attribution_breakdown
from agents.analyst.cohort_analysis import CohortKey, cohort_breakdown
from agents.analyst.conversion_api import build_conversion_api_payload
from agents.analyst.landing_pages import landing_page_performance
from agents.analyst.predictive_roas import project_roas
from agents.analyst.reporting import (
    attach_week_over_week,
    build_phase_a_alerts,
    build_phase_a_report,
)
from agents.analyst.scheduler import build_weekly_optimisation_report
from agents.analyst.schemas import (
    AbTestsResponse,
    AlertsResponse,
    AttributionResponse,
    CohortsResponse,
    ConversionApiResponse,
    LandingPagesResponse,
    ObservationRequest,
    ObservationResponse,
    PredictiveRoasResponse,
    ReportResponse,
    ScoringFeedbackResponse,
    StatusResponse,
    WeeklyReportResponse,
)
from agents.analyst.scoring_feedback import build_calibration_proposals
from agents.analyst.seed_data import load_seed_dataset
from common.logging import log_action
from common.tracing import traced_action
from config.settings import settings


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str
    agent_name: str
    client_id: str


app = FastAPI(
    title="Analyst Agent",
    version="0.1.0",
    description="Backward-looking reporting and optimization agent.",
)
analyst_agent = AnalystAgent()
app.state.log_path = Path("logs/analyst.jsonl")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return the Analyst service health status."""

    return HealthResponse(
        status="ok",
        agent_name="analyst",
        client_id=settings.analyst.client_id,
    )


@app.post("/observe", response_model=ObservationResponse)
def observe_task(request: ObservationRequest) -> ObservationResponse:
    """Observe another agent's task as the Analyst binome."""

    with traced_action(
        agent_name="analyst",
        client_id=request.client_id,
        phase="phase_b_observe",
        model_used="rule-based",
        lead_id=request.lead_id,
    ):
        started_at = perf_counter()
        response = analyst_agent.observe_task(request)
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name="analyst",
            action_type="observe_task",
            input_summary=f"{request.agent_name}.{request.task_type}: {request.input_summary}",
            output_summary=(
                f"safe_to_continue={response.safe_to_continue}; risks={len(response.risks)}"
            ),
            lead_id=request.lead_id,
            client_id=request.client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
    return response


@app.get("/report", response_model=ReportResponse)
def report() -> ReportResponse:
    """Return a Phase B KPI report from the Analyst seed dataset."""

    with traced_action(
        agent_name="analyst",
        client_id=settings.analyst.client_id,
        phase="phase_b_report",
        model_used="rule-based",
    ):
        report = attach_week_over_week(build_phase_a_report(), datetime.now(UTC))
        return ReportResponse(
            agent_name="analyst",
            status="ok",
            client_id=settings.analyst.client_id,
            metrics=report,
            message="Phase B report, live where reachable, seeded otherwise.",
        )


@app.get("/attribution", response_model=AttributionResponse)
def attribution(group_by: AttributionKey = "campaign") -> AttributionResponse:
    """Return the CPL/CPQ/CPQL breakdown by campaign, ad set, or creative asset (B2)."""

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_b_attribution",
        model_used="rule-based",
    ):
        started_at = perf_counter()
        dataset = load_seed_dataset()
        result = attribution_breakdown(dataset.spend_rows, dataset.leads, group_by)
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name="analyst",
            action_type="get_attribution",
            input_summary=f"group_by={group_by}",
            output_summary=f"top={result['top_performer']}, bottom={result['bottom_performer']}",
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
        return AttributionResponse(agent_name="analyst", client_id=client_id, **result)


@app.get("/landing-pages", response_model=LandingPagesResponse)
def landing_pages() -> LandingPagesResponse:
    """Return visitor-to-form conversion rate per landing page (B3)."""

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_b_landing_pages",
        model_used="rule-based",
    ):
        started_at = perf_counter()
        dataset = load_seed_dataset()
        pages = landing_page_performance(dataset.landing_page_rows)
        latency_ms = int((perf_counter() - started_at) * 1000)
        flagged_count = sum(1 for page in pages if page["below_threshold"])
        log_action(
            agent_name="analyst",
            action_type="get_landing_pages",
            input_summary="Computed conversion rate for every landing page",
            output_summary=f"{flagged_count}/{len(pages)} page(s) below the 15% threshold",
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
        return LandingPagesResponse(agent_name="analyst", client_id=client_id, pages=pages)


@app.get("/alerts", response_model=AlertsResponse)
def alerts() -> AlertsResponse:
    """Return conversion-drop alerts above the threshold and volume floor (B5/ANA-03)."""

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_b_alerts",
        model_used="rule-based",
    ):
        started_at = perf_counter()
        alert_rows = build_phase_a_alerts(client_id)
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name="analyst",
            action_type="get_alerts",
            input_summary="Checked conversion-drop alerts",
            output_summary=f"{len(alert_rows)} alert(s) above threshold and volume floor",
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
        return AlertsResponse(agent_name="analyst", client_id=client_id, alerts=alert_rows)


@app.get("/weekly-report", response_model=WeeklyReportResponse)
def weekly_report() -> WeeklyReportResponse:
    """Return the weekly optimisation report as plain text (B6).

    Read-only: this only builds and returns the report text. It never
    sends anything and never writes a `KpiSnapshot` -- that only happens
    from the real Monday scheduler job (`scheduler.run_weekly_report_job`),
    to avoid noisy snapshot rows from repeated manual/API calls.
    """

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_b_weekly_report_api",
        model_used="rule-based",
    ):
        started_at = perf_counter()
        report_text = build_weekly_optimisation_report(client_id)
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name="analyst",
            action_type="get_weekly_report",
            input_summary="Built the weekly optimisation report on demand",
            output_summary=f"Generated {len(report_text)} characters",
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
        return WeeklyReportResponse(agent_name="analyst", client_id=client_id, report=report_text)


@app.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    """Return live reachability and configuration status for every dependency.

    `crm_keeper_reachable`/`media_buyer_reachable` perform a real call
    (bounded by the same tenacity retries as `live_data.py`, so this can
    take several seconds when a dependency is down) -- this is a
    diagnostic endpoint, not one to poll tightly.
    """

    from common.db import is_database_reachable
    from common.llm import active_model, is_configured

    client_id = settings.analyst.client_id
    crm_keeper_reachable = live_data.fetch_crm_keeper_leads(client_id) is not None
    media_buyer_reachable = live_data.fetch_media_buyer_spend() is not None
    langfuse_configured = bool(settings.get("LANGFUSE_PUBLIC_KEY")) and bool(
        settings.get("LANGFUSE_SECRET_KEY")
    )
    return StatusResponse(
        agent_name="analyst",
        crm_keeper_reachable=crm_keeper_reachable,
        media_buyer_reachable=media_buyer_reachable,
        database_reachable=is_database_reachable(),
        llm_configured=is_configured(),
        llm_model=active_model(),
        langfuse_configured=langfuse_configured,
    )


@app.get("/predictive-roas", response_model=PredictiveRoasResponse)
def predictive_roas(days: int = 30) -> PredictiveRoasResponse:
    """Project expected closed-won revenue over the next `days` days (Phase C, C2)."""

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_c_predictive_roas",
        model_used="rule-based",
    ):
        started_at = perf_counter()
        dataset = load_seed_dataset()
        result = project_roas(dataset, days=days, client_id=client_id)
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name="analyst",
            action_type="get_predictive_roas",
            input_summary=f"Projected revenue over the next {days} days",
            output_summary=f"sufficient_data={result['sufficient_data']}",
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
        return PredictiveRoasResponse(agent_name="analyst", **result)


@app.get("/cohorts", response_model=CohortsResponse)
def cohorts(group_by: CohortKey = "campaign") -> CohortsResponse:
    """Break lead quality and closed-won outcomes down by cohort (Phase C, C3)."""

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_c_cohorts",
        model_used="rule-based",
    ):
        started_at = perf_counter()
        dataset = load_seed_dataset()
        result = cohort_breakdown(dataset, group_by=group_by)
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name="analyst",
            action_type="get_cohorts",
            input_summary=f"group_by={group_by}",
            output_summary=(
                f"{len(result['ranked'])} ranked, {len(result['insufficient'])} insufficient"
            ),
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
        return CohortsResponse(agent_name="analyst", client_id=client_id, **result)


@app.get("/conversion-api-payload", response_model=ConversionApiResponse)
def conversion_api_payload() -> ConversionApiResponse:
    """Preview the weekly Conversion API payload, read-only (Phase C, C1).

    Always `dry_run=True` -- see `agents/analyst/conversion_api.py` for why
    this never calls Media Buyer's real endpoint. Read-only: does not log
    the way the real Monday job (`scheduler.run_conversion_api_push_job`)
    does, to avoid noisy duplicate log rows from repeated manual calls.
    """

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_c_conversion_api",
        model_used="rule-based",
    ):
        dataset = load_seed_dataset()
        result = build_conversion_api_payload(dataset, client_id=client_id)
        return ConversionApiResponse(agent_name="analyst", **result)


@app.get("/scoring-feedback", response_model=ScoringFeedbackResponse)
def scoring_feedback() -> ScoringFeedbackResponse:
    """Return scoring-dimension recalibration proposals, never auto-applied (Phase C, C4)."""

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_c_scoring_feedback",
        model_used="rule-based",
    ):
        started_at = perf_counter()
        dataset = load_seed_dataset()
        proposals = build_calibration_proposals(dataset)
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name="analyst",
            action_type="get_scoring_feedback",
            input_summary="Compared scoring dimensions against closed-deal outcomes",
            output_summary=f"{len(proposals)} calibration proposal(s)",
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
        return ScoringFeedbackResponse(
            agent_name="analyst", client_id=client_id, proposals=proposals
        )


@app.get("/ab-tests", response_model=AbTestsResponse)
def ab_tests() -> AbTestsResponse:
    """Evaluate every A/B variant group for a statistically significant winner (Phase C, C5)."""

    client_id = settings.analyst.client_id
    with traced_action(
        agent_name="analyst",
        client_id=client_id,
        phase="phase_c_ab_tests",
        model_used="rule-based",
    ):
        started_at = perf_counter()
        dataset = load_seed_dataset()
        results = evaluate_ab_tests(dataset)
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name="analyst",
            action_type="get_ab_tests",
            input_summary="Evaluated every A/B variant group",
            output_summary=f"{len(results)} group(s) evaluated",
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=latency_ms,
            path=app.state.log_path,
        )
        return AbTestsResponse(agent_name="analyst", client_id=client_id, results=results)
