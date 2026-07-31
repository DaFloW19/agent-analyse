# Analyst Agent Build + Agent Hardening — Work Plan

**For:** Dev A and Dev B **Deadline:** Sunday **August 10**. Absolute limit: **August 12** (buffer for fixes only, no new work). **Scope:** Build the Analyst agent from zero to Phase C, and close 21 hardening gaps across the 6 existing agents.

---

## 1. Where the project stands

The 6 existing agents (Commander, CRM Keeper, Qualifier, Content & Conversion Strategist, Media Buyer, Closer) are at Phase C. The Analyst does not exist. None of the 21 hardening items has been implemented.

We are still in **MVP development**. There is no live client, no real ad spend, no real leads. Everything is built and tested in the dev environment against seeded data with all external writes in dry-run. Nothing you build will touch a real ad account or a real phone number.

**When this is done:** all 7 agents at Phase C, every guardrail working and logged, one deployment running on the VPS, ready for the pitching stage.

---

## 2. Ground rules

**Repo**

- One shared repo. Both of you work in it. No second repo, no forks.
- One branch per ticket, named after the ticket: `feat/ANA-02-metrics-module`, `feat/CLO-01-whatsapp-window`.
- One pull request per ticket. Never commit directly to `main`.
- Do not refactor code outside your ticket. If you find something broken elsewhere, open an issue and keep moving.

**Who approves your PR**

- Tickets on the **6 existing agents**: the agent's original developer (on the project since April) reviews and approves before merge. One agent = one reviewer. Ping them when the PR is ready.
- Tickets on the **Analyst**: you two own it outright. Dev A approves Dev B's Analyst PRs and vice versa. No external sign-off.
- Exception: **ANA-01** touches the Qualifier's intake path. That specific change needs the Qualifier's original dev to approve.

**Deployment**

- You each have your own VPS account, but there is **only one deployment**. **Dev A is the deploy owner.** Dev B never deploys.
- One process stack, one `.env`, one Postgres, one Langfuse project. If you find yourself creating a second instance of anything, stop and ask.
- Deploy happens at the gates in section 4 — not continuously, not per merge.

**Every ticket ships with**

- Code + tests in `tests/`.
- README updated if behaviour changed.
- CHANGELOG entry in plain English: what was built, what was validated.
- Google-style docstrings on new functions.
- Every new action logged in the mandatory format (section 3.1).

**When you are blocked**

- Blocked more than 2 hours on an existing agent → contact that agent's original dev.
- Scope question, or something that looks like it needs a decision instead of a fix → studio lead.
- Do not silently change a spec to unblock yourself.

---

## 3. Reference rules you must follow

### 3.1 Mandatory log format (every agent, every action)

```json
{
  "agent_name": "string",
  "action_type": "string",
  "input_summary": "string",
  "output_summary": "string",
  "lead_id": "string or null",
  "client_id": "string",
  "model_used": "string",
  "latency_ms": 0,
  "timestamp": "ISO 8601"
}
```

Phase C behaviour: write to the central Postgres store **and** emit as a Langfuse event inside the active trace.

### 3.2 The 9 KPIs — use these definitions exactly, do not reinterpret

| KPI                   | Definition                                                              |
| --------------------- | ----------------------------------------------------------------------- |
| CPL                   | Total ad spend / total form submissions (all leads, any quality)        |
| CPQ                   | Total ad spend / leads with score ≥ 31                                  |
| CPQL                  | Total ad spend / leads with score ≥ 61                                  |
| CPBD                  | Total ad spend / appointments successfully booked                       |
| ROAS                  | Total contract value of `closed_won` deals / total ad spend             |
| Stage conversion rate | % of leads moving from one pipeline stage to the next, per transition   |
| Time to first contact | Avg minutes from form submission to Closer's first message (target < 5) |
| Response rate         | % of first-contact messages replied to within 48h                       |
| Meeting show rate     | % of booked meetings where the lead showed up                           |

Every one of these is implemented **once**, in `common/metrics.py` (ANA-02). Nobody re-implements a KPI anywhere else.

