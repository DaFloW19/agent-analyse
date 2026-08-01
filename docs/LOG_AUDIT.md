# Log Audit

Phase A audit of mandatory local JSON logging.

| Agent | agent_name | action_type | input_summary | output_summary | lead_id | client_id | model_used | latency_ms | timestamp | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Commander | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | Agent not built yet; pipeline validated via `scripts/generate_test_logs.py` |
| CRM Keeper | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | Agent not built yet; pipeline validated via `scripts/generate_test_logs.py` |
| Qualifier | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | Agent not built yet; pipeline validated via `scripts/generate_test_logs.py` |
| Content Strategist | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | pass (simulated) | Agent not built yet; pipeline validated via `scripts/generate_test_logs.py` |
| Media Buyer | fail | fail | fail | fail | fail | fail | fail | fail | fail | Real code exists (separate repo) but never calls `log_action`; its one mandatory-format dict is only `print()`ed in `/ads/alert`, never persisted |
| Closer | fail | fail | fail | fail | fail | fail | fail | fail | fail | Real code exists (separate repo) but never builds or writes the mandatory format anywhere |
| Analyst | pass | pass | pass | pass | pass | pass | pass | pass | pass | Local JSONL + central `agent_logs` store implemented, real code, own agent |

## Notes

- Analyst logs are written locally to `logs/analyst.jsonl` and dual-written to the central `agent_logs` table (`common/db.py`) when the database is reachable. A database outage never blocks or crashes the agent; the failure itself is appended to the local JSONL file.
- No live Postgres server was available in this dev environment; the central store is implemented and tested against an in-memory SQLite database (`tests/conftest.py`), not yet validated against a real Postgres instance.
- **"pass (simulated)" is not the same as "pass".** Commander, CRM Keeper, Qualifier, and Content Strategist do not exist in this repo yet, so there is no real code to audit. `scripts/generate_test_logs.py` writes one realistic action per agent through the exact same `common.logging.log_action` every real agent must use, and `tests/test_multi_agent_logging.py` asserts all 6 rows land in `agent_logs` with every mandatory field populated (nulls only where `lead_id` is legitimately absent). This proves the log_action -> JSONL -> `agent_logs` pipeline is correct for any `agent_name` — it does not certify that the real agent's own code will log correctly once built. Each agent still needs its own real audit against this table when it lands.
- Media Buyer and Closer were reviewed directly from their own repos (`agent closer github/media_buyer`, `agent closer github/closer`). Neither writes to a shared, validated `log_action` — this is the actual blocker for those two, not a documentation gap.
- A second, separate "Phase A" scaffold (`agent-analyst-phaseA`) was found in a colleague's own repo, with its own `common/logger.py` (no field validation, writes only to `~/logs/` on the local machine, no DB write in the same call) and its own `audit_logs.py` (looks for logs under `../commander/logs/`, `../crm_keeper/logs/`, `../qualifier/logs/` — a path that does not match where its own `logger.py` writes). Per the work plan's ground rules ("One shared repo... No second repo, no forks"), this repo is being consolidated into this one rather than maintained in parallel. Its `generate_test_logs.py` idea (fake logs for agents that do not exist yet) is what `scripts/generate_test_logs.py` in this repo adapts, through the validated shared `log_action`.

