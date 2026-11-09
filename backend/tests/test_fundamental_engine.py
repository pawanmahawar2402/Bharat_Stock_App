"""
Deterministic tests for the statement-driven valuation engine.
All fixtures are synthetic statements in INR (absolute), keyed the way DataFetcher emits them.
Crore = 1e7.
"""
import pytest
from app.services import fundamental_engine as fe
from app.services.research_service import stock_macro_sentiment, triangulate
from app.services.valuation_service import ValuationEngine

CR = 1e7


def _statements(years, rev, ebit, ebitda, pretax, tax, interest, ni, cogs, cfo, capex, dep,
                div, net_borrow, debt, cash, equity, assets, ca, cl, shares):
    """Builds {period_end: {line: value}} blocks for N years (most recent first)."""
    dates = [f"{2025 - i}-03-31" for i in range(len(rev))]
    IS, CF, BS = {}, {}, {}
    for i, d in enumerate(dates):
        IS[d] = {"Total Revenue": rev[i] * CR, "EBIT": ebit[i] * CR, "EBITDA": ebitda[i] * CR,
                 "Pretax Income": pretax[i] * CR, "Tax Provision": tax[i] * CR,
                 "Interest Expense": interest[i] * CR, "Net Income Common Stockholders": ni[i] * CR,
                 "Cost Of Revenue": cogs[i] * CR}
        CF[d] = {"Operating Cash Flow": cfo[i] * CR, "Capital Expenditure": -capex[i] * CR,
                 "Depreciation And Amortization": dep[i] * CR, "Cash Dividends Paid": -div[i] * CR,
                 "Net Issuance Payments Of Debt": net_borrow[i] * CR}
        BS[d] = {"Total Debt": debt[i] * CR, "Cash Cash Equivalents And Short Term Investments": cash[i] * CR,
                 "Stockholders Equity": equity[i] * CR, "Total Assets": assets[i] * CR,
                 "Current Assets": ca[i] * CR, "Current Liabilities": cl[i] * CR,
                 "Ordinary Shares Number": shares}
    return {"income_statement": IS, "cash_flow": CF, "balance_sheet": BS}


def industrial_financials():
    # Healthy, cash-generative industrial: FCFF = 180 + 20*(1-t) - 60 > 0
    return _statements(
        years=[0, 1, 2], rev=[1000, 900, 800], ebit=[200, 180, 160], ebitda=[260, 235, 210],
        pretax=[190, 170, 150], tax=[47.5, 42.5, 37.5], interest=[20, 18, 16], ni=[142.5, 127.5, 112.5],
        cogs=[600, 560, 520], cfo=[180, 165, 150], capex=[60, 55, 50], dep=[60, 55, 50],
        div=[30, 28, 25], net_borrow=[10, 0, -5], debt=[200, 210, 220], cash=[100, 90, 80],
        equity=[800, 700, 600], assets=[1500, 1400, 1300], ca=[500, 480, 450], cl=[300, 290, 280],
        shares=1e8,
    )


INDUSTRIAL_FUND = {"symbol": "TEST.NS", "company_name": "Test Industrials", "sector": "Industrials",
                   "industry": "Specialty Machinery", "current_price": 1000.0, "market_cap": 1000 * 1e8,
                   "shares_outstanding": 1e8, "beta": 1.1, "enterprise_to_ebitda": 18.0}


def test_non_financial_uses_fcff_dcf():
    res = fe.run_valuation(INDUSTRIAL_FUND, industrial_financials())
    assert res["is_applicable"] is True
    assert res["method_code"] == "FCFF"
    assert res["intrinsic_value"] > 0
    wacc = res["inputs"]["wacc_pct"]
    assert 8.0 < wacc < 16.0
    # Terminal growth must sit below WACC by the minimum spread
    assert wacc - res["inputs"]["terminal_growth_pct"] >= 2.0
    # Sensitivity grid is 5 WACC rows x 3 growth columns
    grid = res["sensitivity"]["value_per_share_grid"]
    assert len(grid) == 5 and all(len(r) == 3 for r in grid)
    # Higher WACC must not raise value (monotonic in the grid's middle column)
    col = [r[1] for r in grid]
    assert col == sorted(col, reverse=True)
    # EV/EBITDA is kept as a cross-check, not the primary method
    assert "EV_EBITDA" in res["cross_checks"]


