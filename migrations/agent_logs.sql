-- Central log store schema (agent_logs).
--
-- This repo has no Alembic migration runner. This file is the raw DDL
-- equivalent of the SQLAlchemy model in `common/db.py`, kept for review and
-- documentation purposes. The actual table is created by
-- `common.db.get_engine()` (idempotent, `CREATE TABLE IF NOT EXISTS`
-- semantics) the first time any agent logs an action, or explicitly via
-- `python -m scripts.init_db`. If this file and `common/db.py` ever
-- disagree, `common/db.py` is the source of truth.

CREATE TABLE IF NOT EXISTS agent_logs (
    id BIGSERIAL PRIMARY KEY,
    agent_name VARCHAR(100) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    input_summary TEXT NOT NULL,
    output_summary TEXT NOT NULL,
    lead_id VARCHAR(100) NULL,
    client_id VARCHAR(100) NOT NULL,
    model_used VARCHAR(100) NOT NULL,
    latency_ms INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_agent_logs_client_agent_timestamp
    ON agent_logs (client_id, agent_name, timestamp);

CREATE INDEX IF NOT EXISTS ix_agent_logs_lead_timestamp
    ON agent_logs (lead_id, timestamp);
