"""Phase A ticket 7.1 end-to-end test: one action per agent -> agent_logs.

The other 6 agents do not exist in this repo yet, so `scripts.generate_test_logs`
simulates one realistic action per agent through the same shared
`common.logging.log_action` every real agent must use. This test proves the
log_action -> local JSONL -> agent_logs pipeline holds for every agent_name,
matching ticket 7.1's validation: "Trigger one action per agent -> 6 rows in
agent_logs, all 9 fields populated, no nulls where nulls are not allowed."
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db import AgentLog, get_engine
from common.logging import MANDATORY_LOG_FIELDS
from scripts.generate_test_logs import SIMULATED_ACTIONS, generate_test_logs


def test_generate_test_logs_writes_one_row_per_agent(tmp_path):
    log_path = tmp_path / "simulated_agents.jsonl"

    entries = generate_test_logs(path=str(log_path))

    assert len(entries) == len(SIMULATED_ACTIONS) == 6
    simulated_agent_names = {action["agent_name"] for action in SIMULATED_ACTIONS}
    assert simulated_agent_names == {
        "commander",
        "crm_keeper",
        "qualifier",
        "content_strategist",
        "media_buyer",
        "closer",
    }

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6


def test_generate_test_logs_populates_agent_logs_with_no_unexpected_nulls(tmp_path):
    log_path = tmp_path / "simulated_agents.jsonl"
    nullable_fields = {"lead_id"}
    isolated_client_id = "test-isolated-nulls-check"

    generate_test_logs(path=str(log_path), client_id=isolated_client_id)

    with Session(get_engine()) as session:
        rows = session.scalars(
            select(AgentLog).where(AgentLog.client_id == isolated_client_id)
        ).all()

    assert len(rows) == 6
    for row in rows:
        for field in MANDATORY_LOG_FIELDS:
            value = getattr(row, field)
            if field in nullable_fields:
                continue
            assert value not in (None, ""), f"{field} must not be empty on {row.agent_name}"
