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
    path: str | Path | None = None,
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
        path: JSONL destination path. Defaults to `logs/{agent_name}.jsonl`
            so every agent keeps its own append-only history file (Phase A
            requirement) without every caller having to know the convention.
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
    resolved_path = path if path is not None else Path(f"logs/{agent_name}.jsonl")
    _write_jsonl(entry, resolved_path)
    _write_to_central_store(entry, resolved_path)
    return entry


def _write_jsonl(entry: dict[str, Any], path: str | Path) -> None:
    """Append one log entry to the local append-only JSONL file.

    Args:
        entry: Log entry to write. Must already be validated.
        path: JSONL destination path.
    """

    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")


def _write_to_central_store(entry: dict[str, Any], path: str | Path) -> None:
    """Best-effort dual-write of one log entry to the central `agent_logs` table.

    Never raises: a database outage must not stop an agent from logging or
    running (Phase B rule: keep writing the local file, no crash). On
    failure, the failure itself is appended to the local JSONL file so it
    stays visible in the audit trail.

    Args:
        entry: Log entry already written to the local JSONL file.
        path: JSONL destination path, reused for the failure entry.
    """

    from common.db import (
        write_agent_log,  # local import: log_action stays usable with no DB configured
    )

    try:
        write_agent_log(entry)
    except Exception as exc:  # noqa: BLE001 - a DB outage must never crash the caller
        _write_jsonl(
            {
                **entry,
                "action_type": "central_log_write_failed",
                "db_write_failed": True,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
            path,
        )


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

