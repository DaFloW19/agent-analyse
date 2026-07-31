from agents.analyst.landing_pages import landing_page_performance

DATA_AS_OF = "2026-07-29T10:00:00Z"


def test_page_below_15_percent_is_flagged():
    rows = [
        {"landing_page": "lp_a", "visitors": 100, "form_submissions": 9, "data_as_of": DATA_AS_OF},
    ]

    result = landing_page_performance(rows)

    assert result[0]["conversion_rate_pct"] == 9.0
    assert result[0]["below_threshold"] is True


def test_page_above_15_percent_is_not_flagged():
    rows = [
        {"landing_page": "lp_b", "visitors": 100, "form_submissions": 22, "data_as_of": DATA_AS_OF},
    ]

    result = landing_page_performance(rows)

    assert result[0]["conversion_rate_pct"] == 22.0
    assert result[0]["below_threshold"] is False


def test_zero_visitors_returns_no_data_not_zero():
    rows = [
        {"landing_page": "lp_c", "visitors": 0, "form_submissions": 0, "data_as_of": DATA_AS_OF},
    ]

    result = landing_page_performance(rows)

    assert result[0]["conversion_rate_pct"] is None
    assert result[0]["below_threshold"] is False
