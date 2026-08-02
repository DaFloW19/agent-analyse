"""No-op-safe text generation wrapper shared by every agent.

Wraps `litellm.completion` so agent code can request a short generation
without caring whether an API key is configured, or which provider is
active. When the active provider's API key is blank (the default dev
state, see `.env.example`), `generate_text` is a no-op returning `None` --
callers must treat that exactly like "no data" elsewhere in this project:
never crash, never block, never fabricate a fallback that looks like a
real answer. A reachability or API failure is caught, logged through
`common.logging.log_action`, and also returns `None` rather than raising.

Per the model selection rules (roadmap PDF section 4.3) and team decision,
DeepSeek is the default mid-tier model for "reasoning, content strategy"
work -- summarising already-computed figures into plain language, not
calculating them. KPI math must never move into this module; it stays in
`common/metrics.py`. The active model is overridable via `LLM_MODEL`
(e.g. to `gemini/gemini-1.5-flash` while DeepSeek billing is unavailable)
without touching this module -- litellm routes by the model string's
provider prefix, which is the whole point of using it instead of a
provider-specific SDK.
"""

from __future__ import annotations

from time import perf_counter

from tenacity import retry, stop_after_attempt, wait_exponential

from common.logging import log_action
from common.tracing import traced_action
from config.settings import settings

DEFAULT_MODEL = "deepseek/deepseek-chat"

# Maps a litellm model prefix to the settings key holding its API key.
# Add an entry here when a new provider is used, never a second wrapper.
PROVIDER_API_KEY_SETTINGS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def active_model() -> str:
    """Return the active litellm model string.

    Returns:
        str: `LLM_MODEL` if set, otherwise `DEFAULT_MODEL`
        (`"deepseek/deepseek-chat"`, the team's agreed default).
    """

    return settings.get("LLM_MODEL") or DEFAULT_MODEL


def _active_api_key(model: str) -> str | None:
    """Return the API key setting for the model's provider prefix.

    Args:
        model: A litellm model string, e.g. `"gemini/gemini-1.5-flash"`.

    Returns:
        str | None: The configured key, or `None` if the provider is
        unrecognised or its key setting is unset.
    """

    provider = model.split("/", 1)[0]
    setting_name = PROVIDER_API_KEY_SETTINGS.get(provider)
    if setting_name is None:
        return None
    return settings.get(setting_name)


def is_configured() -> bool:
    """Return whether the active provider has an API key configured.

    Returns:
        bool: True when the active model's provider API key is set.
    """

    return bool(_active_api_key(active_model()))


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
    """Generate a short natural-language completion via the active LLM.

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
        str | None: The generated text, or `None` when the active provider
        is unconfigured or the call fails for any reason. Never raises.
    """

    model = active_model()
    if not _active_api_key(model):
        return None

    started_at = perf_counter()
    with traced_action(
        agent_name=agent_name,
        client_id=client_id,
        phase=phase,
        model_used=model,
        lead_id=lead_id,
        as_type="generation",
    ):
        try:
            response = _completion_with_retry(
                model=model,
                api_key=_active_api_key(model),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content.strip()
        except Exception as exc:  # noqa: BLE001 - an LLM outage must never crash the caller
            _log_generation_failure(agent_name, client_id, lead_id, phase, model, exc)
            return None

        latency_ms = int((perf_counter() - started_at) * 1000)
        log_action(
            agent_name=agent_name,
            action_type="llm_generation",
            input_summary=f"{model} completion for phase={phase}",
            output_summary=f"Generated {len(text)} characters",
            lead_id=lead_id,
            client_id=client_id,
            model_used=model,
            latency_ms=latency_ms,
        )
        return text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def _completion_with_retry(
    *, model: str, api_key: str | None, system_prompt: str, user_prompt: str, max_tokens: int
):
    """Call `litellm.completion` with exponential backoff, up to 3 attempts.

    Retry parameters match the Media Buyer and Closer agents' own tenacity
    usage on their external calls, for a consistent retry pattern across
    the system (per `AGENT_LIBRARIES_ADDENDUM.md`: nothing in the stack
    retried transient failures before this).

    Args:
        model: Active litellm model string.
        api_key: API key for that model's provider.
        system_prompt: System role content.
        user_prompt: User role content.
        max_tokens: Upper bound on the completion length.

    Returns:
        The raw `litellm.completion` response.

    Raises:
        Exception: Whatever `litellm` raises, after 3 failed attempts.
            `generate_text` catches this and returns `None` rather than
            raising further -- an LLM outage must never crash the caller.
    """

    import litellm

    return litellm.completion(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        timeout=10,
    )


def _log_generation_failure(
    agent_name: str, client_id: str, lead_id: str | None, phase: str, model: str, exc: Exception
) -> None:
    """Log an LLM call failure without raising it to the caller."""

    log_action(
        agent_name=agent_name,
        action_type="llm_generation_failed",
        input_summary=f"Attempted a {model} completion for phase={phase}",
        output_summary="Continuing without a generated summary for this action.",
        lead_id=lead_id,
        client_id=client_id,
        model_used=model,
        latency_ms=0,
        extra_fields={"error_type": type(exc).__name__, "error_message": str(exc)},
    )
