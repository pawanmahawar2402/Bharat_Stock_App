import pytest
from app.services.valuation_service import ValuationEngine

def test_dcf_calculation():
    # Test DCF with sample profitable firm
    res = ValuationEngine.calculate_dcf(
        fcf_cr=10000.0,
        shares_cr=100.0,
        growth_rate_stage1=0.12,
        growth_rate_stage2=0.06,
        terminal_growth=0.045,
        wacc=0.11,
        cash_cr=5000.0,
        debt_cr=2000.0,
        margin_of_safety_pct=0.20
    )

    assert res["is_applicable"] == True
    assert res["intrinsic_value"] > 0
    assert res["fair_value_with_mos"] < res["intrinsic_value"]
    assert len(res["projected_fcfs"]) == 10

def test_graham_valuation():
    res = ValuationEngine.calculate_graham_valuation(
        eps=120.0,
        book_value=650.0,
        expected_growth_rate=12.0,
        india_10y_yield=6.80
    )

    assert res["is_applicable"] == True
    assert res["graham_number"] > 0
    assert res["graham_formula_value"] > 0

def test_bank_valuation():
    # HDFC Bank style parameters: BVPS 600, ROE 16%
    res = ValuationEngine.calculate_bank_valuation(
        book_value=600.0,
        roe=16.0,
        cost_of_equity=0.12,
        long_term_growth=0.06
    )

    assert res["is_applicable"] == True
    assert res["target_pb"] > 1.0
    assert res["intrinsic_value"] > 600.0

def test_quality_scorecard():
    fund = {
        "return_on_equity": 0.22,
        "debt_to_equity": 0.15,
        "free_cashflow": 15000000000,
        "operating_cashflow": 22000000000,
        "eps_trailing": 85.0,
        "peg_ratio": 1.2,
        "sector": "Information Technology",
        "industry": "IT Services"
    }
    res = ValuationEngine.compute_quality_scorecard(fund, {})
    assert res["quality_score"] >= 70
    # No statements -> Piotroski is unknown, never a synthetic default
    assert res["piotroski_f_score"] is None
