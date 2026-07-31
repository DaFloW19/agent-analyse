"""Core Analyst agent logic."""

from agents.analyst.schemas import ObservationRequest, ObservationResponse


MANDATORY_LOG_FIELDS = [
    "agent_name",
    "action_type",
    "input_summary",
    "output_summary",
    "lead_id",
    "client_id",
    "model_used",
    "latency_ms",
    "timestamp",
]


AGENT_KPI_MAP = {
    "commander": ["stage_conversion_rate", "time_to_first_contact"],
    "crm_keeper": ["stage_conversion_rate", "response_rate", "meeting_show_rate", "roas"],
    "qualifier": ["cpq", "cpql", "stage_conversion_rate"],
    "content_strategist": ["cpl", "cpq", "cpql", "response_rate"],
    "media_buyer": ["cpl", "cpq", "cpql", "cpbd", "roas"],
    "closer": ["time_to_first_contact", "response_rate", "meeting_show_rate", "cpbd"],
    "analyst": ["cpl", "cpq", "cpql", "cpbd", "roas"],
}


AGENT_GUARDRAIL_MAP = {
    "commander": ["autonomy_policy", "event_idempotency", "signature_verification"],
    "crm_keeper": ["schema_validation", "consent_check", "optimistic_concurrency"],
    "qualifier": ["scoring_provenance", "boundary_review", "golden_set_regression"],
    "content_strategist": ["output_contract", "compliance_lint", "ab_test_stopping_rule"],
    "media_buyer": ["dry_run_mode", "spend_limits", "statistical_floor", "change_ledger"],
    "closer": ["do_not_contact", "quiet_hours", "rate_cap", "whatsapp_session_window"],
    "analyst": ["no_direct_execution", "data_freshness", "canonical_metrics"],
}


class AnalystAgent:
    """Side-effect-free Analyst service used for reporting and task observation."""

    name = "analyst"

    def observe_task(self, request: ObservationRequest) -> ObservationResponse:
        """Analyse a task being handled by another agent.

        Args:
            request: Structured task context from the active agent.

        Returns:
            ObservationResponse: KPI, guardrail, logging, and risk guidance.
        """

        affected_kpis = AGENT_KPI_MAP.get(request.agent_name, [])
        guardrails = AGENT_GUARDRAIL_MAP.get(request.agent_name, [])
        risks = self._detect_risks(request)

        return ObservationResponse(
            agent_name=self.name,
            observed_agent=request.agent_name,
            task_type=request.task_type,
            affected_kpis=affected_kpis,
            guardrails_to_check=guardrails,
            required_log_fields=MANDATORY_LOG_FIELDS,
            risks=risks,
            recommendation=self._build_recommendation(request, affected_kpis, guardrails, risks),
            safe_to_continue=not risks,
        )

    def _detect_risks(self, request: ObservationRequest) -> list[str]:
        """Detect obvious analytical risks from the task summary and available data points.

        Args:
            request: Structured task context from the active agent.

        Returns:
            list[str]: Human-readable risk labels.
        """

        risks: list[str] = []
        data_points = request.data_points

        if request.agent_name == "media_buyer":
            if data_points.get("dry_run") is False:
                risks.append("media_buying_write_without_dry_run")
            conversions = data_points.get("conversions")
            if isinstance(conversions, int | float) and conversions < 15:
                risks.append("insufficient_conversion_volume")

        if request.agent_name == "closer" and data_points.get("do_not_contact") is True:
            risks.append("lead_marked_do_not_contact")

        if request.agent_name == "qualifier" and not data_points.get("scoring_model_version"):
            risks.append("missing_scoring_model_version")

        if request.agent_name == "content_strategist" and not data_points.get("asset_id"):
            risks.append("missing_asset_id_for_attribution")

        if data_points.get("data_stale") is True:
            risks.append("stale_source_data")

        return risks

    def _build_recommendation(
        self,
        request: ObservationRequest,
        affected_kpis: list[str],
        guardrails: list[str],
        risks: list[str],
    ) -> str:
        """Build the Analyst's plain-language recommendation.

        Args:
            request: Structured task context from the active agent.
            affected_kpis: KPIs likely impacted by the task.
            guardrails: Guardrails that should be checked before execution.
            risks: Risks detected from the task context.

        Returns:
            str: Recommendation for the active agent and Commander.
        """

        if risks:
            return (
                "Pause execution and route through Commander review. "
                f"Detected risks: {', '.join(risks)}."
            )

        kpi_text = ", ".join(affected_kpis) if affected_kpis else "no direct KPI"
        guardrail_text = ", ".join(guardrails) if guardrails else "standard logging"
        return (
            f"Continue with {request.agent_name}.{request.task_type}. "
            f"Track {kpi_text} and confirm {guardrail_text} before execution."
        )

