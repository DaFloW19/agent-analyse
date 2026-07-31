import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db import AgentLog, get_engine, reset_engine_for_testing
from common.logging import log_action
from config.settings import settings


def test_log_action_dual_writes_to_agent_logs_table(tmp_path):
    log_path = tmp_path / "analyst.jsonl"
    marker = "test_log_action_dual_writes_to_agent_logs_table"

    log_action(
        agent_name="analyst",
        action_type=marker,
        input_summary="in",
        output_summary="out",
        lead_id=None,
        client_id="demo-real-estate",
        model_used="rule-based",
        latency_ms=1,
        path=log_path,
    )

    with Session(get_engine()) as session:
        rows = session.scalars(select(AgentLog).where(AgentLog.action_type == marker)).all()

    assert len(rows) == 1
    assert rows[0].client_id == "demo-real-estate"

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_log_action_survives_an_unreachable_database(tmp_path):
    """Phase A/B rule: kill the DB, the agent keeps running and keeps
    writing the local file. No crash, no hang."""

    log_path = tmp_path / "analyst.jsonl"
    original_url = settings.database_url
    settings.set("database_url", "postgresql+psycopg://user:password@127.0.0.1:59999/nope")
    reset_engine_for_testing()

    try:
        entry = log_action(
            agent_name="analyst",
            action_type="test_survives_unreachable_db",
            input_summary="in",
            output_summary="out",
            lead_id=None,
            client_id="demo-real-estate",
            model_used="rule-based",
            latency_ms=1,
            path=log_path,
        )
    finally:
        settings.set("database_url", original_url)
        reset_engine_for_testing()

    assert entry["agent_name"] == "analyst"

    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["action_type"] == "test_survives_unreachable_db"
    assert lines[1]["db_write_failed"] is True
    assert lines[1]["error_type"]