### 3.3 Dev environment rules

- No real data. Work against the seeded dataset (SETUP-03).
- All ad platform writes go through Media Buyer's guarded path with `dry_run=true` and `writes_enabled=false`.
- WhatsApp sends are mocked at the 360dialog client layer. Build the mechanism, not the live integration.
- Anything that would spend money, message a person, or write to a production CRM must be simulated and logged, never sent.

---

## 4. Sequence and gates

Three things block everything else. Do them first, in this order:

1. **SETUP-01 lead schema migration** — adds the fields used by almost every ticket below. Nothing schema-dependent starts until this is merged.
2. **SETUP-02 Dynaconf layered config** — CMD-02, CCS-02, MB-01, CLO-02 and ANA-03 all read from it.
3. **ANA-02 metrics module** — MB-03, CCS-03 and ANA-03 import from it. Build it before those three.

| Gate   | Date       | Must be true                                                                                                                                                                      |
| ------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **G1** | Fri Aug 1  | SETUP-01/02/03 merged. ANA-02 merged and passing its fixture. Analyst Phase B done: log audit complete, central log store ingesting from all 6 agents. First VPS deploy by Dev A. |
| **G2** | Tue Aug 5  | Analyst Phase B complete and reporting. Roughly half the hardening tickets merged and signed off.                                                                                 |
| **G3** | Fri Aug 8  | All 21 hardening tickets merged and signed off. Analyst Phase C code-complete.                                                                                                    |
| **G4** | Sun Aug 10 | Single VPS deployment updated and running. Full end-to-end run on seeded data passes. All READMEs and CHANGELOGs current.                                                         |
| Buffer | Aug 11–12  | Fixes to problems found in the Aug 10 run only. No new scope.                                                                                                                     |

---

## 5. Ownership split

| Dev A                                                           | Dev B                                                                |
| --------------------------------------------------------------- | -------------------------------------------------------------------- |
| SETUP-01 schema migration                                       | SETUP-03 seed dataset                                                |
| SETUP-02 Dynaconf config                                        | ANA-03 anomaly floor + freshness                                     |
| ANA-01 click IDs and UTMs                                       | Analyst Phase B — reporting, alerts, Langfuse                        |
| ANA-02 metrics module                                           | Analyst Phase C — Qualifier calibration, A/B conclusions, eval suite |
| Analyst Phase B — log audit + log store                         | Qualifier: QUA-01, QUA-02, QUA-03                                    |
| Analyst Phase B — data pull, attribution, landing pages         | Content Strategist: CCS-01, CCS-02, CCS-03                           |
| Analyst Phase C — Conversion API push, predictive ROAS, cohorts | Closer: CLO-01, CLO-02, CLO-03                                       |
| Commander: CMD-01, CMD-02, CMD-03                               |                                                                      |
| CRM Keeper: CRM-01, CRM-02, CRM-03                              |                                                                      |
| Media Buyer: MB-01, MB-02, MB-03                                |                                                                      |
| **Deployment owner**                                            |                                                                      |

Rule of thumb: Dev A owns the data plane and the write guardrails. Dev B owns the intelligence layer and the outbound guardrails. You each own whole agents so each agent has exactly one reviewer relationship.

---

## 6. Setup tickets

### SETUP-01 — Lead schema migration (Dev A, 5–6h)

**Build.** One migration adding every field the tickets below need: `consent_source`, `consent_at`, `do_not_contact`, `version`, `handoff_state`, `last_inbound_at`, `scoring_model_version`, `click_id`, `click_id_platform`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `data_as_of`.
New tables (empty, populated by their own tickets): `processed_events`, `failed_events`, `lead_events`, `scoring_runs`, `content_assets`, `ad_changes`, `agent_logs`.

**Test.** Migration runs clean on an empty DB and on a copy of the current dev DB. Rollback script tested. Existing agents still boot.

---

### SETUP-02 — Dynaconf layered config (Dev A, 4–5h)

