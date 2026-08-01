# Agent Analyse

Analyst agent for Marketing Project.

## Current Bootstrap

- `agents/analyst/`: Analyst FastAPI service skeleton.
- `common/`: shared code used by every agent.
- `config/`: layered configuration.
- `migrations/`: database migrations.
- `tests/`: automated tests.
- `docs/ANALYST_AGENT_WORK_PLAN.md`: implementation plan.
- `common/metrics.py`: canonical KPI and statistical helper module.
- `common/logging.py`: mandatory local JSONL logging helper, dual-writing to `common/db.py`'s central `agent_logs` table.
- `common/tracing.py`: no-op-safe Langfuse tracing wrapper.
- `common/llm.py`: no-op-safe DeepSeek text generation wrapper, used for the weekly report's plain-language summary. Blank `DEEPSEEK_API_KEY` = clean no-op, never a crash.
- `scripts/init_db.py`: one-shot script to provision the central log store schema (`python -m scripts.init_db`).
- `scripts/generate_test_logs.py`: simulates one action per non-Analyst agent through `log_action`, since those agents do not exist in this repo yet (`python -m scripts.generate_test_logs`). See `docs/LOG_AUDIT.md`.

## Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn agents.analyst.main:app --reload
```

Run the Phase B Telegram bot with:

```powershell
python -m agents.analyst.telegram_bot
```

## Tests

```powershell
.\.venv\Scripts\python -m pytest
```

## Phase B Logs

Analyst local logs are append-only JSONL at `logs/analyst.jsonl`. Runtime log files are ignored by Git.
