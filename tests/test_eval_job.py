from agents.analyst.eval_job import evaluate_weekly_summary, run_weekly_eval_job

FIGURES = {"roas": 1.6}


def test_evaluate_weekly_summary_passes_when_grounded_and_french():
    summary = "Le ROAS global est de 1.60x cette semaine, une belle performance pour le client."

    result = evaluate_weekly_summary(summary, FIGURES, "demo-real-estate")

    assert result["grounded"] is True
    assert result["ungrounded_numbers"] == []
    assert result["looks_french"] is True
    assert result["score"] == 1.0


def test_evaluate_weekly_summary_flags_an_invented_number():
    summary = "Le ROAS a explosé à 99.9x, un record historique pour le client."

    result = evaluate_weekly_summary(summary, FIGURES, "demo-real-estate")

    assert result["grounded"] is False
    assert "99.9" in result["ungrounded_numbers"]
    assert result["score"] == 0.5


def test_evaluate_weekly_summary_flags_non_french_text():
    summary = "The ROAS is 1.60x this week, a great performance for the client."

    result = evaluate_weekly_summary(summary, FIGURES, "demo-real-estate")

    assert result["looks_french"] is False
    assert result["score"] == 0.5


def test_run_weekly_eval_job_is_a_no_op_when_there_is_no_summary():
    assert run_weekly_eval_job(None, FIGURES, "demo-real-estate") is None


def test_run_weekly_eval_job_returns_the_evaluation_for_a_real_summary():
    summary = "Le ROAS global est de 1.60x cette semaine."

    result = run_weekly_eval_job(summary, FIGURES, "demo-real-estate")

    assert result is not None
    assert result["grounded"] is True
