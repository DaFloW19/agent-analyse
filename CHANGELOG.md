# Changelog

## Unreleased

- Created the initial repository structure.
- Added the Analyst work plan under `docs/`.
- Added the Python project bootstrap with a minimal Analyst FastAPI app.
- Added the canonical metrics module with fixture-backed tests for the 9 KPIs.
- Added Phase B local JSONL logging and wired Analyst `/observe` and `/report`.
- Added a Phase B Telegram long-polling bot with `/health`, `/report`, and `/observe`.
- Fixed a documentation bug: the Analyst's Phase A audit/log-store step had been mislabeled Phase B in `docs/ANALYST_AGENT_WORK_PLAN.md` and `docs/PROJECT_CONTEXT.md`, restored against the supervisor's original brief.
- Added SETUP-03: a deterministic seed dataset generator (`agents/analyst/seed_data.py`, ~400 leads over 8 weeks) replacing the tiny hardcoded `demo_data.py` fixtures.
- Added B1: a data pull layer (`agents/analyst/data_pull.py`) shaping seed data for `common/metrics.py`, with no KPI arithmetic outside it.
- Added B2: attribution breakdown by campaign/ad set/creative asset (`agents/analyst/attribution.py`), with an explicit `unattributed` bucket and top/bottom performer ranking.
- Added B3: landing page performance (`agents/analyst/landing_pages.py`), flagging pages below the 15% visitor-to-form threshold.
- Completed B5/ANA-03: `build_conversion_drop_alerts` now requires both a threshold breach and a minimum sample-size floor before alerting; drops below the floor are suppressed and logged with their counts instead. Added `mark_stale` to flag KPI figures whose source data is older than 6 hours.
- Added B6: a weekly optimisation report (`agents/analyst/scheduler.py`) with concrete scale/pause/rewrite recommendations backed by figures, scheduled every Monday via APScheduler. The Analyst never executes any recommendation.
- Added B7: a no-op-safe Langfuse tracing wrapper (`common/tracing.py`). Tracing is a clean no-op when `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` are unset, and never crashes the caller if Langfuse is unreachable. Wired into `/report`, `/observe`, `/weekly_report`, and `/alerts`.
- Added the central `agent_logs` store (`common/db.py`, SQLAlchemy, no Alembic): `log_action` now dual-writes to Postgres/SQLite in addition to the local JSONL file, with a fast connection timeout and a logged fallback if the database is unreachable so an agent never crashes or hangs because of a database outage.
- Added `tests/conftest.py` forcing the test suite onto an in-memory SQLite database, independent of local `.env` contents.
- Added `/optimisation_report`, a manual Telegram command to preview the B6 weekly report without waiting for the Monday 08:00 job.
- Closed ticket 7.1 (Phase A audit and log store): added `scripts/generate_test_logs.py`, simulating one realistic action per non-Analyst agent (Commander, CRM Keeper, Qualifier, Content Strategist, Media Buyer, Closer) through the same shared `log_action`, since those agents do not exist in this repo yet. `tests/test_multi_agent_logging.py` proves all 6 rows land in `agent_logs` with every mandatory field populated. Updated `docs/LOG_AUDIT.md` to distinguish "pass (simulated)" — pipeline proven, agent not built — from a real pass, and recorded that the Media Buyer and Closer agents (reviewed directly from their own repos) exist but never call a validated `log_action`, which is their actual Phase A gap, not a documentation one. Also recorded that a second, separate "Phase A" scaffold was found in a colleague's own repo and is being consolidated into this one per the work plan's "one shared repo, no forks" rule.
- Fixed `.env`'s `DATABASE_URL` (`postgresql://` -> `postgresql+psycopg://`, the scheme our `psycopg`-based dependency actually needs) and validated the central `agent_logs` store against a real local PostgreSQL 17 instance for the first time: schema creation, all 6 simulated agent logs written with zero database-write failures, confirmed by direct query.
- Added the first real LLM call in the Analyst: `common/llm.py`, a no-op-safe DeepSeek wrapper (`litellm`, model `deepseek/deepseek-chat`) mirroring `common/tracing.py`'s pattern -- a blank `DEEPSEEK_API_KEY` makes generation a clean no-op, and any API failure is caught, logged, and returns `None`, never raised. Every call is traced as a Langfuse generation (B7) and logged through the mandatory log format, success or failure. Wired into the weekly optimisation report (B6): `build_weekly_optimisation_report` now ends with a 2-3 sentence plain-language summary of that week's scale/pause/rewrite recommendations and overall ROAS, generated from the same figures already shown -- never used to calculate a KPI, only to explain one in prose, consistent with `common/metrics.py` staying the only place KPI math happens.
