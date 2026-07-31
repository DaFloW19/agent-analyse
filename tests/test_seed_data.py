from agents.analyst.seed_data import generate_seed_dataset


def test_same_seed_produces_identical_dataset():
    first = generate_seed_dataset(seed=7)
    second = generate_seed_dataset(seed=7)

    assert first.leads == second.leads
    assert first.spend_rows == second.spend_rows
    assert first.booking_rows == second.booking_rows
    assert first.deal_rows == second.deal_rows


def test_different_seed_produces_different_leads():
    first = generate_seed_dataset(seed=1)
    second = generate_seed_dataset(seed=2)

    assert first.leads != second.leads


def test_dataset_includes_unattributed_leads():
    dataset = generate_seed_dataset()

    assert any(lead["campaign"] is None for lead in dataset.leads)


def test_dataset_includes_a_zero_spend_day():
    dataset = generate_seed_dataset()

    assert any(row["spend"] == 0.0 for row in dataset.spend_rows)


def test_bad_ad_set_never_reaches_sql_threshold():
    dataset = generate_seed_dataset()

    bad_ad_set_leads = [lead for lead in dataset.leads if lead["ad_set"] == "adset_retarget_bad"]

    assert bad_ad_set_leads
    assert all((lead["score"] or 0) < 61 for lead in bad_ad_set_leads)


def test_landing_pages_include_a_below_and_above_threshold_page():
    dataset = generate_seed_dataset()

    rates = {
        row["landing_page"]: row["form_submissions"] / row["visitors"] * 100
        for row in dataset.landing_page_rows
    }

    assert any(rate < 15.0 for rate in rates.values())
    assert any(rate >= 15.0 for rate in rates.values())
