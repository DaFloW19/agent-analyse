"""Central log store engine and schema (`agent_logs`).

`get_engine()` lazily creates a single SQLAlchemy engine for the process,
bound to `settings.database_url` (Postgres in dev/prod, in-memory SQLite in
tests per `[testing]` in `config/settings.toml`). `common.logging.log_action`
uses this module to dual-write every log entry to `agent_logs`, alongside
the local JSONL file, which always remains the source of truth if the
database is unreachable.

There is no Alembic in this repo. `create_all()` is idempotent
(`CREATE TABLE IF NOT EXISTS` semantics) and is called once when the engine
is first created, which is enough for a single-table, pre-production repo.
See `migrations/agent_logs.sql` for the equivalent raw DDL, kept for
review/documentation purposes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Engine, Index, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from config.settings import settings


class Base(DeclarativeBase):
    """Declarative base for every table in the central log store."""


class AgentLog(Base):
    """Mandatory-format action log row, mirrored from the local JSONL log."""

    __tablename__ = "agent_logs"
    __table_args__ = (
        Index("ix_agent_logs_client_agent_timestamp", "client_id", "agent_name", "timestamp"),
        Index("ix_agent_logs_lead_timestamp", "lead_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    output_summary: Mapped[str] = mapped_column(Text, nullable=False)
    lead_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_ENGINE: Engine | None = None


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating it once.

    Uses `StaticPool` for in-memory SQLite URLs so every session shares the
    same connection — otherwise each connection would see its own empty
    `:memory:` database.

    Returns:
        Engine: Engine bound to `settings.database_url`, with `agent_logs`
        already created.
    """

    global _ENGINE
    if _ENGINE is None:
        database_url = settings.database_url
        if "sqlite" in database_url and ":memory:" in database_url:
            from sqlalchemy.pool import StaticPool

            engine_kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        else:
            # A silently-dropped connection (firewall, wrong host) must fail fast,
            # not hang — "the agent must keep running" also means it must not block.
            engine_kwargs = {"pool_pre_ping": True, "connect_args": {"connect_timeout": 3}}
        _ENGINE = create_engine(database_url, **engine_kwargs)
        Base.metadata.create_all(_ENGINE)
    return _ENGINE


def reset_engine_for_testing() -> None:
    """Drop the cached engine so the next `get_engine()` call rebuilds it.

    Only intended for test isolation between test modules that configure
    different `settings.database_url` values.
    """

    global _ENGINE
    _ENGINE = None


def write_agent_log(entry: dict) -> None:
    """Write one mandatory-format log entry to the `agent_logs` table.

    Args:
        entry: A log entry as built by `common.logging.log_action`, already
            validated against the mandatory schema.

    Raises:
        Exception: Any database error is propagated to the caller.
            `common.logging.log_action` is expected to catch it so a
            database outage never stops an agent from running.
    """

    engine = get_engine()
    with Session(engine) as session:
        session.add(
            AgentLog(
                agent_name=entry["agent_name"],
                action_type=entry["action_type"],
                input_summary=entry["input_summary"],
                output_summary=entry["output_summary"],
                lead_id=entry["lead_id"],
                client_id=entry["client_id"],
                model_used=entry["model_used"],
                latency_ms=entry["latency_ms"],
                timestamp=datetime.fromisoformat(str(entry["timestamp"]).replace("Z", "+00:00")),
            )
        )
        session.commit()
