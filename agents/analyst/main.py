"""FastAPI entrypoint for the Analyst agent."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI
from pydantic import BaseModel

from agents.analyst.agent import AnalystAgent
from agents.analyst.reporting import attach_week_over_week, build_phase_a_report
from agents.analyst.schemas import ObservationRequest, ObservationResponse, ReportResponse
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
