import json

import pytest

from common.logging import log_action, validate_log_entry


def test_log_action_writes_mandatory_jsonl_entry(tmp_path):
    log_path = tmp_path / "analyst.jsonl"

    entry = log_action(
        agent_name="analyst",
        action_type="observe_task",
        input_summary="media_buyer.pause_ad_set",
        output_summary="safe_to_continue=False",
        lead_id=None,
        client_id="demo-real-estate",
        model_used="rule-based",
        latency_ms=12,
        timestamp="2026-07-29T10:00:00+00:00",
        path=log_path,
    )

    written_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(written_lines) == 1
    assert json.loads(written_lines[0]) == entry
    assert entry["lead_id"] is None


def test_validate_log_entry_rejects_missing_required_field():
    with pytest.raises(ValueError, match="Missing mandatory log fields"):
        validate_log_entry({"agent_name": "analyst"})