def test_fcff_margin_matches_hand_calculation():
    res = fe.run_valuation(INDUSTRIAL_FUND, industrial_financials())
    # Year 0 FCFF = 180 + 20*(1-t) - 60, t = 47.5/190 = 25%
    t = 47.5 / 190
    fcff0 = 180 + 20 * (1 - t) - 60
    fcff1 = 165 + 18 * (1 - 42.5 / 170) - 55
    fcff2 = 150 + 16 * (1 - 37.5 / 150) - 50
    expected_margin = (fcff0 / 1000 + fcff1 / 900 + fcff2 / 800) / 3
    assert res["inputs"]["normalised_fcff_margin_pct"] == pytest.approx(expected_margin * 100, abs=0.01)


def test_financial_institution_uses_fcfe():
    fin = _statements(
        years=[0, 1, 2], rev=[5000, 4300, 3800], ebit=[0, 0, 0], ebitda=[0, 0, 0],
        pretax=[650, 560, 480], tax=[160, 140, 120], interest=[0, 0, 0],
        ni=[500, 430, 370], cogs=[0, 0, 0], cfo=[400, 350, 300], capex=[20, 20, 20],
        dep=[10, 10, 10], div=[100, 90, 80], net_borrow=[0, 0, 0], debt=[0, 0, 0],
        cash=[0, 0, 0], equity=[4000, 3600, 3100], assets=[50000, 45000, 40000],
        ca=[0, 0, 0], cl=[0, 0, 0], shares=2e8,
    )
    fund = {"symbol": "BANK.NS", "company_name": "Test Bank", "sector": "Financial Services",
            "industry": "Banks - Regional", "current_price": 400.0, "market_cap": 400 * 2e8,
            "shares_outstanding": 2e8, "beta": 1.0}
    res = fe.run_valuation(fund, fin)
    assert res["is_financial_institution"] is True
    assert res["method_code"] == "FCFE"
    assert res["intrinsic_value"] > 0
    # Growth = ROE x retention; payout = 100/500 = 20% => retention 80%
    roe = 500 / ((4000 + 3600) / 2)
    assert res["inputs"]["roe_pct"] == pytest.approx(roe * 100, abs=0.01)
    assert res["inputs"]["sustainable_growth_pct"] == pytest.approx(roe * 0.8 * 100, abs=0.01)
    assert "P_B_ROE" in res["cross_checks"]


def test_negative_fcff_falls_back_to_ev_ebitda():
    fin = _statements(
        years=[0, 1], rev=[400, 300], ebit=[60, 40], ebitda=[80, 60],
        pretax=[55, 35], tax=[13, 9], interest=[5, 4], ni=[42, 26], cogs=[250, 200],
        cfo=[10, 20], capex=[100, 90], dep=[20, 20], div=[0, 0], net_borrow=[50, 40],
        debt=[200, 150], cash=[100, 80], equity=[900, 800], assets=[1400, 1200],
        ca=[400, 350], cl=[300, 280], shares=1e8,
    )
    res = fe.run_valuation(INDUSTRIAL_FUND, fin)
    # Negative FCFF with positive NOPAT: the growth-consistent value-driver model is primary,
    # and the EV/EBITDA relative value is kept as a cross-check.
    assert res["method_code"] == "VALUE_DRIVER"
    assert res["cross_checks"]["EV_EBITDA"]["multiple_used"] == 24.0
    # Sector assumption for Industrials is 24x; equity = 24*80 - 200 + 100
    expected = (24 * 80 - 200 + 100) * CR / 1e8
    assert res["cross_checks"]["EV_EBITDA"]["value_per_share"] == pytest.approx(expected, rel=1e-3)


def test_missing_statements_returns_not_applicable_not_a_made_up_number():
    res = fe.run_valuation(INDUSTRIAL_FUND, {})
    assert res["is_applicable"] is False
    assert res["intrinsic_value"] is None
    assert res["margin_of_safety_pct"] is None


