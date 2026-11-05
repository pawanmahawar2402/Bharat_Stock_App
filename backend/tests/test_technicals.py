import pytest
import pandas as pd
import numpy as np
from app.services.technical_service import TechnicalEngine

@pytest.fixture
def sample_ohlcv_data():
    dates = pd.date_range(start="2023-01-01", periods=150, freq="B")
    np.random.seed(42)
    base_price = 1000.0
    returns = np.random.normal(0.001, 0.015, len(dates))
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        "Open": prices * (1 + np.random.normal(0, 0.002, len(dates))),
        "High": prices * (1 + np.abs(np.random.normal(0, 0.008, len(dates)))),
        "Low": prices * (1 - np.abs(np.random.normal(0, 0.008, len(dates)))),
        "Close": prices,
        "Volume": np.random.randint(100000, 500000, len(dates))
    }, index=dates)
    return df

def test_add_indicators(sample_ohlcv_data):
    df_ind = TechnicalEngine.add_indicators(sample_ohlcv_data)
    assert "SMA20" in df_ind.columns
    assert "SMA50" in df_ind.columns
    assert "SMA200" in df_ind.columns
    assert "RSI" in df_ind.columns
    assert "MACD" in df_ind.columns
    assert "BB_Upper" in df_ind.columns
    assert "ATR" in df_ind.columns

    last_rsi = df_ind["RSI"].iloc[-1]
    assert 0 <= last_rsi <= 100

def test_support_resistance_and_fibonacci(sample_ohlcv_data):
    sr = TechnicalEngine.detect_support_resistance(sample_ohlcv_data)
    assert isinstance(sr, list)
    assert len(sr) > 0

    fib = TechnicalEngine.calculate_fibonacci_levels(sample_ohlcv_data)
    assert "61.8% (Golden Pocket)" in fib
    assert fib["100.0% (Swing High)"] > fib["0.0% (Swing Low)"]

def test_technical_analysis(sample_ohlcv_data):
    res = TechnicalEngine.analyze(sample_ohlcv_data)
    assert "overall_rating" in res
    assert res["overall_rating"] in ["Strong Buy", "Buy", "Neutral", "Sell", "Strong Sell"]
    assert "signals" in res
    assert res["technical_score"] >= 0
