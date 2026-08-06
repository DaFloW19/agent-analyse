"""Weekly LLM-output eval job for the Analyst (Phase C, C6 -- Analyst-only scope).

C6 asks for active eval jobs across all 7 agents. Only the Analyst has a
real LLM call to evaluate here -- the weekly report's plain-language summary
(`common/llm.py::generate_text`) -- the other 6 agents' eval jobs need their
own Langfuse-instrumented calls, none of which exist yet in their repos.
This module covers the 1/7 that's actually possible today; see
`agents/analyst/README.md`'s "Known limitations" for the rest.

Two deterministic, testable checks, not another LLM call judging an LLM
call:
    - grounding: every number mentioned in the summary must (approximately)
      match one of the figures actually given to the prompt -- catches an
      invented statistic.
    - language: a lightweight French-language heuristic (every report is
      French per the readability rewrite, so the summary should read as
      French too).
"""

from __future__ import annotations

import re

from common.logging import log_action
from common.tracing import record_score

FRENCH_MARKERS = ("le ", "la ", "les ", "de ", "du ", "des ", "un ", "une ", "et ", "pour ")
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
# Numbers are compared rounded to 1 decimal, since a figure like ROAS 1.6 may
# legitimately be rendered "1.60x" in the summary -- an exact string match
# would falsely flag it as ungrounded.
NUMBER_TOLERANCE_DECIMALS = 1


def evaluate_weekly_summary(summary_text: str, source_figures: dict, client_id: str) -> dict:
    """Score one weekly AI summary for grounding and language.

    Args:
        summary_text: The generated summary (from `common.llm.generate_text`).
        source_figures: The numeric figures actually fed to the prompt (e.g.
            `{"cpql": 148.31, "roas": 1.6}`) -- every number the summary
            mentions must trace back to one of these.
        client_id: Client identifier, used only for the caller's logging.

    Returns:
        dict: `{grounded, ungrounded_numbers, looks_french, score}`.
        `score` is the fraction of the two checks passed (0.0, 0.5, or
        1.0) -- a simple, explainable signal, not a black-box LLM judgment.
    """

    allowed_numbers = {
        _round(value) for value in source_figures.values() if isinstance(value, (int, float))
    }
    mentioned_numbers = NUMBER_PATTERN.findall(summary_text)
    ungrounded = [
        number for number in mentioned_numbers if _round(number) not in allowed_numbers
    ]
    grounded = len(ungrounded) == 0

    lowered = f" {summary_text.lower()} "
    looks_french = any(marker in lowered for marker in FRENCH_MARKERS)

    return {
        "grounded": grounded,
        "ungrounded_numbers": ungrounded,
        "looks_french": looks_french,
        "score": (int(grounded) + int(looks_french)) / 2,
    }


def run_weekly_eval_job(
    summary_text: str | None, source_figures: dict, client_id: str
) -> dict | None:
    """Evaluate the weekly summary and record/log the result, no-op when there is none.

    Args:
        summary_text: The generated summary, or `None` when the LLM wasn't
            configured/reachable that week -- nothing to evaluate.
        source_figures: The numeric figures actually fed to the prompt.
        client_id: Client identifier.

    Returns:
        dict | None: The evaluation result (see `evaluate_weekly_summary`),
        or `None` when `summary_text` is `None`.
    """

    if summary_text is None:
        return None

    result = evaluate_weekly_summary(summary_text, source_figures, client_id)

    record_score(
        name="weekly_summary_quality",
        value=result["score"],
        client_id=client_id,
        comment=f"grounded={result['grounded']}, looks_french={result['looks_french']}",
    )
    log_action(
        agent_name="analyst",
        action_type="weekly_summary_eval",
        input_summary="Scored the weekly AI summary for grounding and language",
        output_summary=(
            f"score={result['score']}, grounded={result['grounded']}, "
            f"looks_french={result['looks_french']}"
        ),
        lead_id=None,
        client_id=client_id,
        model_used="rule-based",
        latency_ms=0,
    )
    return result


def _round(value: object) -> float:
    """Round a number (or numeric string) for tolerant grounding comparison."""

    return round(float(value), NUMBER_TOLERANCE_DECIMALS)
