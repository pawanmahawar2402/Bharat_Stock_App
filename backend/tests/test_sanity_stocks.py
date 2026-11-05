import pytest
from app.services.data_fetcher import DataFetcher
from app.services.valuation_service import ValuationEngine
from app.services.technical_service import TechnicalEngine

@pytest.mark.parametrize("symbol", ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "MAHABANK.NS"])
def test_known_stocks_sanity(symbol):
    fundamentals = DataFetcher.fetch_quote_and_fundamentals(symbol)
    assert fundamentals is not None
    assert "current_price" in fundamentals
    
    # Financial statements
    financials = DataFetcher.fetch_financial_statements(symbol)
    assert isinstance(financials, dict)

    # Valuation summary
    val = ValuationEngine.calculate_valuation_summary(fundamentals, financials)
    assert "blended_intrinsic_value" in val
    assert val["blended_intrinsic_value"] > 0
    assert "valuation_label" in val
    assert "quality_scorecard" in val

    # Technicals
    hist = DataFetcher.fetch_history(symbol, period="3mo", interval="1d")
    if not hist.empty:
        tech = TechnicalEngine.analyze(hist)
        assert "overall_rating" in tech
        assert "signals" in tech
