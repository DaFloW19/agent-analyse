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
- `common/logging.py`: mandatory local JSONL logging helper.

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
