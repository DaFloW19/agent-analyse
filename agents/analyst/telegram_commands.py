"""Telegram command parsing and execution helpers for the Analyst."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from agents.analyst.ab_test_conclusions import evaluate_ab_tests
from agents.analyst.agent import AnalystAgent
from agents.analyst.cohort_analysis import cohort_breakdown
from agents.analyst.conversion_api import build_conversion_api_payload
from agents.analyst.predictive_roas import project_roas
from agents.analyst.reporting import (
    attach_week_over_week,
    build_phase_a_alerts,
    build_phase_a_report,
    format_alerts_for_telegram,
    format_report_for_telegram,
    format_weekly_report_for_telegram,
)
from agents.analyst.scheduler import build_weekly_optimisation_report
from agents.analyst.schemas import KnownAgentName, ObservationRequest
from agents.analyst.scoring_feedback import build_calibration_proposals
from agents.analyst.seed_data import load_seed_dataset
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
        return format_health_check()

    if command == "/report":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_b_report",
            model_used="rule-based",
        ):
            report = attach_week_over_week(build_phase_a_report(), datetime.now(UTC))
            return format_report_for_telegram(report)

    if command == "/weekly_report":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_b_weekly_report",
            model_used="rule-based",
        ):
            report = attach_week_over_week(build_phase_a_report(), datetime.now(UTC))
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

    if command == "/predictive_roas":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_c_predictive_roas",
            model_used="rule-based",
        ):
            result = project_roas(load_seed_dataset(), client_id=active_client_id)
            return format_predictive_roas_for_telegram(result)

    if command == "/cohorts":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_c_cohorts",
            model_used="rule-based",
        ):
            result = cohort_breakdown(load_seed_dataset(), group_by="campaign")
            return format_cohorts_for_telegram(result)

    if command == "/conversion_api":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_c_conversion_api",
            model_used="rule-based",
        ):
            result = build_conversion_api_payload(load_seed_dataset(), client_id=active_client_id)
            return format_conversion_api_for_telegram(result)

    if command == "/scoring_feedback":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_c_scoring_feedback",
            model_used="rule-based",
        ):
            proposals = build_calibration_proposals(load_seed_dataset())
            return format_scoring_feedback_for_telegram(proposals)

    if command == "/ab_tests":
        with traced_action(
            agent_name="analyst",
            client_id=active_client_id,
            phase="phase_c_ab_tests",
            model_used="rule-based",
        ):
            results = evaluate_ab_tests(load_seed_dataset())
            return format_ab_tests_for_telegram(results)

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


def format_health_check() -> str:
    """Check every dependency the Analyst relies on and format the result.

    Args:
        None.

    Returns:
        str: A French, emoji-flagged health summary (✅/❌ per dependency)
        for PostgreSQL, Langfuse, and the active LLM provider. PostgreSQL
        is checked live (bounded by the same 3s connect timeout
        `common.db.get_engine()` already sets); Langfuse/LLM only check
        whether a key is configured, no network call.
    """

    from common.db import is_database_reachable
    from common.llm import active_model
    from common.llm import is_configured as llm_is_configured

    database_ok = is_database_reachable()
    langfuse_ok = bool(settings.get("LANGFUSE_PUBLIC_KEY")) and bool(
        settings.get("LANGFUSE_SECRET_KEY")
    )
    llm_ok = llm_is_configured()
    provider_name = active_model().split("/", 1)[0].capitalize()

    def _icon(ok: bool) -> str:
        return "✅" if ok else "❌"

    now = datetime.now(UTC)
    return (
        "🩺 État de l'Agent Analyst\n\n"
        f"{_icon(database_ok)} PostgreSQL : {'OK' if database_ok else 'Injoignable'}\n"
        f"{_icon(langfuse_ok)} Langfuse : {'OK' if langfuse_ok else 'Non configuré'}\n"
        f"{_icon(llm_ok)} LLM ({provider_name}) : {'OK' if llm_ok else 'Non configuré'}\n\n"
        f"🕐 {now.strftime('%Y-%m-%d %H:%M')} UTC"
    )


def format_predictive_roas_for_telegram(result: dict) -> str:
    """Format the C2 predictive ROAS projection as a French Telegram message."""

    if not result["sufficient_data"]:
        return (
            "📈 ROAS prédictif - Agent Analyst\n\n"
            f"⚠️ Données insuffisantes : seulement {result['pipeline_volume']} lead(s) SQL "
            "dans le pipeline -- pas assez de volume pour une projection fiable."
        )

    lines = [
        "📈 ROAS prédictif - Agent Analyst",
        "",
        f"💰 Revenu projeté ({result['days']} jours) : "
        f"{result['projected_revenue_low']:.2f} - {result['projected_revenue_high']:.2f}",
        "",
        "Hypothèses :",
    ]
    lines.extend(f"- {assumption}" for assumption in result["assumptions"])
    return "\n".join(lines)


def format_cohorts_for_telegram(result: dict) -> str:
    """Format the C3 cohort breakdown as a French Telegram message."""

    lines = [
        "👥 Analyse de cohortes - Agent Analyst",
        f"Regroupement : {result['group_by']}",
        "",
    ]
    if result["ranked"]:
        lines.append("Classement (par taux de closed-won) :")
        for position, key in enumerate(result["ranked"], start=1):
            cohort = result["cohorts"][key]
            lines.append(
                f"{position}. {key} : {cohort['closed_won_rate_pct']:.2f}% closed-won "
                f"({cohort['lead_count']} leads, {cohort['sql_rate_pct']:.2f}% SQL)"
            )
    else:
        lines.append("Aucune cohorte n'a assez de volume pour être classée.")

    if result["insufficient"]:
        insufficient_list = ", ".join(result["insufficient"])
        lines.append("")
        lines.append(f"⚠️ Cohortes insuffisantes (< seuil de volume) : {insufficient_list}")

    return "\n".join(lines)


def format_conversion_api_for_telegram(result: dict) -> str:
    """Format the C1 Conversion API payload preview as a French Telegram message."""

    return (
        "🔄 Aperçu Conversion API - Agent Analyst\n\n"
        f"✅ {len(result['pushed'])} deal(s) prêt(s) à pousser vers Meta/Google\n"
        f"⚠️ {result['excluded_no_click_id']} deal(s) exclu(s) -- pas de click_id\n\n"
        "🧪 Mode dry-run : rien n'est réellement envoyé. L'endpoint réel de Media Buyer "
        "(/capi/push-conversion) attend un email+pixel_id, pas un click_id -- voir les "
        "limitations connues du README."
    )


SCORING_DIRECTION_LABELS = {"decrease": "diminuer", "increase": "augmenter"}


def format_scoring_feedback_for_telegram(proposals: list[dict]) -> str:
    """Format the C4 scoring calibration proposals as a French Telegram message."""

    if not proposals:
        return (
            "🎯 Feedback de scoring - Agent Analyst\n\n"
            "Aucune proposition de recalibrage cette semaine."
        )

    lines = ["🎯 Feedback de scoring - Agent Analyst", ""]
    for proposal in proposals:
        evidence = proposal["evidence"]
        direction = SCORING_DIRECTION_LABELS.get(
            proposal["suggested_direction"], proposal["suggested_direction"]
        )
        lines.extend(
            [
                f"⚠️ Proposition : {proposal['dimension']}",
                f"- Poids actuel : {proposal['current_weight']}",
                f"- Score moyen (deals gagnés) : {evidence['avg_score_closed_won']} "
                f"(n={evidence['sample_size_closed_won']})",
                f"- Score moyen (autres) : {evidence['avg_score_other']} "
                f"(n={evidence['sample_size_other']})",
                f"- Suggestion : {direction} ce poids -- le plus élevé, "
                "mais le moins corrélé au résultat réel",
                "",
            ]
        )
    return "\n".join(lines).strip()


def format_ab_tests_for_telegram(results: list[dict]) -> str:
    """Format the C5 A/B test conclusions as a French Telegram message."""

    lines = ["🧪 Conclusions des tests A/B - Agent Analyst", ""]
    for result in results:
        if result["status"] == "winner":
            lines.append(
                f"🏆 {result['variant_group_id']} : gagnant = {result['winner_asset_id']} "
                f"(variante {result['winner_variant']}), p={result['p_value']:.4f}"
            )
        elif result["status"] == "no_winner":
            lines.append(
                f"➡️ {result['variant_group_id']} : pas de gagnant clair "
                "(différence non significative à 95%)"
            )
        else:
            lines.append(
                f"⚠️ {result['variant_group_id']} : données insuffisantes "
                "(< 30 conversions par variante)"
            )
    return "\n".join(lines)


def build_help_message() -> str:
    """Build the Telegram welcome/help message.

    Returns:
        str: Help text listing commands, agents, and examples.
    """

    return (
        "Analyst Agent Phase C is active.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/help - Show this message\n"
        "/health - Check Analyst status\n"
        "/report - Show the Phase B KPI report\n"
        "/weekly_report - Show weekly KPIs and alerts\n"
        "/alerts - Check conversion drops above 50%\n"
        "/optimisation_report - Preview the weekly scale/pause/rewrite recommendations "
        "(normally sent automatically every Monday)\n"
        "/predictive_roas - Project expected revenue over the next 30 days (C2)\n"
        "/cohorts - Break lead quality down by campaign cohort (C3)\n"
        "/conversion_api - Preview the weekly Conversion API payload, dry-run only (C1)\n"
        "/scoring_feedback - Show scoring-dimension recalibration proposals (C4)\n"
        "/ab_tests - Show A/B test winner conclusions (C5)\n"
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