**Build.** Three layers: global → industry (real_estate, ecommerce, healthcare) → client. Client overrides industry, industry overrides global. One loader, `config/`, `.env` for secrets only. Document every key in `.env.example` with a comment.

**Test.** Set a value at all three levels → client wins. Remove client level → industry wins. Missing required key → startup fails with the key name in the error, not a stack trace.

---

### SETUP-03 — Seed dataset (Dev B, 5–6h)

**Build.** A generator producing a realistic dev dataset for one fictional real-estate client: ~400 leads across all pipeline stages, spread over 8 weeks, with scores, stage transitions, message history, bookings, show/no-show, `closed_won` values, ad spend rows, and attribution params. Deterministic — same seed produces the same data. One command to reset and reload.

**Test.** Reload twice → identical data. Every KPI in section 3.2 is computable from it and returns a non-null number. Includes deliberate edge cases: leads with no attribution, a zero-spend day, a stage with zero conversions.

---

## 7. The Analyst — full build

**Role.** The Analyst is the only agent that looks backward. Every other agent acts in the present; the Analyst studies what happened and tells the team what to do differently. It tracks every metric that matters and sends optimisation signals back to Commander, Media Buyer and Content Strategist. It is also the primary Langfuse user — observation is its whole purpose.

**Stack.** LangChain · FastAPI · LiteLLM · Dynaconf · Langfuse · APScheduler · Postgres · CRM adapter · Ad platform adapters.

**What the Analyst does NOT do.** It never changes a budget, never sends a message, never edits a lead. It computes, reports, and recommends. Execution belongs to the other agents, through the Commander.

---

### 7.1 Phase B — audit and log store (Dev A, 8h)

The Analyst has no active logic in Phase B. Its job is making sure everything else is measurable.

**Build.**

1. Audit all 6 agents' log output against the format in 3.1. Produce `docs/LOG_AUDIT.md`: a table of agent × field × pass/fail.
2. Any agent missing a field: raise it with that agent's original dev, then fix it under their sign-off.
3. `common/logging.py` with a single `log_action(**fields)` used by every agent. No agent formats its own log line.
4. Central store: `agent_logs` table matching the schema exactly. Indexes on `(client_id, agent_name, timestamp)` and `(lead_id, timestamp)`.
5. Local append-only JSON file per agent kept as backup.

**Test.** Trigger one action per agent → 6 rows in `agent_logs`, all 9 fields populated, no nulls where nulls are not allowed. Kill the DB → agents keep running and keep writing the local file, no crash.

---

### 7.2 ANA-01 — Capture click IDs and UTMs at intake (Dev A, 4–5h)

**Why.** Without click IDs, every per-campaign number is inferred rather than measured, and the Phase C Conversion API push cannot match a deal back to a click.

**Build.**

- Hidden form fields populated from the query string on load (Typeform supports this natively).
- Landing pages must propagate query params — audit every existing page, fix any that drop them.
- Qualifier's Pydantic model: missing params are acceptable. Log at info level when a lead arrives unattributed and track the rate.
- Set `click_id_platform` from whichever param is present. If both `fbclid` and `gclid` are present, prefer `gclid`.
- Store the click ID **exactly as received**. No trimming, no normalisation — Conversion API matching is exact.
- Add `get_leads_by_attribution(client_id, group_by, date_range)` to the CRM Keeper for the Analyst to call.

**Test.** Simulated click with `fbclid` → lead carries it byte-identical plus all UTMs. Navigate a landing page with params → form → confirm they survive. No params → lead created, nulls logged at info level.

**Note.** This touches the Qualifier's intake path — the Qualifier's original dev approves this PR.

---

### 7.3 ANA-02 — One canonical metrics module (Dev A, 6–7h)

**Why.** Nine KPIs defined in prose get implemented three times — Analyst, Console API, dashboard — and produce three different numbers. Two screens disagreeing in front of a client kills every number in the system.

**Build.**

