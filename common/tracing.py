"""No-op-safe Langfuse tracing wrapper shared by every agent (B7).

Wraps Langfuse observability so agent code can request a trace without
caring whether Langfuse is configured. When `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` are blank (the default dev state, see
`.env.example`), tracing becomes a complete no-op: the wrapped code still
runs normally, nothing is sent anywhere, and no exception is raised.
Failures to reach a *configured* Langfuse host are caught and logged
through `common.logging.log_action`, never raised to the caller — an
observability outage must never take an agent down with it.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Any, Literal

from common.logging import log_action
from config.settings import settings

ObservationType = Literal["span", "generation"]

_CACHED_CLIENT_STATE: dict[str, Any] = {"checked": False, "client": None}


def get_langfuse_client() -> Any | None:
    """Return a configured Langfuse client, or `None` when unconfigured.

    Returns:
        Any | None: A `langfuse.Langfuse` client when
        `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are both set, otherwise
        `None`. The client is created once and cached for the process
        lifetime.
    """

    if _CACHED_CLIENT_STATE["checked"]:
        return _CACHED_CLIENT_STATE["client"]

    _CACHED_CLIENT_STATE["checked"] = True
    public_key = settings.get("LANGFUSE_PUBLIC_KEY") or ""
    secret_key = settings.get("LANGFUSE_SECRET_KEY") or ""
    if not public_key or not secret_key:
        return None

    from langfuse import Langfuse

    _CACHED_CLIENT_STATE["client"] = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=settings.get("LANGFUSE_HOST") or "https://cloud.langfuse.com",
    )
    return _CACHED_CLIENT_STATE["client"]


@contextmanager
def traced_action(
    *,
    agent_name: str,
    client_id: str,
    phase: str,
    model_used: str,
    lead_id: str | None = None,
    as_type: ObservationType = "span",
):
    """Trace an agent action, no-op if Langfuse is unconfigured or unreachable.

    Args:
        agent_name: Name of the agent performing the action.
        client_id: Client identifier.
        phase: Project phase the action belongs to (e.g. `"phase_b"`).
        model_used: Model name, or `"rule-based"` for hardcoded logic.
        lead_id: Lead identifier, when the action is lead-specific.
        as_type: `"generation"` for an LLM call, `"span"` for everything else.

    Yields:
        The active Langfuse observation, or `None` when tracing is a no-op
        (unconfigured, or the observation could not be started).
    """

    client = get_langfuse_client()
    if client is None:
        yield None
        return

    stack = ExitStack()
    metadata = {
        "agent_name": agent_name,
        "client_id": client_id,
        "lead_id": lead_id,
        "phase": phase,
        "model_used": model_used,
    }
    try:
        observation = stack.enter_context(
            client.start_as_current_observation(
                name=f"{agent_name}.{phase}",
                as_type=as_type,
                model=model_used,
                metadata=metadata,
            )
        )
    except Exception as exc:  # noqa: BLE001 - an observability outage must never take the agent down
        _log_tracing_failure(agent_name, client_id, lead_id, exc)
        stack.close()
        yield None
        return

    try:
        yield observation
    finally:
        stack.close()


def _log_tracing_failure(
    agent_name: str, client_id: str, lead_id: str | None, exc: Exception
) -> None:
    """Log a Langfuse connection failure without raising it to the caller."""

    log_action(
        agent_name=agent_name,
        action_type="tracing_failed",
        input_summary="Attempted to start a Langfuse observation.",
        output_summary="Continuing without tracing for this action.",
        lead_id=lead_id,
        client_id=client_id,
        model_used="rule-based",
        latency_ms=0,
        extra_fields={"error_type": type(exc).__name__, "error_message": str(exc)},
    )


def record_score(
    *,
    name: str,
    value: float,
    client_id: str,
    comment: str | None = None,
    agent_name: str = "analyst",
) -> None:
    """Attach a numeric score to Langfuse (e.g. an eval job result), no-op-safe.

    A clean no-op when Langfuse is unconfigured, same as `traced_action`. A
    failure to reach a *configured* Langfuse host is caught and logged
    through `common.logging.log_action`, never raised (C6).

    Args:
        name: Score name (e.g. `"weekly_summary_quality"`).
        value: Score value.
        client_id: Client identifier, used for the failure log entry.
        comment: Optional human-readable explanation of the score.
        agent_name: Name of the agent recording the score.
    """

    client = get_langfuse_client()
    if client is None:
        return

    try:
        client.create_score(name=name, value=value, comment=comment)
    except Exception as exc:  # noqa: BLE001 - an observability outage must never crash the caller
        log_action(
            agent_name=agent_name,
            action_type="score_failed",
            input_summary=f"Attempted to record Langfuse score '{name}'",
            output_summary="Continuing without recording this score.",
            lead_id=None,
            client_id=client_id,
            model_used="rule-based",
            latency_ms=0,
            extra_fields={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
