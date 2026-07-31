"""Hardcoded Phase A data for the Analyst report endpoint."""

SPEND_ROWS = [
    {"spend": 100, "data_as_of": "2026-07-29T09:00:00Z"},
    {"spend": 200, "data_as_of": "2026-07-29T08:00:00Z"},
]

LEAD_ROWS = [
    {"lead_id": "lead-001", "score": 20, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-002", "score": 31, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-003", "score": 61, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-004", "score": 80, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-005", "score": None, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-006", "score": 50, "data_as_of": "2026-07-29T10:00:00Z"},
]

BOOKING_ROWS = [
    {"lead_id": "lead-002", "booked": True, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-003", "booked": True, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-004", "booked": True, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-006", "booked": False, "data_as_of": "2026-07-29T10:00:00Z"},
]

DEAL_ROWS = [
    {
        "lead_id": "lead-003",
        "status": "closed_won",
        "contract_value": 500,
        "data_as_of": "2026-07-29T10:00:00Z",
    },
    {
        "lead_id": "lead-004",
        "status": "closed_won",
        "contract_value": 400,
        "data_as_of": "2026-07-29T10:00:00Z",
    },
    {
        "lead_id": "lead-006",
        "status": "closed_lost",
        "contract_value": 1000,
        "data_as_of": "2026-07-29T10:00:00Z",
    },
]

TRANSITION_ROWS = [
    {
        "lead_id": "lead-001",
        "from_stage": "new",
        "to_stage": "disqualified",
        "data_as_of": "2026-07-29T10:00:00Z",
    },
    {
        "lead_id": "lead-002",
        "from_stage": "new",
        "to_stage": "mql",
        "data_as_of": "2026-07-29T10:00:00Z",
    },
    {
        "lead_id": "lead-003",
        "from_stage": "new",
        "to_stage": "mql",
        "data_as_of": "2026-07-29T10:00:00Z",
    },
    {
        "lead_id": "lead-004",
        "from_stage": "new",
        "to_stage": "mql",
        "data_as_of": "2026-07-29T10:00:00Z",
    },
]

CONTACT_ROWS = [
    {
        "lead_id": "lead-002",
        "submitted_at": "2026-07-28T10:00:00Z",
        "first_contact_at": "2026-07-28T10:04:00Z",
        "replied_at": "2026-07-28T11:00:00Z",
        "data_as_of": "2026-07-29T10:00:00Z",
    },
    {
        "lead_id": "lead-003",
        "submitted_at": "2026-07-28T11:00:00Z",
        "first_contact_at": "2026-07-28T11:06:00Z",
        "replied_at": "2026-07-31T11:06:00Z",
        "data_as_of": "2026-07-29T10:00:00Z",
    },
    {
        "lead_id": "lead-004",
        "submitted_at": "2026-07-28T12:00:00Z",
        "first_contact_at": "2026-07-28T12:05:00Z",
        "replied_at": "2026-07-29T12:05:00Z",
        "data_as_of": "2026-07-29T10:00:00Z",
    },
]

MEETING_ROWS = [
    {"lead_id": "lead-002", "booked": True, "showed": True, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-003", "booked": True, "showed": False, "data_as_of": "2026-07-29T10:00:00Z"},
    {"lead_id": "lead-004", "booked": True, "showed": True, "data_as_of": "2026-07-29T10:00:00Z"},
]

WEEKLY_STAGE_CONVERSION_ROWS = [
    {
        "transition": "new_to_mql",
        "label": "New to MQL",
        "previous_rate": 70.0,
        "current_rate": 30.0,
        "previous_denominator": 100,
        "current_denominator": 90,
        "data_as_of": "2026-07-29T10:00:00Z",
    },
    {
        "transition": "mql_to_sql",
        "label": "MQL to SQL",
        "previous_rate": 50.0,
        "current_rate": 35.0,
        "previous_denominator": 80,
        "current_denominator": 75,
        "data_as_of": "2026-07-29T10:00:00Z",
    },
]
