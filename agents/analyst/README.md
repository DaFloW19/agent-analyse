# Analyst Agent

The Analyst is the observation and performance intelligence agent. It studies historical activity, calculates KPIs, detects anomalies, and sends optimisation recommendations to the Commander and specialist agents.

## Responsibilities

- Audit all agent logs against the mandatory schema.
- Calculate funnel and performance KPIs through the shared metrics module.
- Produce KPI reports with week-on-week freshness (`data_as_of`, staleness flag).
- Break down CPL/CPQ/CPQL by campaign, ad set, and creative asset (B2), never dropping unattributed leads.
- Flag landing pages below the 15% visitor-to-form threshold (B3).
- Detect stage-conversion anomalies, subject to a minimum sample-size floor so ordinary variance never fires an alert (B5/ANA-03).
- Generate a weekly optimisation report with concrete, evidence-backed recommendations every Monday (B6), ending with a DeepSeek-generated plain-language summary of that week's figures. It only recommends — it never executes.
- Act as an observation binome when another agent is called for a task.
- Trace every action through Langfuse when configured; run as a clean no-op otherwise (B7).
- Dual-write every logged action to a local JSONL file and the central `agent_logs` table, without ever crashing or blocking if the database is unreachable.

## What This Agent Does Not Do

- It does not change budgets.
- It does not send WhatsApp or email messages.
- It does not edit CRM lead records directly.
- It does not publish content.
- It does not bypass Commander approval or specialist guardrails.

## Setup

```powershell
python -m pip install -e ".[dev]"
copy .env.example .env  # fill in TELEGRAM_BOT_TOKEN at minimum
```

## Environment variables

See the root `.env.example` for the full list (`ANALYST_CLIENT_ID`, `TELEGRAM_BOT_TOKEN`, `LANGFUSE_*`, `DATABASE_URL`, ...).

## Current Phase

Phase B, mostly complete for the Analyst:

- Done: log audit (Phase A), KPI report, weekly report + alerts, attribution breakdown (B2), landing page performance (B3), anomaly volume floor + data freshness (B5/ANA-03), weekly optimisation report scheduler (B6), Langfuse tracing (B7), central `agent_logs` store with local-JSONL fallback.
- Not started: Phase C (predictive feedback loop, Qualifier calibration, A/B conclusions, full eval suite).

## Running the agent

```powershell
python -m uvicorn agents.analyst.main:app --reload
```

## Running the Telegram bot

Set `TELEGRAM_BOT_TOKEN` in `.env`, then run:

```powershell
python -m agents.analyst.telegram_bot
```

Starting the bot also starts the weekly optimisation report job (every Monday 08:00), which sends to `TELEGRAM_ALLOWED_CHAT_ID` if set.

Commands:

```text
/start
/help
/health
/report
/weekly_report
/alerts
/optimisation_report
/observe media_buyer
/observe media_buyer pause_ad_set conversions=6 dry_run=true
```

## Running tests

```powershell
python -m pytest
```

Tests always run against an in-memory SQLite database (see `tests/conftest.py`), never a real Postgres server.

## Known limitations

- Phase C is not started.
- The central log store was validated against a real local PostgreSQL 17 instance on 2026-08-01 (schema creation + 6 simulated agent logs, zero write failures). The automated test suite still runs against in-memory SQLite for speed and CI independence.
- The seed dataset (`agents/analyst/seed_data.py`) stands in for real CRM/ad-platform data. Swapping in real data sources is a Phase C concern (data pull layer already isolates KPI arithmetic from data shape).
- The weekly optimisation report's "scale"/"pause" recommendations are based on CPQL only; richer criteria (statistical confidence, minimum conversions) are Phase C (MB-03-equivalent) work.
- Without `DEEPSEEK_API_KEY` set, the weekly report's plain-language summary shows "unavailable" instead of generated text — this is a clean no-op, not an error.

## Inputs and outputs

### Observation input

The Analyst receives a structured task summary from another agent:

```json
{
  "client_id": "demo-real-estate",
  "agent_name": "media_buyer",
  "task_type": "pause_ad_set",
  "lead_id": null,
  "input_summary": "Ad set has CPL above target for 3 days",
  "expected_output": "Pause recommendation",
  "data_points": {
    "cpl_multiplier": 2.4,
    "conversions": 40
  }
}
```

### Observation output

The Analyst returns KPI, guardrail, logging, risk, and recommendation context. It does not execute the task.

### KPI report output

`GET /report` and `/report` (Telegram) return the nine canonical KPIs, each as `{value, numerator, denominator, data_as_of}`, computed from the seed dataset via `agents/analyst/data_pull.py` and `common/metrics.py`.