- `common/metrics.py`. **Pure functions only** — no DB calls, no API calls, no I/O. Data goes in as arguments.
- All nine KPIs from section 3.2.
- Shared helpers: two-proportion z-test, confidence interval on a rate.
- Every function returns `{value, numerator, denominator, data_as_of}` — always show the working.
- `tests/fixtures/metrics_fixture.json`: a small dataset with every expected KPI value computed **by hand** and written down.
- Resolve and document these ambiguities in the module docstring: which timezone defines a "day", a re-scored lead counts once, whether spend includes platform fees, divide-by-zero returns `None`.
- The Console API team imports this module. No reimplementation anywhere.

**Test.** Fixture suite → all nine match the hand-computed values. Divide-by-zero returns `None` and renders as "no data", never as "0".

---

### 7.4 Phase B — reporting, alerts, Langfuse

#### B1 — Data pull layer (Dev A, 5h)

Read from `agent_logs` and the CRM Keeper, shape the data, pass it to `metrics.py`. No KPI arithmetic lives here. **Test.** All nine KPIs computed from seeded data match a direct call to the metrics module with the same inputs.

#### B2 — Attribution breakdown (Dev A, 5h)

Break CPL, CPQ and CPQL down by campaign, ad set and creative asset. Identify the top and bottom performer at each level. Group by the fields from ANA-01 and by `asset_id` from CCS-03. **Test.** Seeded data with a deliberately bad ad set → it is named as bottom performer. Unattributed leads appear in an explicit "unattributed" bucket, never silently dropped.

#### B3 — Landing page performance (Dev A, 4h)

Conversion rate per landing page. Flag any page below 15% visitor-to-form to the Content Strategist. **Test.** Seeded page at 9% → flagged. Page at 22% → not flagged.

#### B4 — Report command (Dev B, 5h)

Operator sends `report` (Telegram and Console) → formatted KPI summary with current values and week-on-week change. Every figure carries its `data_as_of` stamp. **Test.** `report` returns all nine KPIs with deltas. A KPI with no data shows "no data", not 0.

#### B5 — Anomaly detection (Dev B, 4h)

Immediate alert when a stage conversion rate drops more than the configured threshold. Subject to the ANA-03 volume floor — build them together. **Test.** Inject a real drop above the floor → alert fires. Injected noise below the floor → no alert.

#### B6 — Weekly optimisation report (Dev B, 6h)

Generated every Monday via APScheduler. Specific recommended actions only: scale campaign X, pause ad set Y, rewrite asset Z. Each recommendation carries the numbers that justify it. Sent to the Commander — the Analyst never executes. **Test.** Run the job against seeded data → report contains at least one recommendation per category, each with its supporting figures. Confirm nothing was executed as a side effect.

#### B7 — Langfuse integration (Dev B, 6h)

Wrap every Analyst LLM call: `trace()` at agent level, `generation()` per call. Required metadata on every trace: `agent_name`, `client_id`, `lead_id`, `phase`, `model_used`. Set up weekly eval jobs for Qualifier accuracy and Content Strategist output quality. **Test.** Run a report → complete trace visible in Langfuse with all metadata present and cost recorded. Eval job runs on schedule and writes a score.

---

### 7.5 ANA-03 — Anomaly volume floor and data freshness (Dev B, 4–5h)

**Why.** An alert that fires on ordinary variance (6 leads down to 3 is just a Tuesday) gets switched off, and then it is not there when something real happens. Stale numbers are worse than no numbers.

**Build.**

- Config: `anomaly_min_denominator` (20), `anomaly_threshold_pct` (50).
- An alert requires **both**: drop greater than the threshold **and** both periods at or above the denominator. Below the floor, no alert — log the suppression with the counts.
- Low volume → widen the window (7d → 14d). Never lower the floor.
- Alert text shows the working: "SQL conversion 12% → 5%, based on 34 and 41 leads, 14-day windows."
- Every source reports `data_as_of`. The metrics module propagates the **oldest** contributing source to any composite figure.
- Mark any figure stale if its source is more than 6h old.
- A source entirely unavailable → the report says so. Never compute a partial number and present it as complete.

