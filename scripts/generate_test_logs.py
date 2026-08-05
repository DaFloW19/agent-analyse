"""One-shot script simulating one action per non-Analyst agent.

Usage:
    python -m scripts.generate_test_logs

The other 6 agents (Commander, CRM Keeper, Qualifier, Content Strategist,
Media Buyer, Closer) do not exist in this repo, so their real code cannot be
triggered to prove the Phase A pipeline end to end (ticket 7.1's test:
"Trigger one action per agent -> 6 rows in agent_logs, all 9 fields
populated"). This script fills that gap with one realistic, hand-written
action per agent, written through the same `common.logging.log_action` every
real agent must use -- not a second, parallel logger.

This only proves the log_action -> local JSONL -> agent_logs pipeline is
correct for any agent_name. It does NOT certify that the other agents' own
code logs correctly once it exists; each one still needs its own real audit
when it is built (see docs/LOG_AUDIT.md).
"""

from __future__ import annotations

from common.logging import log_action

CLIENT_ID = "demo-real-estate"

SIMULATED_ACTIONS = [
    {
        "agent_name": "commander",
        "action_type": "route_task",
        "input_summary": "Received 'new lead' via Telegram",
        "output_summary": "Routed to Qualifier webhook",
        "lead_id": "ld_001",
        "model_used": "rule-based",
        "latency_ms": 42,
    },
    {
        "agent_name": "crm_keeper",
        "action_type": "create_lead",
        "input_summary": "Lead data from form",
        "output_summary": "Lead created with ID ld_002",
        "lead_id": "ld_002",
        "model_used": "rule-based",
        "latency_ms": 120,
    },
    {
        "agent_name": "qualifier",
        "action_type": "score_lead",
        "input_summary": "Lead profile JSON",
        "output_summary": "Score 85 - SQL",
        "lead_id": "ld_001",
        "model_used": "deepseek-chat",
        "latency_ms": 350,
    },
    {
        "agent_name": "content_strategist",
        "action_type": "generate_ad_copy",
        "input_summary": "Client brief: real_estate, buyer_leads",
        "output_summary": "3 ad copy variants generated",
        "lead_id": None,
        "model_used": "gpt-4o",
        "latency_ms": 1800,
    },
    {
        "agent_name": "media_buyer",
        "action_type": "process_alert",
        "input_summary": "Alert 'cpl_spike' on adset_120247096711530625",
        "output_summary": "Ad set paused",
        "lead_id": None,
        "model_used": "rule-based",
        "latency_ms": 210,
    },
    {
        "agent_name": "closer",
        "action_type": "send_message",
        "input_summary": "SQL lead ld_001, template sql_step_1",
        "output_summary": "WhatsApp message sent",
        "lead_id": "ld_001",
        "model_used": "rule-based",
        "latency_ms": 95,
    },
]


def generate_test_logs(
    path: str | None = None, client_id: str = CLIENT_ID
) -> list[dict]:
    """Write one simulated log entry per non-Analyst agent.

    Args:
        path: JSONL destination path for the simulated entries. Defaults to
            `None`, which lets each entry land in its own `logs/{agent_name}.jsonl`
            (see `common.logging.log_action`) -- one history file per agent,
            same as a real agent would get. Pass an explicit path (e.g. in
            tests) to force every entry into a single shared file instead.
        client_id: Client identifier stamped on every simulated entry. Callers
            that need to isolate one run's rows in `agent_logs` (e.g. tests
            sharing a session-scoped database) should pass a unique value.

    Returns:
        list[dict]: The log entries written, in the same order as
        `SIMULATED_ACTIONS`.
    """

    return [
        log_action(client_id=client_id, path=path, **action) for action in SIMULATED_ACTIONS
    ]


def main() -> None:
    """Generate the simulated logs and report where they landed."""

    entries = generate_test_logs()
    print(f"{len(entries)} simulated logs written, one per agent under logs/, and to agent_logs.")
    for entry in entries:
        print(f"  - {entry['agent_name']}: {entry['action_type']}")


if __name__ == "__main__":
    main()
