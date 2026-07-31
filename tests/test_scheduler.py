from agents.analyst.scheduler import build_weekly_optimisation_report


def test_weekly_report_has_one_recommendation_per_category():
    report = build_weekly_optimisation_report()

    assert "Scale:" in report
    assert "Pause:" in report
    assert "Rewrite:" in report


def test_weekly_report_names_the_deliberately_bad_ad_set_to_pause():
    report = build_weekly_optimisation_report()

    assert "Pause: adset_retarget_bad" in report


def test_weekly_report_names_the_underperforming_landing_page():
    report = build_weekly_optimisation_report()

    assert "Rewrite: lp_buyers_v1" in report


def test_weekly_report_states_it_never_executes():
    report = build_weekly_optimisation_report()

    assert "no action below has been executed" in report.lower()


def test_weekly_report_scale_and_pause_never_recommend_unattributed():
    report = build_weekly_optimisation_report()

    assert "Scale: unattributed" not in report
    assert "Pause: unattributed" not in report