def test_live_peer_multiple_overrides_sector_assumption():
    fin = _statements(
        years=[0, 1], rev=[400, 300], ebit=[60, 40], ebitda=[80, 60], pretax=[55, 35], tax=[13, 9],
        interest=[5, 4], ni=[42, 26], cogs=[250, 200], cfo=[10, 20], capex=[100, 90], dep=[20, 20],
        div=[0, 0], net_borrow=[50, 40], debt=[200, 150], cash=[100, 80], equity=[900, 800],
        assets=[1400, 1200], ca=[400, 350], cl=[300, 280], shares=1e8)
    res = fe.run_valuation(INDUSTRIAL_FUND, fin, peer_ev_ebitda=15.0)
    assert res["cross_checks"]["EV_EBITDA"]["multiple_used"] == 15.0
    assert "Live peer" in res["cross_checks"]["EV_EBITDA"]["multiple_source"]


def test_piotroski_computed_from_statements():
    pio = fe.piotroski_fscore(industrial_financials())
    assert pio["checks_available"] == 9
    # ROA 2025 = 142.5/1500 = 9.5% vs 2024 = 127.5/1400 = 9.1%, so ROA-improving PASSES
    names = {c["check"]: c["passed"] for c in pio["checks"]}
    assert names["ROA improving"] is True
    assert names["CFO > 0"] is True
    assert 0 <= pio["score"] <= 9


def test_piotroski_without_statements_is_none_not_fabricated():
    pio = fe.piotroski_fscore({})
    assert pio["score"] is None
    q = ValuationEngine.compute_quality_scorecard({"return_on_equity": 0.22}, {})
    assert q["piotroski_f_score"] is None


def test_dcf_unchanged_for_interactive_simulator():
    res = ValuationEngine.calculate_dcf(fcf_cr=100, shares_cr=10, wacc=0.11, terminal_growth=0.045)
    assert res["is_applicable"] is True and res["intrinsic_value"] > 0


def test_triangulation_strong_case_is_buy():
    val = {"margin_of_safety_pct": 40.0}
    tri = triangulate(val, technical_score=80, quality_score=80, regime="Risk-On", sentiment_net=2)
    assert tri["action"] in ("Strong Buy", "Buy")
    assert tri["agreement"] == "Aligned"


def test_triangulation_overvalued_weak_tape_is_sell():
    val = {"margin_of_safety_pct": -40.0}
    tri = triangulate(val, technical_score=25, quality_score=40, regime="Risk-Off", sentiment_net=-3)
    assert tri["action"] in ("Reduce", "Sell")


def test_stock_macro_sentiment_fires_rupee_tailwind_for_it():
    market = [
        {"name": "USD / INR", "change_1m_pct": 2.0, "current_value": 90.0},
        {"name": "India VIX", "change_1m_pct": 0.0, "current_value": 15.0},
        {"name": "Nifty 50", "change_1m_pct": 0.0, "current_value": 20000.0},
        {"name": "Nasdaq Composite", "change_1m_pct": 0.0, "current_value": 15000.0},
        {"name": "US 10-Yr Treasury", "change_1m_pct": 0.0, "current_value": 4.0},
        {"name": "Brent Crude Oil", "change_1m_pct": 0.0, "current_value": 80.0},
    ]
    fund = {"sector": "Technology", "industry": "Information Technology Services", "beta": 1.0,
            "debt_to_equity": 0, "change_1m_pct": 0.0}
    s = stock_macro_sentiment(fund, market)
    assert s["profile"] == "IT services"
    usd = next(f for f in s["factors"] if f["rule"] == "usd_inr")
    assert usd["stance"] == "positive" and usd["points"] > 0
    assert s["sentiment"] in ("Positive", "Mixed")


def test_stock_macro_sentiment_differs_within_sector():
    """Same sector and same market: beta, leverage and momentum must change the score."""
    market = [
        {"name": "Nifty 50", "change_1m_pct": 4.0, "current_value": 22000.0},
        {"name": "India VIX", "change_1m_pct": 0.0, "current_value": 22.0},
        {"name": "US 10-Yr Treasury", "change_1m_pct": 0.0, "current_value": 4.8},
        {"name": "USD / INR", "change_1m_pct": 0.0, "current_value": 90.0},
        {"name": "Brent Crude Oil", "change_1m_pct": 0.0, "current_value": 80.0},
        {"name": "Nasdaq Composite", "change_1m_pct": 0.0, "current_value": 15000.0},
    ]
    base = {"sector": "Consumer Cyclical", "industry": "Auto Manufacturers", "debt_to_equity": 10}
    high_beta = stock_macro_sentiment({**base, "beta": 1.8, "change_1m_pct": 6.0}, market)
    low_beta = stock_macro_sentiment({**base, "beta": 0.5, "change_1m_pct": -2.0}, market)
    assert high_beta["score"] != low_beta["score"]
    assert high_beta["beta_used"] > low_beta["beta_used"]
    assert high_beta["score"] > low_beta["score"]


