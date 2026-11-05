"""Pattern recognition on synthetic series with known answers."""
import numpy as np
import pandas as pd
from app.services.technical_patterns import detect_candlestick_patterns, detect_chart_patterns


def _df(ohlc):
    idx = pd.bdate_range("2025-01-01", periods=len(ohlc))
    arr = np.array(ohlc, dtype=float)
    return pd.DataFrame({"Open": arr[:, 0], "High": arr[:, 1], "Low": arr[:, 2], "Close": arr[:, 3],
                         "Volume": 1000.0}, index=idx)


def _names(res):
    return {p["pattern"] for p in res}


def _downtrend(n=15, start=110.0):
    rows = []
    price = start
    for _ in range(n):
        rows.append((price, price + 0.5, price - 2.0, price - 1.8))
        price -= 2.0
    return rows, price


def _uptrend(n=15, start=80.0):
    rows = []
    price = start
    for _ in range(n):
        rows.append((price, price + 2.2, price - 0.5, price + 2.0))
        price += 2.0
    return rows, price


def test_hammer_after_downtrend_is_bullish():
    rows, p = _downtrend()
    # small body near the top, long lower shadow
    rows.append((p + 0.5, p + 0.8, p - 6.0, p + 0.2))
    res = detect_candlestick_patterns(_df(rows))
    hammer = [x for x in res if x["pattern"] == "Hammer"]
    assert hammer and hammer[0]["bias"] == "Bullish"


def test_shooting_star_after_uptrend_is_bearish():
    rows, p = _uptrend()
    # small body near the bottom, long upper shadow
    rows.append((p - 0.5, p + 6.0, p - 0.8, p - 0.2))
    res = detect_candlestick_patterns(_df(rows))
    star = [x for x in res if x["pattern"] == "Shooting Star"]
    assert star and star[0]["bias"] == "Bearish"
    assert "Hanging Man" not in _names(res)


def test_same_shape_after_uptrend_is_hanging_man_not_hammer():
    rows, p = _uptrend()
    rows.append((p + 0.2, p + 0.5, p - 6.0, p - 0.1))   # hammer shape at the top
    res = detect_candlestick_patterns(_df(rows))
    assert "Hanging Man" in _names(res)
    assert "Hammer" not in _names(res)


def _zigzag(points, steps=6):
    """Linear legs between vertices: each vertex is a clean pivot for a 5-bar window."""
    closes = []
    for a, b in zip(points, points[1:]):
        for k in range(steps):
            closes.append(a + (b - a) * k / steps)
    closes.append(points[-1])
    return [(c - 0.4, c + 0.4, c - 0.4, c) for c in closes]


def test_bearish_engulfing():
    rows, p = _uptrend(n=14)
    rows.append((100.0, 102.0, 99.5, 101.0))   # green candle
    rows.append((102.0, 102.5, 98.5, 99.0))    # red body engulfs the green body
    res = detect_candlestick_patterns(_df(rows))
    assert "Bearish Engulfing" in _names(res)


def test_head_and_shoulders_confirmed_on_neckline_break():
    # left shoulder 110, head 125, right shoulder 111, neckline 100, then a close at 86 breaks it
    rows = _zigzag([100, 110, 100, 125, 100, 111, 100, 86])
    res = detect_chart_patterns(_df(rows))
    names = {p["pattern"]: p for p in res}
    assert "Head and Shoulders" in names
    assert names["Head and Shoulders"]["bias"] == "Bearish"
    assert names["Head and Shoulders"]["status"] == "Confirmed"


def test_double_bottom_confirmed():
    # two troughs at 100 with a peak of 110 between; a close at 125 breaks above the neckline
    rows = _zigzag([120, 100, 110, 100, 125, 130])
    res = detect_chart_patterns(_df(rows))
    names = {p["pattern"]: p for p in res}
    assert "Double Bottom" in names
    assert names["Double Bottom"]["status"] == "Confirmed"


def test_no_chart_pattern_on_a_straight_line():
    rows = [(100 + i + 0.5, 100 + i + 1.0, 100 + i - 0.5, 100 + i + 0.2) for i in range(60)]
    assert detect_chart_patterns(_df(rows)) == []
