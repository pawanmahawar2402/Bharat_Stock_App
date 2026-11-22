"""Darvas box detection on synthetic price paths with known answers."""
import numpy as np
import pandas as pd
from app.services.darvas_service import find_darvas_box, darvas_trade_plan


def _frame(rows):
    """rows: list of (high, low, close, volume). Dates are consecutive business days."""
    idx = pd.bdate_range("2025-01-01", periods=len(rows))
    df = pd.DataFrame(rows, columns=["High", "Low", "Close", "Volume"], index=idx)
    df["Open"] = df["Close"]
    return df[["Open", "High", "Low", "Close", "Volume"]]


def _ramp(n=40, start=80.0, step=0.5):
    rows = []
    for i in range(n):
        c = start + i * step
        rows.append((c + 0.5, c - 0.5, c, 1000))
    return rows


def _box_rows(top=100.0, bottom=90.0):
    """Top 100 made, lower highs for 3 days, dip to 90, holds above 90 for 3 days."""
    return [
        (top, top - 2, top - 1, 1000),        # new high = box top
        (98, 92, 95, 1000),                   # below top 1
        (97, 90, 93, 1000),                   # below top 2, dip to bottom
        (99, 93, 96, 1000),                   # below top 3 -> top confirmed
        (96, 91, 94, 1000),                   # holds above bottom 1
        (95, 92, 93, 1000),                   # holds 2
        (95, 92, 94, 1000),                   # holds 3 -> box complete
    ]


def test_breakout_on_volume_is_detected():
    rows = _ramp() + _box_rows() + [(101.5, 99.5, 101.0, 3000)]   # close above 100 on 3x volume
    df = _frame(rows)
    box = find_darvas_box(df)
    assert box is not None
    assert box["box_top"] == 100.0
    assert box["box_bottom"] == 90.0
    assert box["status"] == "Breakout"
    assert box["breakout_volume_ratio"] is not None and box["breakout_volume_ratio"] > 1.5
    assert box["stop_loss"] < box["box_bottom"]
    assert box["target"] == 110.0   # measured move: top + height


def test_inside_box_when_price_sits_mid_range():
    rows = _ramp() + _box_rows() + [(94, 92, 93, 1000)]
    box = find_darvas_box(_frame(rows))
    assert box is not None
    assert box["status"] == "Inside box"


def test_near_breakout_when_pressing_the_top():
    rows = _ramp() + _box_rows() + [(99.5, 97, 99.0, 1000)]   # within 3% below 100
    box = find_darvas_box(_frame(rows))
    assert box["status"] == "Near breakout"
    plan = darvas_trade_plan(box)
    assert plan["entry"] == 100.0
    assert plan["stop_loss"] == round(90 * 0.995, 2)


def test_breakdown_below_box_bottom():
    rows = _ramp() + _box_rows() + [(90, 84, 85, 1000)]
    box = find_darvas_box(_frame(rows))
    assert box["status"] == "Breakdown"


def test_no_box_in_pure_noise_downtrend_returns_none_or_not_actionable():
    rows = [(100 - i * 0.3 + 0.5, 100 - i * 0.3 - 0.5, 100 - i * 0.3, 1000) for i in range(60)]
    box = find_darvas_box(_frame(rows))
    # A steady downtrend keeps making lower highs: no new top ever confirms a box
    assert box is None or box["status"] not in ("Breakout", "Near breakout")


def test_short_history_returns_none():
    assert find_darvas_box(_frame(_ramp(10))) is None


def _strong_stock(n=260, start=50.0, step=0.4, volume=300_000):
    idx = pd.bdate_range("2024-01-01", periods=n)
    closes = np.array([start + i * step for i in range(n)])
    df = pd.DataFrame({"Open": closes, "High": closes + 0.5, "Low": closes - 0.5,
                       "Close": closes, "Volume": float(volume)}, index=idx)
    return df


def test_momentum_screen_passes_strong_liquid_large_cap():
    from app.services.darvas_service import momentum_screen
    res = momentum_screen(_strong_stock(), market_cap_inr=5000 * 1e7)
    assert res is not None and res["passed"] == 4


def test_momentum_screen_rejects_far_from_high_small_cap_or_illiquid():
    from app.services.darvas_service import momentum_screen
    df = _strong_stock()
    assert momentum_screen(df, market_cap_inr=500 * 1e7) is None            # below Rs 1,000 Cr
    assert momentum_screen(_strong_stock(volume=50_000), market_cap_inr=5000 * 1e7) is None  # thin volume
    fallen = df.copy()
    fallen.iloc[-1, fallen.columns.get_loc("Close")] = 60.0                 # far below the 52-week high
    assert momentum_screen(fallen, market_cap_inr=5000 * 1e7) is None
