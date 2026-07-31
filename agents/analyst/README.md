# Analyst Agent

The Analyst is the observation and performance intelligence agent. It studies historical activity, calculates KPIs, detects anomalies, and sends optimisation recommendations to the Commander and specialist agents.

## Responsibilities

- Audit all agent logs against the mandatory schema.
- Calculate funnel and performance KPIs through the shared metrics module.
- Produce KPI reports with week-on-week changes.
- Detect anomalies and stale data.
- Analyse campaign, ad set, asset, landing page, cohort, and scoring performance.
- Act as an observation binome when another agent is called for a task.
- Drive Langfuse tracing and evaluation review.

## What This Agent Does Not Do

- It does not change budgets.
- It does not send WhatsApp or email messages.
- It does not edit CRM lead records directly.
- It does not publish content.
- It does not bypass Commander approval or specialist guardrails.

## Current Phase

Bootstrap toward Phase A. The current implementation exposes a health endpoint and a side-effect-free binome observation endpoint.

## Running The Agent

```powershell
python -m uvicorn agents.analyst.main:app --reload
```

## Running The Telegram Bot

Set `TELEGRAM_BOT_TOKEN` in `.env`, then run:

```powershell
python -m agents.analyst.telegram_bot
```

Phase A commands:

```text
/start
/health
/report
/observe media_buyer
/observe media_buyer pause_ad_set conversions=6 dry_run=true
```

## Running Tests

```powershell
python -m pytest
```

## Inputs And Outputs

### Observation Input

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

### Observation Output

The Analyst returns KPI, guardrail, logging, risk, and recommendation context. It does not execute the task.
