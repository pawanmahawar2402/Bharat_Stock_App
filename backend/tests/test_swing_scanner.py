import pytest
import pandas as pd
import numpy as np
from app.services.swing_service import SwingScanner

def test_backtest_statistics():
    stats = SwingScanner.get_backtest_statistics()
    assert "setups" in stats
    assert len(stats["setups"]) == 6
    for s in stats["setups"]:
        assert s["win_rate_pct"] > 50.0
        assert s["profit_factor"] > 1.5
        assert s["sample_size"] > 100

def test_swing_setup_generation():
    # Construct a breakout scenario
    dates = pd.date_range(start="2023-01-01", periods=60, freq="B")
    prices = [100.0 + (i * 0.5) for i in range(59)] + [145.0] # Massive breakout on last day
    volumes = [100000 for _ in range(59)] + [500000] # Massive volume surge

    df = pd.DataFrame({
        "Open": prices,
        "High": [p * 1.01 for p in prices],
        "Low": [p * 0.99 for p in prices],
        "Close": prices,
        "Volume": volumes
    }, index=dates)

    picks = SwingScanner.identify_setups_for_stock(df, "TEST.NS", "Test Company", "Technology")
    assert isinstance(picks, list)
    if picks:
        p = picks[0]
        assert p["risk_reward"] >= 1.4
        assert p["stop_loss"] < p["current_price"]
        assert p["target_1"] > p["current_price"]
        assert p["target_2"] > p["target_1"]
        assert "50%" in p["profit_plan"]
