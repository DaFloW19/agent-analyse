# Analyst Agent

The Analyst is the observation and performance intelligence agent. It studies historical activity, calculates KPIs, detects anomalies, and sends optimisation recommendations to the Commander and specialist agents.

## Responsibilities

- Audit all agent logs against the mandatory schema.
- Calculate funnel and performance KPIs through the shared metrics module. CPL, CPQ, CPQL, and stage_conversion_rate are pulled live from CRM Keeper and Media Buyer when both are reachable, falling back to the seed dataset otherwise (`agents/analyst/live_data.py`, `data_pull.py`). Every KPI carries a `source` field (`"live"` or `"simulated"`) so a report never silently mixes the two.
- Produce KPI reports with week-on-week deltas (`common/db.py`'s `KpiSnapshot` table, one row per metric captured every Monday) and freshness flags (`data_as_of`, staleness).
- Break down CPL/CPQ/CPQL by campaign, ad set, and creative asset (B2), never dropping unattributed leads. Always simulated: neither CRM Keeper nor Media Buyer expose this granularity (verified against their actual code).
- Flag landing pages below the 15% visitor-to-form threshold (B3), and notify Content Strategist's `/cro-analysis` best-effort (their API has no page identifier — see Known limitations).
- Detect stage-conversion anomalies, subject to a minimum sample-size floor so ordinary variance never fires an alert (B5/ANA-03) — pushed automatically every 6 hours when something fires, in addition to the on-demand `/alerts` command.
- Generate a weekly optimisation report with concrete, evidence-backed recommendations every Monday (B6), ending with an LLM-generated plain-language summary of that week's figures (DeepSeek by default, any `litellm`-supported provider via `LLM_MODEL`). It only recommends — it never executes.
- Act as an observation binome when another agent is called for a task.
- Trace every action through Langfuse when configured; run as a clean no-op otherwise (B7).
- Dual-write every logged action to a local JSONL file (one file per agent, `logs/{agent_name}.jsonl`) and the central `agent_logs` table, without ever crashing or blocking if the database is unreachable.
- Project expected closed-won revenue as a range over the next N days (C2), and break lead quality/outcomes down by acquisition cohort (C3) -- both entirely from the Analyst's own data, no other agent involved.
- Build (and log, dry-run only) the weekly Conversion API payload from closed-won deals with a click ID (C1); propose scoring-dimension recalibrations from closed-deal outcomes, never auto-applied (C4); and decide A/B test winners with the same z-test used everywhere else in this codebase (C5). All three run against simulated data standing in for tables that don't exist yet in the Qualifier's/Content Strategist's own repos -- see Known limitations.
- Score the weekly AI summary for grounding and language every Monday (C6), the one agent-eval job that's actually possible today -- the other 6 agents need their own Langfuse instrumentation first.

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

See the root `.env.example` for the full list (`ANALYST_CLIENT_ID`, `TELEGRAM_BOT_TOKEN`, `LANGFUSE_*`, `DATABASE_URL`, `CRM_KEEPER_URL`, `MEDIA_BUYER_URL`, `CONTENT_STRATEGIST_URL`, ...). The three agent URLs are best-effort: if unreachable, the Analyst falls back to simulated data and never crashes.

## Current Phase

Phase C, code-complete for the Analyst's own scope:

- Phase A/B: log audit, KPI report, weekly report + alerts, attribution breakdown (B2), landing page performance (B3), anomaly volume floor + data freshness (B5/ANA-03), weekly optimisation report scheduler (B6), Langfuse tracing (B7), central `agent_logs` store with local-JSONL fallback.
- Phase C: predictive ROAS (C2) and cohort analysis (C3) are real, computed entirely from the Analyst's own data. Conversion API payload (C1), scoring feedback (C4), and A/B test conclusions (C5) are built and fully tested, but run against simulated data standing in for tables that don't exist yet in colleagues' repos -- see Known limitations. The eval job (C6) covers only the Analyst's own weekly LLM summary (1/7 agents); the other 6 need their own Langfuse instrumentation first, same blocker as B7's eval-job gap.

## Running the agent

```powershell
python -m uvicorn agents.analyst.main:app --reload
```

Swagger/OpenAPI docs are then live at `http://localhost:8000/docs`. Routes:

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/health` | Service identity |
| POST | `/observe` | Observation-binome guardrail check for another agent's task |
| GET | `/report` | The 9 canonical KPIs, live where reachable, with week-on-week deltas |
| GET | `/attribution?group_by=campaign\|ad_set\|creative_asset` | CPL/CPQ/CPQL breakdown (B2), always simulated |
| GET | `/landing-pages` | Visitor-to-form conversion per page, flagged below 15% (B3) |
| GET | `/alerts` | Conversion-drop alerts above the threshold and volume floor (B5/ANA-03) |
| GET | `/weekly-report` | The weekly optimisation report as text (B6), read-only -- never snapshots KPIs or sends anything, unlike the real Monday job |
| GET | `/status` | Live reachability of CRM Keeper/Media Buyer, LLM/Langfuse configuration |
| GET | `/predictive-roas?days=30` | Projected closed-won revenue range over the next N days (C2) |
| GET | `/cohorts?group_by=campaign\|week` | Lead quality and closed-won rate by cohort (C3) |
| GET | `/conversion-api-payload` | Preview of the weekly Conversion API payload, always `dry_run=true` (C1) |
| GET | `/scoring-feedback` | Scoring-dimension recalibration proposals, never auto-applied (C4) |
| GET | `/ab-tests` | A/B test winner conclusions per variant group (C5) |

## Running the Telegram bot

Set `TELEGRAM_BOT_TOKEN` in `.env`, then run:

```powershell
python -m agents.analyst.telegram_bot
```

Starting the bot also starts three background jobs, sending to `TELEGRAM_ALLOWED_CHAT_ID` if set: the weekly optimisation report (every Monday 08:00, also snapshots this week's KPIs for next week's delta and runs the C6 eval job on its AI summary), an anomaly watch (every 6 hours, silent unless a conversion-drop alert actually fires), and the Conversion API payload job (every Monday 08:05, log-only -- nothing sent to Telegram).

All Telegram-facing reports (`/report`, `/weekly_report`, `/alerts`, `/optimisation_report`, `/health`) are in French, with a boxed layout (`┌/├/└`) and emoji flags (`⬆️/⬇️/➡️` for week-on-week deltas, `⚠️ [périmé]` for stale data, `(simulé)` for simulated KPIs) so a non-technical operator can read them unaided. Every KPI acronym is spelled out next to its value (e.g. `CPQL (coût par vente qualifiée)`).

Commands:

```text
/start
/help
/health
/report
/weekly_report
/alerts
/optimisation_report
/predictive_roas
/cohorts
/conversion_api
/scoring_feedback
/ab_tests
/observe media_buyer
/observe media_buyer pause_ad_set conversions=6 dry_run=true
```

## Running tests

```powershell
python -m pytest
```

Tests always run against an in-memory SQLite database (see `tests/conftest.py`), never a real Postgres server.

## Known limitations

- The central log store was validated against a real local PostgreSQL 17 instance on 2026-08-01 (schema creation + 6 simulated agent logs, zero write failures). The automated test suite still runs against in-memory SQLite for speed and CI independence.
- **Conversion API payload (C1) is built and logged, but never sent.** Media Buyer's real `/capi/push-conversion` endpoint keys by `email`+`pixel_id`, not `click_id` (verified against its actual code). Our seed data has neither, and click IDs aren't captured anywhere real yet (ANA-01 was never built -- see the B2 limitation above). `agents/analyst/conversion_api.py` builds and logs the exact payload the ticket describes, but does not call Media Buyer's real endpoint with a shape it doesn't accept.
- **Scoring feedback (C4) and A/B test conclusions (C5) run against simulated data.** The Qualifier's real `scoring_runs` table (QUA-01) and Content Strategist's real `content_assets` table (CCS-03) don't exist in their repos yet, so `agents/analyst/seed_data.py` stands in for both with a deliberately miscalibrated dimension and three deliberately-scenario'd A/B variant pairs. Both modules' logic is data-shape-agnostic -- point them at the real tables once QUA-01/CCS-03 exist and they work unchanged.
- **The eval job (C6) covers only the Analyst's own weekly LLM summary, 1/7 agents.** The other 6 need their own Langfuse-instrumented LLM calls first -- same blocker as B7's "weekly eval jobs for Qualifier/Content Strategist" gap.
- **ROAS and B2 attribution cannot be derived from live data and stay on the seed dataset**, marked `(simulated)` in every report. Verified directly against CRM Keeper's and Media Buyer's actual code: CRM Keeper's `LeadResponse` has no deal/contract-value field of any kind, and Media Buyer's `/performance/last-7-days` is a single account-level aggregate (spend/impressions/clicks/leads), never broken down by campaign, ad set, or creative asset. This needs a schema change on their side, not something this repo can work around.
- **Content Strategist notification is best-effort and cannot correlate a page.** Its `/cro-analysis` endpoint accepts only `{"conversion_rate": float}` — no page identifier, no `client_id` (verified against its actual code). The Analyst still calls it per flagged page and logs the generic advice it returns, but Content Strategist itself has no way to know which page the number belongs to. Needs a `page_id`/`client_id` field added to their `LandingPagePerformance` model to become a real integration.
- **The weekly optimisation report is not delivered to a real Commander.** Commander's `POST /event` routes an event *to* another agent (`target_agent` must be a key in its own agent registry) — it isn't designed to *receive* a report addressed to itself, and `POST /text` runs input through its LLM intent classifier and operator memory, which doesn't fit a structured report either (verified against its actual `api.py`/`core/agent.py`). The report keeps going to Telegram, explicitly labeled "for Commander review", until Commander exposes an intake endpoint suited for this.
- The weekly optimisation report's "scale"/"pause" recommendations are based on CPQL only; richer criteria (statistical confidence, minimum conversions) are Phase C (MB-03-equivalent) work.
- Without an API key set for the active `LLM_MODEL` provider (`DEEPSEEK_API_KEY` by default), the weekly report's plain-language summary shows "indisponible" instead of generated text — this is a clean no-op, not an error.

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
