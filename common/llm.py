"""No-op-safe DeepSeek text generation wrapper shared by every agent.

Wraps `litellm.completion` so agent code can request a short generation
without caring whether an API key is configured. When `DEEPSEEK_API_KEY` is
blank (the default dev state, see `.env.example`), `generate_text` is a
no-op returning `None` -- callers must treat that exactly like "no data"
elsewhere in this project: never crash, never block, never fabricate a
fallback that looks like a real answer. A reachability or API failure is
caught, logged through `common.logging.log_action`, and also returns
`None` rather than raising.

Per the model selection rules (roadmap PDF section 4.3), DeepSeek is the
mid-tier model for "reasoning, content strategy" work -- summarising
already-computed figures into plain language, not calculating them. KPI
math must never move into this module; it stays in `common/metrics.py`.
"""

from __future__ import annotations

from time import perf_counter

from common.logging import log_action
from common.tracing import traced_action
from config.settings import settings

DEEPSEEK_MODEL = "deepseek/deepseek-chat"


def is_configured() -> bool:
    """Return whether a DeepSeek API key is configured.

    Returns:
        bool: True when `DEEPSEEK_API_KEY` is set to a non-empty value.
    """

    return bool(settings.get("DEEPSEEK_API_KEY"))


def generate_text(
    *,
    system_prompt: str,
    user_prompt: str,
    agent_name: str,
    client_id: str,
    phase: str,
    lead_id: str | None = None,
    max_tokens: int = 300,
) -> str | None:
    """Generate a short natural-language completion via DeepSeek.

    Traced as a Langfuse generation (B7) with the required
    agent_name/client_id/phase/model_used metadata, and logged through the
    mandatory log format on every call, success or failure.

    Args:
        system_prompt: Instructions establishing the assistant's role and
            constraints (e.g. "never invent a figure not given below").
        user_prompt: The structured data to summarise or reason over.
        agent_name: Name of the agent requesting the generation.
        client_id: Client identifier.
        phase: Project phase/feature this generation belongs to.
        lead_id: Lead identifier, when the generation is lead-specific.
        max_tokens: Upper bound on the completion length.

    Returns:
        str | None: The generated text, or `None` when DeepSeek is
        unconfigured or the call fails for any reason. Never raises.
    """

    if not is_configured():
        return None

    started_at = perf_counter()
    with traced_action(
        agent_name=agent_name,
        client_id=client_id,
        phase=phase,
        model_used=DEEPSEEK_MODEL,
        lead_id=lead_id,
        as_type="generation",
    ):
        try:
            import litellm

            response = litellm.completion(
                model=DEEPSEEK_MODEL,
                api_key=settings.get("DEEPSEEK_API_KEY"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                timeout=10,
            )
            text = response.choices[0].message.content.strip()
        except Exception as exc:  # noqa: BLE001 - an LLM outage must never crash the caller
            _log_generation_failure(agent_name, client_id, lead_id, phase, exc)
            return None

        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name=agent_name,
            action_type="llm_generation",
            input_summary=f"DeepSeek completion for phase={phase}",
            output_summary=f"Generated {len(text)} characters",
            lead_id=lead_id,
            client_id=client_id,
            model_used=DEEPSEEK_MODEL,
            latency_ms=latency_ms,
        )
        return text


def _log_generation_failure(
    agent_name: str, client_id: str, lead_id: str | None, phase: str, exc: Exception
) -> None:
    """Log a DeepSeek call failure without raising it to the caller."""

    log_action(
        agent_name=agent_name,
        action_type="llm_generation_failed",
        input_summary=f"Attempted a DeepSeek completion for phase={phase}",
        output_summary="Continuing without a generated summary for this action.",
        lead_id=lead_id,
        client_id=client_id,
        model_used=DEEPSEEK_MODEL,
        latency_ms=0,
        extra_fields={"error_type": type(exc).__name__, "error_message": str(exc)},
    )
