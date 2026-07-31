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
