"""Shared append-only JSONL logging for every agent."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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


def log_action(
    *,
    agent_name: str,
    action_type: str,
    input_summary: str,
    output_summary: str,
    lead_id: str | None,
    client_id: str,
    model_used: str,
    latency_ms: int,
    timestamp: str | None = None,
    path: str | Path = "logs/agent_actions.jsonl",
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one mandatory-format action log entry to an append-only JSONL file.

    Args:
        agent_name: Name of the agent taking or observing the action.
        action_type: Short machine-readable action label.
        input_summary: Brief description of what the agent received.
        output_summary: Brief description of what the agent produced.
        lead_id: Lead identifier, or None for non-lead-specific actions.
        client_id: Client identifier.
        model_used: Model name, or `rule-based` for hardcoded Phase B logic.
        latency_ms: Total action latency in milliseconds.
        timestamp: ISO 8601 timestamp. Generated in UTC when omitted.
        path: JSONL destination path.
        extra_fields: Optional extra fields such as error metadata.

    Returns:
        dict[str, Any]: The log entry that was written.

    Raises:
        ValueError: If a required non-null field is empty.
        OSError: If the destination file cannot be written.
    """

    entry: dict[str, Any] = {
        "agent_name": agent_name,
        "action_type": action_type,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "lead_id": lead_id,
        "client_id": client_id,
        "model_used": model_used,
        "latency_ms": latency_ms,
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
    }
    if extra_fields:
        entry.update(extra_fields)

    validate_log_entry(entry)
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    return entry


def validate_log_entry(entry: dict[str, Any]) -> None:
    """Validate that a log entry contains the mandatory Phase B fields.

    Args:
        entry: Log entry to validate.

    Raises:
        ValueError: If a mandatory field is missing or invalid.
    """

    missing_fields = [field for field in MANDATORY_LOG_FIELDS if field not in entry]
    if missing_fields:
        raise ValueError(f"Missing mandatory log fields: {', '.join(missing_fields)}")

    nullable_fields = {"lead_id"}
    for field in MANDATORY_LOG_FIELDS:
        if field in nullable_fields:
            continue
        value = entry[field]
        if value is None or value == "":
            raise ValueError(f"Mandatory log field cannot be empty: {field}")

    if not isinstance(entry["latency_ms"], int) or entry["latency_ms"] < 0:
        raise ValueError("latency_ms must be a non-negative integer")