def _leveraged_fin():
    # EBITDA 130 Cr with debt 1,395 Cr: net debt dwarfs any sector-multiple enterprise value
    return _statements(
        years=[0, 1], rev=[848, 756], ebit=[102, 88], ebitda=[130, 116], pretax=[70, 60], tax=[18, 15],
        interest=[30, 25], ni=[29, 35], cogs=[600, 550], cfo=[-230, 196], capex=[556, 318], dep=[28, 28],
        div=[0, 0], net_borrow=[800, 100], debt=[1395, 597], cash=[5, 5], equity=[816, 789],
        assets=[2000, 1500], ca=[400, 350], cl=[300, 280], shares=3.0e7)


def test_leveraged_company_relative_value_is_not_the_headline():
    fund = {**INDUSTRIAL_FUND, "current_price": 2395.0, "market_cap": 2395.0 * 3.0e7,
            "shares_outstanding": 3.0e7, "enterprise_value": 7.5e10}
    res = fe.run_valuation(fund, _leveraged_fin(), peer_ev_ebitda=15.0)
    assert res["method_code"] == "VALUE_DRIVER"
    # The sector/peer multiple gives a thin, unstable residual; it must not be the headline value
    assert res["cross_checks"]["EV_EBITDA"]["value_per_share"] != res["intrinsic_value"]


def test_market_pricing_far_above_benchmark_is_reflected_in_implied_profit():
    fin = _statements(
        years=[0, 1], rev=[400, 300], ebit=[60, 40], ebitda=[80, 60], pretax=[55, 35], tax=[13, 9],
        interest=[5, 4], ni=[42, 26], cogs=[250, 200], cfo=[10, 20], capex=[100, 90], dep=[20, 20],
        div=[0, 0], net_borrow=[50, 40], debt=[200, 150], cash=[100, 80], equity=[900, 800],
        assets=[1400, 1200], ca=[400, 350], cl=[300, 280], shares=1e8)
    fund = {**INDUSTRIAL_FUND, "enterprise_value": 70 * 80 * CR, "market_cap": 1000 * 1e8}
    res = fe.run_valuation(fund, fin)
    implied = res["cross_checks"]["VALUE_DRIVER"]["market_implied_nopat_multiple"]
    assert implied > 1.0  # the price needs more than today's normalised profit


def test_value_driver_nil_equity_is_reported_as_zero_not_error():
    fin = _leveraged_fin()
    fund = {**INDUSTRIAL_FUND, "current_price": 2395.0, "market_cap": 2395.0 * 3.0e7,
            "shares_outstanding": 3.0e7, "enterprise_value": 7.5e10}
    res = fe.run_valuation(fund, fin)
    assert res["method_code"] == "VALUE_DRIVER"
    assert res["is_applicable"] is True
    assert res["intrinsic_value"] == 0.0
    assert res["margin_of_safety_pct"] is None
    vd = res["cross_checks"]["VALUE_DRIVER"]
    assert vd["market_implied_nopat_multiple"] > 1.0
    assert vd["scenarios"]["bear"]["value_per_share"] <= vd["scenarios"]["bull"]["value_per_share"]


def test_value_driver_ev_rises_with_return_on_new_capital():
    low = fe.value_driver_ev(100e7, 0.08, 0.12, 0.12, 0.045)
    high = fe.value_driver_ev(100e7, 0.08, 0.12, 0.20, 0.045)
    assert high > low


def test_implied_multiple_solves_back_to_market_ev():
    nop = 65e7
    target = fe.value_driver_ev(14.8 * nop, 0.08, 0.12, 0.12, 0.045)
    k = fe._implied_nopat_multiple(target, nop, 0.08, 0.12, 0.12, 0.045)
    assert abs(k - 14.8) < 0.01