**Test.** 6 → 3 leads: no alert, suppression logged with counts. 40 → 18 leads: alert with context. Stale ads data: affected figures marked. Ads source unavailable: report states it.

---

### 7.6 Phase C — feedback loop and prediction

#### C1 — Conversion API push (Dev A, 6h)

Weekly job: compile all `closed_won` deals with their click IDs and instruct the Media Buyer to push them to Meta and Google via Conversion API. The Analyst produces the payload; the Media Buyer executes it through its guarded path (MB-01), which in dev means `dry_run=true`. **Test.** Weekly job on seeded data → correct payload built, click IDs byte-identical to stored values, full API call logged, nothing sent. Deal with no click ID → excluded and counted in the log.

#### C2 — Predictive ROAS (Dev A, 7h)

From current pipeline volume per stage and historical stage-to-stage conversion rates, project expected revenue for the next 30 days. Output a range, not a single number, and state the assumptions used. **Test.** Run against a seeded snapshot where the outcome is known → projection lands within the stated range. Thin pipeline → returns "insufficient data" instead of a number.

#### C3 — Cohort analysis (Dev A, 7h)

Track lead quality by acquisition date, campaign and audience segment. Identify which sources produce the best long-term outcomes. **Test.** Seeded data with one deliberately strong cohort → it is identified as best-performing. Cohorts below the ANA-03 volume floor are reported as insufficient, not ranked.

#### C4 — Scoring model feedback to Qualifier (Dev B, 7h)

Compare the Qualifier's SQL predictions against actual closed deals using `scoring_runs` (QUA-01). Produce calibration signals for dimension weights. **Write them as proposals to a calibration table — never auto-apply.** Every proposal is logged with the evidence behind it. **Test.** Seeded data where one dimension is systematically over-weighted → proposal names that dimension with its evidence. Confirm no live weight changed.

#### C5 — A/B test conclusions (Dev B, 5h)

When a Content Strategist test reaches significance, flag the winner and instruct the Strategist to deprecate the loser. Use the z-test helper from `metrics.py` — 95% confidence, minimum 30 conversions per variant. Below that: "insufficient data", no winner. **Test.** 40 conversions with a real difference → winner declared with p-value. 40 conversions marginal → no winner, interval shown. 20 conversions → insufficient data.

#### C6 — Full Langfuse eval suite (Dev B, 6h)

Active eval jobs for all 7 agents. Analyst reviews results weekly and surfaces issues to the Commander. **Test.** All 7 agents appear in Langfuse with active eval jobs and at least one scored run each.

---

## 8. Hardening — the 21 items

Full detail for each item is in `AGENT_HARDENING_BRIEF_SIMPLIFIED.md`. Below is what to build and how it is verified. If the two documents ever disagree, the hardening brief wins.

### Commander — Dev A

**CMD-01 — Idempotency and signature verification on `POST /event` (4–5h)** Webhook retries currently create duplicate leads, and the endpoint accepts anything.
Build: `common/webhook_auth.py` with per-provider HMAC-SHA256 (Meta, 360dialog, Typeform). `processed_events` table, deduplicate on arrival, 24h TTL cleanup job. Bad signature → 401 + log + reject. Duplicate → 200 + log + return the original result.
Test: replay an identical payload 3× → 1 lead created, 2 logged as duplicates, all 200.

**CMD-02 — Autonomy policy engine (6–8h)** The UX spec defines auto / approve-first / suggest-only tiers; nothing enforces them.
Build: action class enum (`crm_write`, `send_message`, `spend_change`, `campaign_state_change`, `content_publish`, `segment_sync`). Per-client tier config. One dispatch function `commander.dispatch(action_class, payload, reason)` that everything routes through. `approve_first` → pending-actions table, expires if unapproved, never auto-executes. Log every tier check and its decision.
Test: `spend_change` set to approve_first → change queued, not sent. Flip to auto → dispatches. Set suggest_only and approve manually → still does not execute.

