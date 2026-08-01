"""Telegram command parsing and execution helpers for the Analyst."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from agents.analyst.agent import AnalystAgent
from agents.analyst.reporting import (
    build_phase_a_alerts,
    build_phase_a_report,
    format_alerts_for_telegram,
    format_report_for_telegram,
    format_weekly_report_for_telegram,
)
from agents.analyst.scheduler import build_weekly_optimisation_report
from agents.analyst.schemas import KnownAgentName, ObservationRequest
from common.logging import log_action
from common.tracing import traced_action
from config.settings import settings

AGENT_LABELS = {
    "commander": "Commander",
    "crm_keeper": "CRM Keeper",
    "qualifier": "Qualifier",
    "content_strategist": "Content Strategist",
    "media_buyer": "Media Buyer",
    "closer": "Closer",
    "analyst": "Analyst",
}

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

GUARDRAIL_LABELS = {
    "autonomy_policy": "Autonomy policy",
    "event_idempotency": "Event idempotency",
    "signature_verification": "Signature verification",
    "schema_validation": "Schema validation",
    "consent_check": "Consent check",
    "optimistic_concurrency": "Optimistic concurrency",
    "scoring_provenance": "Scoring provenance",
    "boundary_review": "Boundary review",
    "golden_set_regression": "Golden-set regression",
    "output_contract": "Output contract",
    "compliance_lint": "Compliance lint",
    "ab_test_stopping_rule": "A/B stopping rule",
    "dry_run_mode": "Dry-run mode",
    "spend_limits": "Spend limits",
    "statistical_floor": "Statistical floor",
    "change_ledger": "Change ledger",
    "do_not_contact": "Do-not-contact",
    "quiet_hours": "Quiet hours",
    "rate_cap": "Rate cap",
    "whatsapp_session_window": "WhatsApp session window",
    "no_direct_execution": "No direct execution",
    "data_freshness": "Data freshness",
    "canonical_metrics": "Canonical metrics",
}

RISK_LABELS = {
    "media_buying_write_without_dry_run": "Media buying write attempted without dry-run",
    "insufficient_conversion_volume": "Insufficient conversion volume",
    "lead_marked_do_not_contact": "Lead is marked do-not-contact",
    "missing_scoring_model_version": "Missing scoring model version",
    "missing_asset_id_for_attribution": "Missing asset ID for attribution",
    "stale_source_data": "Source data is stale",
}

KNOWN_AGENT_NAMES = {
    "commander",
    "crm_keeper",
    "qualifier",
    "content_strategist",
    "media_buyer",
    "closer",
    "analyst",
}


@dataclass(frozen=True)
class ParsedObserveCommand:
    """Parsed representation of a Telegram `/observe` command."""

    agent_name: KnownAgentName
    task_type: str
    data_points: dict[str, Any]


def parse_observe_command(text: str) -> ParsedObserveCommand:
    """Parse a Phase B `/observe` Telegram command.

    Args:
        text: Full Telegram command text.

    Returns:
        ParsedObserveCommand: Parsed agent, task, and key-value data points.

    Raises:
        ValueError: If the command is malformed or names an unknown agent.
    """

    parts = text.strip().split()
    if len(parts) < 2 or parts[0] != "/observe":
        raise ValueError("Usage: /observe <agent_name> [task_type] key=value")

    agent_name = parts[1]
    if agent_name not in KNOWN_AGENT_NAMES:
        raise ValueError(f"Unknown agent: {agent_name}")

    task_type = parts[2] if len(parts) >= 3 and "=" not in parts[2] else "general_observation"
    data_points = {}
    data_point_parts = parts[3:] if task_type != "general_observation" else parts[2:]
    for part in data_point_parts:
        if "=" not in part:
            raise ValueError(f"Expected key=value, got: {part}")
        key, value = part.split("=", 1)
        data_points[key] = _coerce_value(value)

    return ParsedObserveCommand(
        agent_name=agent_name,  # type: ignore[arg-type]
        task_type=task_type,
        data_points=data_points,
    )


def handle_text_command(
    text: str,
    *,
    analyst_agent: AnalystAgent | None = None,
    client_id: str | None = None,
    log_path: str = "logs/analyst.jsonl",
) -> str:
    """Handle a Telegram text command without depending on Telegram runtime objects.

    Args:
        text: Incoming Telegram command.
        analyst_agent: Analyst agent instance. A default instance is created when omitted.
        client_id: Client identifier. Defaults to Dynaconf Analyst client id.
        log_path: Local JSONL path for Phase B logs.

    Returns:
        str: Telegram-ready response text.
    """

    agent = analyst_agent or AnalystAgent()
    active_client_id = client_id or settings.analyst.client_id
    command = text.strip()

    if command in {"/start", "/help"}:
        return build_help_message()

    if command == "/health":
        return f"Analyst health: ok\nclient_id: {active_client_id}"

    if command == "/report":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_b_report",
            model_used="rule-based",
        ):
            return format_report_for_telegram(build_phase_a_report())

    if command == "/weekly_report":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_b_weekly_report",
            model_used="rule-based",
        ):
            report = build_phase_a_report()
            alerts = build_phase_a_alerts(active_client_id)
            return format_weekly_report_for_telegram(report, alerts)

    if command == "/alerts":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_b_alerts",
            model_used="rule-based",
        ):
            return format_alerts_for_telegram(build_phase_a_alerts(active_client_id))

    if command == "/optimisation_report":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_b_optimisation_report",
            model_used="rule-based",
        ):
            return build_weekly_optimisation_report(active_client_id)

    if command.startswith("/observe"):
        parsed = parse_observe_command(command)
        request = ObservationRequest(
            client_id=active_client_id,
            agent_name=parsed.agent_name,
            task_type=parsed.task_type,
            input_summary=f"Telegram observe command for {parsed.agent_name}.{parsed.task_type}",
            data_points=parsed.data_points,
        )
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_b_observe",
            model_used="rule-based",
            lead_id=request.lead_id,
        ):
            started_at = perf_counter()
            response = agent.observe_task(request)
            latency_ms = int((perf_counter() - started_at) * 1000)
            log_action(
                agent_name="analyst",
                action_type="telegram_observe",
                input_summary=f"{request.agent_name}.{request.task_type}",
                output_summary=(
                    f"safe_to_continue={response.safe_to_continue}; risks={len(response.risks)}"
                ),
                lead_id=request.lead_id,
                client_id=request.client_id,
                model_used="rule-based",
                latency_ms=latency_ms,
                path=log_path,
            )
        return format_observation_for_telegram(response)

    return "Unknown command. Use /help."


def build_help_message() -> str:
    """Build the Telegram welcome/help message.

    Returns:
        str: Help text listing commands, agents, and examples.
    """

    return (
        "Analyst Agent Phase B is active.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/help - Show this message\n"
        "/health - Check Analyst status\n"
        "/report - Show the Phase B KPI report\n"
        "/weekly_report - Show weekly KPIs and alerts\n"
        "/alerts - Check conversion drops above 50%\n"
        "/optimisation_report - Preview the weekly scale/pause/rewrite recommendations "
        "(normally sent automatically every Monday)\n"
        "/observe <agent_name> - Observe one agent\n"
        "/observe <agent_name> <task_type> key=value - Observe a specific task\n\n"
        "Agents:\n"
        "commander\n"
        "crm_keeper\n"
        "qualifier\n"
        "content_strategist\n"
        "media_buyer\n"
        "closer\n"
        "analyst\n\n"
        "Examples:\n"
        "/weekly_report\n"
        "/alerts\n"
        "/observe media_buyer\n"
        "/observe media_buyer pause_ad_set conversions=6 dry_run=true\n"
        "/observe closer send_first_contact do_not_contact=false\n"
        "/observe qualifier score_lead scoring_model_version=1.0.0"
    )


def format_observation_for_telegram(response: Any) -> str:
    """Format an Analyst observation as a readable Telegram report.

    Args:
        response: Observation response returned by the Analyst agent.

    Returns:
        str: Human-friendly Telegram response.
    """

    agent_label = AGENT_LABELS.get(response.observed_agent, str(response.observed_agent))
    task_label = _humanize_identifier(response.task_type)
    decision = "Continue" if response.safe_to_continue else "Review required"
    kpis = _format_label_list(response.affected_kpis, KPI_LABELS)
    guardrails = _format_label_list(response.guardrails_to_check, GUARDRAIL_LABELS)
    risks = _format_label_list(response.risks, RISK_LABELS) if response.risks else "None"

    if response.safe_to_continue:
        recommendation = (
            f"{agent_label} can continue. Track the listed KPIs and confirm the guardrails "
            "before any execution."
        )
    else:
        recommendation = "Pause execution and route this through Commander review."

    return (
        "Observation Report\n"
        f"Agent: {agent_label}\n"
        f"Task: {task_label}\n"
        f"Decision: {decision}\n\n"
        f"KPIs to watch: {kpis}\n"
        f"Guardrails: {guardrails}\n"
        f"Risks: {risks}\n\n"
        f"Recommendation: {recommendation}"
    )


def _coerce_value(value: str) -> str | int | float | bool:
    """Coerce Telegram key-value strings into simple Python values."""

    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _format_label_list(values: list[str], labels: dict[str, str]) -> str:
    """Render identifiers as a comma-separated list of readable labels."""

    if not values:
        return "None"
    return ", ".join(labels.get(value, _humanize_identifier(value)) for value in values)


def _humanize_identifier(value: str) -> str:
    """Convert an underscore identifier into readable title case."""

    return value.replace("_", " ").capitalize()
