def test_result_has_borrower_id():
    assert result["borrower_id"] is not None

def test_name_matches_input():
    assert result["name"] is not None

def test_credit_score_in_range():
    assert 300 <= result["credit_score"] <= 850

def test_employment_status_valid():
    assert result["employment_status"] in ("employed", "self_employed", "unemployed")

def test_monthly_income_positive():
    assert result["monthly_income"] > 0

def test_all_fields_present():
    expected = ["borrower_id", "name", "address", "city", "phone", "email",
                "credit_score", "monthly_income", "employment_status"]
    for field in expected:
        assert field in result, f"missing field: {field}"