**CMD-03 — Dead-letter store and replay (4–5h)** Failed events are retried twice then vanish with no record.
Build: `failed_events` table (`event_id, provider, raw_payload, target_agent, error_type, error_message, attempt_count, first_failed_at, status ∈ {pending, replayed, abandoned}`). Write after the 2nd retry failure + alert. Operator commands: `failed`, `replay <event_id>`, `replay --agent <name>`. Auto-abandon after 5 failed replays.
Test: stop the Qualifier, submit 3 forms → 3 rows. Restart, `replay --agent qualifier` → 3 leads, no duplicates.

### CRM Keeper — Dev A

**CRM-01 — Consent and do-not-contact (3–4h)** Build: `consent_source` ('form_submission' | 'whatsapp_inbound' | 'manual_import'), `consent_at`, `do_not_contact`. Null consent source → lead creation fails. `check_contactable(lead_id) → (bool, reason)`. Any update that would trigger outreach on a flagged lead → 409, blocked, logged. Setting `do_not_contact` is irreversible via the agent API.
Test: create a lead without `consent_source` → rejected, error names the field. Set `do_not_contact`, attempt a send → blocked and logged.

**CRM-02 — Append-only lead_events timeline (5–6h)** Build: `lead_events` (`event_id, lead_id, client_id, actor_agent, event_type, from_value, to_value, reason, timestamp`). Types: `stage_change`, `score_assigned`, `message_sent`, `consent_changed`, `field_updated`, `action_blocked`, `handoff`. One helper `crm_keeper.append_event(...)` called from every state change. Enforce append-only at DB level (revoke UPDATE/DELETE). Index `(lead_id, timestamp)` and `(client_id, event_type, timestamp)`.
Test: run a lead through create → score → stage → send; timeline returns 4 events in order.

**CRM-03 — Optimistic concurrency on lead writes (4–5h)** Build: `version` integer, default 1. `update_lead(lead_id, expected_version, fields)` → `WHERE lead_id = ? AND version = ?`, increment on success. Mismatch → 409 with current version and changed fields. Caller retries via Tenacity, exponential backoff, max 3. After 3 failures, escalate to Commander.
Test: concurrent updates to the same lead → one succeeds, one gets 409, retry succeeds with both changes present.

### Media Buyer — Dev A

**MB-01 — Spend guardrails and dry-run mode (5–6h)** Build: config `max_budget_change_pct` (20), `max_daily_spend` (500), `max_monthly_spend` (10000), `max_bid_change_pct` (15), `max_actions_per_day` (10), `dry_run` (true), `writes_enabled` (false). Every write goes through `media_buyer.execute_change(change)`: kill switch → dry-run → specific limits → execute. `dry_run=true` logs the exact API call and returns simulated success so the rest of the pipeline behaves identically. `max_actions_per_day` breach trips a circuit breaker requiring manual reset.
Test: `writes_enabled=false` → every write blocked. `dry_run=true` → full payload logged, nothing sent. 40% change against a 20% cap → rejected, limit named. 11 actions in a day → breaker fires, 12th blocked.

**MB-02 — Change ledger with rollback (5–6h)** Build: `ad_changes` table (`change_id, client_id, platform, entity_type, entity_id, field, before_value, after_value, reason, triggered_by, decision_data JSONB, executed_at, rolled_back_at, dry_run`). Row written **before** the API call, pending status. `reason` is mandatory and human-readable ("CPL 2.3× for 3 days, 47 conversions"). `rollback <change_id>` re-applies the before value through the guarded path and gets its own ledger row. `rollback --since <timestamp>` reverses in reverse-chronological order, stopping on first error.
Test: make a change → ledger row with before/after. Roll back → value restored, linked row created. `rollback --since` across three changes → all three reversed and linked.

**MB-03 — Statistical floor before pause or bid change (5–6h)** Build: config `min_conversions_for_action` (15), `confidence_level` (0.95). Below the floor → alert instead of acting, log the decision. At or above → compute the confidence interval on CPL vs target using the `metrics.py` helper; act only if the interval excludes the target. Extend the window (3d → 7d → 14d) rather than acting on thin data, and log which window was used.
Test: 6 conversions at 3× target → no pause, alert names the volume reason. 40 conversions at 3× target → pause executes. 40 conversions at 1.2× target with wide variance → no action, log shows the interval includes the target.

