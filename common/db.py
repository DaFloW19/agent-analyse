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

from sqlalchemy import DateTime, Engine, Float, Index, Integer, String, Text, create_engine, select
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


class KpiSnapshot(Base):
    """One KPI value captured at a point in time, for week-on-week comparison.

    Written once per metric by the Monday weekly job (`scheduler.py`), not
    on every manual `/report` call, to avoid noisy near-duplicate rows.
    """

    __tablename__ = "kpi_snapshots"
    __table_args__ = (
        Index("ix_kpi_snapshots_client_metric_captured", "client_id", "metric_name", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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


def is_database_reachable() -> bool:
    """Return whether the configured database accepts a trivial query.

    Bounded by the same fast-fail connect timeout `get_engine()` already
    sets for non-SQLite dialects (3s) -- a health check must never hang.

    Returns:
        bool: True if a `SELECT 1` succeeds, False on any error (including
        the database being entirely unreachable). Never raises.
    """

    from sqlalchemy import text

    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - a health check must never crash or raise
        return False


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


def write_kpi_snapshot(
    client_id: str, metric_name: str, value: float | None, captured_at: datetime
) -> None:
    """Write one KPI snapshot row for later week-on-week comparison.

    Args:
        client_id: Client identifier.
        metric_name: Canonical KPI key (e.g. `"cpl"`).
        value: The metric's value at `captured_at`, or `None` when the
            metric had no data that period.
        captured_at: When this value was computed.

    Raises:
        Exception: Any database error is propagated to the caller, which is
            expected to catch it -- a database outage must not stop the
            weekly job from sending the rest of its report.
    """

    engine = get_engine()
    with Session(engine) as session:
        session.add(
            KpiSnapshot(
                client_id=client_id,
                metric_name=metric_name,
                value=value,
                captured_at=captured_at,
            )
        )
        session.commit()


def get_closest_kpi_snapshot(
    client_id: str, metric_name: str, target_time: datetime
) -> float | None:
    """Return the snapshot value closest in time to `target_time`.

    Args:
        client_id: Client identifier.
        metric_name: Canonical KPI key.
        target_time: The point in time to find the nearest snapshot to
            (typically "now minus 7 days").

    Returns:
        float | None: The closest snapshot's value, or `None` if no
        snapshot exists for this client/metric yet (e.g. the first Monday).
    """

    engine = get_engine()
    with Session(engine) as session:
        rows = session.scalars(
            select(KpiSnapshot).where(
                KpiSnapshot.client_id == client_id, KpiSnapshot.metric_name == metric_name
            )
        ).all()

    if not rows:
        return None

    # SQLite silently drops tzinfo on DateTime(timezone=True) columns (Postgres does
    # not), so `row.captured_at` may come back naive while `target_time` is aware --
    # compare both as naive UTC rather than branching on the dialect.
    naive_target = target_time.replace(tzinfo=None)
    closest = min(
        rows,
        key=lambda row: abs((row.captured_at.replace(tzinfo=None) - naive_target).total_seconds()),
    )
    return closest.value