### Qualifier — Dev B

**QUA-01 — Stamp scoring provenance (3–4h)** Build: `scoring_model_version` (semver, bumped manually on any weight or rubric change) and a `scoring_runs` table (`run_id, lead_id, scoring_model_version, weights_used JSONB, thresholds_used JSONB, model_id, prompt_version, dimension_scores JSONB, total_score, classification, created_at`). Store the **actual weights**, not a pointer to config. Emit a `score_assigned` event to `lead_events` with the run_id.
Test: score a lead → row created. Change a weight, bump the version, re-score → second row, both retrievable, the first unchanged.

**QUA-02 — Confidence bands and boundary routing (5–6h)** Build: Instructor response model returns confidence ∈ {low, medium, high} per LLM-scored dimension. Lead confidence = the minimum dimension confidence. If `abs(score - threshold) <= boundary_margin` **and** confidence is low → classification `needs_review`, routed to the Attention Queue. Human resolution writes a `field_updated` event with a reason.
Test: ambiguous lead near 61 → `needs_review`, appears in the queue, Closer sends nothing. Clear strong lead → auto SQL.

**QUA-03 — Golden-set regression fixture (6–7h)** Build: `tests/fixtures/golden_leads_{real_estate,ecommerce,healthcare}.json`, 20 hand-labelled leads each with expected score band and classification. One Langfuse dataset per industry. Assertions: accuracy ≥ 80%, MAE ≤ 12 points, both in config with a comment explaining the number. Non-blocking in CI initially, blocking after 2 green runs.
Test: run the suite → accuracy and MAE reported per industry. Corrupt a weight → suite fails and names which leads moved.

### Content & Conversion Strategist — Dev B

**CCS-01 — Instructor-enforced output contract (3–4h)** Build: Pydantic response model — `headline: str = Field(max_length=40)`, `primary_text: str = Field(max_length=125)`, `cta: Literal[...]` from the approved list. Wrap generation with Instructor, `max_retries=3`. Character counting must match the platform's (Meta counts whitespace and emoji). Three exhausted retries → escalate to Commander with the last invalid output.
Test: generate 10 variants → all within limits, verified by assertion. Force an overshoot → retries visible in logs, escalation after the third.

**CCS-02 — Deterministic compliance lint (4–5h)** Build: `config/compliance/{real_estate,ecommerce,healthcare}.yaml` with `banned_phrases` (exact + regex), `required_disclaimers`, `banned_claim_patterns`. Pure functions in `content_strategist/compliance.py`, string matching only — no LLM reviewing an LLM. Return `{severity: 'block' | 'warn', rule_id, matched_text, position}`. Any block stops the output. Log every block with its rule_id.
Test: healthcare copy with a banned claim → blocked, rule_id in the log. Real estate copy → passes, proving the rules are industry-scoped.

**CCS-03 — Asset registry and A/B stopping rule (6–7h)** Build: `content_assets` table (`asset_id UUID, client_id, asset_type, variant_group_id, content JSONB, version, status, compliance_findings JSONB, created_at, model_id`). The asset_id travels with the asset — into the Media Buyer ad name, into Analyst grouping. Import the winner test from `metrics.py`, do not reimplement it. Winner requires 95% confidence **and** ≥ 30 conversions per variant; below that, "insufficient data". Fix both source documents so they agree on this rule.
Test: create a variant pair → both get IDs, IDs reach the ad platform payload. 40 conversions with a real difference → winner with p-value. 40 conversions marginal → no winner, interval shown.

### Closer — Dev B

**CLO-01 — WhatsApp 24-hour session window (6–7h)** Outside 24h from the customer's last inbound message, WhatsApp only permits pre-approved templates. Free-form sends are rejected, and repeat violations can get the number banned.
Build: `last_inbound_at` updated on every inbound webhook. `closer.window_state(lead) → 'open' | 'closed'`. Map every template in the library to an approved WhatsApp template name or `"free_form_only"`. Window closed with no approved template → refuse, log the rule_id, raise to operator. Approved templates have fixed variable slots — validate all required variables before sending.
Test: inbound 2h ago → free-form send succeeds. 30h ago with an objection handler that has no approved template → refused and logged. Same lead with an approved first-contact template → sends. Missing variable → blocked before the API call.
Note: the studio lead handles actual template submission to Meta. Your job is the mechanism and the mapping.

**CLO-02 — Opt-out, quiet hours, rate cap (6–7h)** Build: opt-out keywords in English, French and Arabic in config. On match: set `do_not_contact=True`, send one confirmation if the window allows, cancel sequences, notify operator. Quiet hours per client timezone (default 21:00–08:00) in the lead's local time — defer, do not drop. Rate cap: max 4 outbound per lead per rolling 7 days across all channels. One gate for everything: `closer.can_send(lead, channel) → (bool, reason)` running all checks including `do_not_contact` and handoff. No bypass paths. Every block writes an `action_blocked` event.
Test: reply "STOP" → flag set, sequences cancelled, nothing further sent, event recorded. "توقف" → same. Send scheduled at 02:00 lead-local → deferred to 08:00. 5 messages in a week → the 5th deferred, operator alerted.

**CLO-03 — Human-handoff lock (4–5h)** Build: `handoff_state` ∈ {none, pending, human_owned}. Transitions to pending on QUA-02 `needs_review`, CMD-02 `approve_first`, 3 send failures, or operator command. `pending` blocks sends; `human_owned` blocks sends and pauses sequences with position preserved. Release is explicit, human-only, with a reason — sequences resume from the stored position, never restart. `closer.can_send` checks handoff first. Surface the state on the Attention Queue and Lead 360.
Test: escalate a lead mid-sequence → sequence pauses, position preserved, next message blocked. Release with reason → resumes at step 3, not step 1.

---

## 9. Cross-cutting cleanup (whoever finishes first, before G4)

| #    | Fix                                                                                                        |
| ---- | ---------------------------------------------------------------------------------------------------------- |
| X-01 | Roadmap says "six agents" then lists seven — correct to seven                                              |
| X-02 | Broken list numbering (8–12, restart, 13+)                                                                 |
| X-03 | Expired MVP deadline of 30 June — escalate to studio lead, do not re-date it yourselves                    |
| X-04 | Model stack drift between roadmap and dev mapping — resolved by LiteLLM routing, update the docs to say so |
| X-05 | Filename says v3, header says Version 2.0 — align                                                          |
| X-06 | A/B stopping rule contradiction (impressions vs conversions) — resolved by CCS-03; fix both documents      |

---

## 10. Definition of done — August 10

Tick every line before saying it is finished.

- [ ] All 21 hardening tickets merged, each approved by that agent's original dev.
- [ ] Analyst at Phase C: Phase B audit done, all 7 Phase B features working, all 6 Phase C features working.
- [ ] `common/metrics.py` is the only place any KPI is calculated. Fixture suite green.
- [ ] All 7 agents write to `agent_logs` in the mandatory format, and emit Langfuse events.
- [ ] Langfuse shows active eval jobs for all 7 agents.
- [ ] End-to-end run on seeded data: lead enters → scored → contacted → booked → appears correctly in the weekly report, with every guardrail observably firing where it should.
- [ ] Every guardrail block is visible in the logs with its rule_id or reason.
- [ ] One deployment on the VPS, deployed by Dev A. No second instance of anything.
- [ ] README, CHANGELOG and `.env.example` current for every agent.
- [ ] `docs/LOG_AUDIT.md` present and passing.

---

## 11. If you take one thing from this document

Build the three blockers first — schema, config, metrics module — or everything after them gets built twice. Never compute a KPI outside `common/metrics.py`. Never let an agent bypass its guardrail function. And when something blocks you for more than two hours, ask instead of improvising.
