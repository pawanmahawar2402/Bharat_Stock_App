"""
Price-pattern recognition: candlestick patterns (with trend context) and chart patterns
(head & shoulders, double tops and bottoms) built from confirmed pivot points.

Every result carries: name, bias (Bullish / Bearish / Neutral), status (Forming, Confirmed,
or Candle signal), the date it appeared, and the price level that matters for the pattern.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

TREND_LOOKBACK = 10          # bars used to judge short-term trend before a candle
TREND_THRESHOLD = 0.03       # +/-3% over the lookback counts as a trend
PIVOT_WINDOW = 5             # bars either side to confirm a pivot
CHART_LOOKBACK = 150         # bars searched for chart patterns
SHOULDER_TOLERANCE = 0.05    # shoulders within 5% of each other
DOUBLE_TOLERANCE = 0.03      # double tops/bottoms within 3%
NECKLINE_MIN_DEPTH = 0.05    # the trough between two peaks must sit at least 5% lower


def _trend(close: np.ndarray, i: int) -> str:
    if i < TREND_LOOKBACK:
        return "Sideways"
    change = close[i - 1] / close[i - 1 - TREND_LOOKBACK] - 1
    if change >= TREND_THRESHOLD:
        return "Uptrend"
    if change <= -TREND_THRESHOLD:
        return "Downtrend"
    return "Sideways"


def _candle(o, h, l, c):
    body = abs(c - o)
    rng = max(h - l, 1e-9)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return body, rng, upper, lower


def detect_candlestick_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Patterns that complete on the latest one to three sessions."""
    if df is None or len(df) < 15:
        return []
    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    i = len(df) - 1
    date = df.index[i].strftime("%Y-%m-%d")
    trend = _trend(c, i)
    body, rng, upper, lower = _candle(o[i], h[i], l[i], c[i])
    out: List[Dict[str, Any]] = []

    def add(name, bias, desc, status="Candle signal"):
        out.append({"pattern": name, "bias": bias, "status": status, "date": date,
                    "trend_before": trend, "description": desc, "level": round(float(c[i]), 2)})

    # Single-candle shapes, interpreted by the trend that precedes them
    small_body = body <= 0.35 * rng
    if small_body and lower >= 2 * max(body, 1e-9) and upper <= 0.5 * max(body, 1e-9) + 0.1 * rng:
        if trend == "Downtrend":
            add("Hammer", "Bullish",
                "Long lower shadow after a fall: sellers pushed price down, buyers pulled it back up. "
                "Confirmed by a higher close next session.")
        elif trend == "Uptrend":
            add("Hanging Man", "Bearish",
                "Hammer-shaped candle at the top of an advance: selling pressure is appearing. "
                "Confirmed by a lower close next session.")
    if small_body and upper >= 2 * max(body, 1e-9) and lower <= 0.5 * max(body, 1e-9) + 0.1 * rng:
        if trend == "Uptrend":
            add("Shooting Star", "Bearish",
                "Long upper shadow after an advance: buyers pushed price up but could not hold it. "
                "Bearish reversal when the next session closes below this candle's body.")
        elif trend == "Downtrend":
            add("Inverted Hammer", "Bullish",
                "Long upper shadow after a fall: buyers tested higher prices. "
                "Needs a higher close next session to confirm.")

    if body <= 0.1 * rng:
        if lower > 0.6 * rng and upper < 0.1 * rng:
            add("Dragonfly Doji", "Bullish" if trend == "Downtrend" else "Neutral",
                "Open and close at the high with a long lower shadow: indecision that often marks a low.")
        elif upper > 0.6 * rng and lower < 0.1 * rng:
            add("Gravestone Doji", "Bearish" if trend == "Uptrend" else "Neutral",
                "Open and close at the low with a long upper shadow: indecision that often marks a high.")
        else:
            add("Doji", "Neutral", "Open and close nearly equal: indecision. Direction comes from the next session.")

    # Two-candle patterns
    if len(df) >= 2:
        po, ph, pl, pc = o[i - 1], h[i - 1], l[i - 1], c[i - 1]
        if pc < po and c[i] > o[i] and c[i] >= po and o[i] <= pc and c[i] > o[i]:
            add("Bullish Engulfing", "Bullish",
                "A green candle's body fully engulfs the prior red body: a strong reversal signal after a decline."
                if trend != "Uptrend" else
                "A green candle engulfs the prior red body during an advance: continuation rather than reversal.")
        if pc > po and c[i] < o[i] and c[i] <= po and o[i] >= pc:
            add("Bearish Engulfing", "Bearish",
                "A red candle's body fully engulfs the prior green body: a strong reversal signal after an advance.")
        mid_prev = (po + pc) / 2
        if pc < po and c[i] > o[i] and o[i] < pc and mid_prev < c[i] < po:
            add("Piercing Line", "Bullish",
                "Green candle opens below the prior low and closes above the midpoint of the prior red body.")
        if pc > po and c[i] < o[i] and o[i] > pc and mid_prev > c[i] > po:
            add("Dark Cloud Cover", "Bearish",
                "Red candle opens above the prior high and closes below the midpoint of the prior green body.")

    # Three-candle patterns
    if len(df) >= 3:
        k = i - 2
        ko, kh, kl, kc = o[k], h[k], l[k], c[k]
        mo, mc = o[i - 1], c[i - 1]
        k_body = abs(kc - ko)
        m_body, m_rng, _, _ = _candle(mo, h[i - 1], l[i - 1], mc)
        if kc < ko and k_body > 0.5 * (kh - kl) and m_body <= 0.3 * m_rng + 1e-9 and c[i] > o[i] and c[i] > (ko + kc) / 2:
            add("Morning Star", "Bullish",
                "Large red candle, then an indecisive small candle, then a strong green candle recovering above "
                "the midpoint of the first: a three-session bottom reversal.")
        if kc > ko and k_body > 0.5 * (kh - kl) and m_body <= 0.3 * m_rng + 1e-9 and c[i] < o[i] and c[i] < (ko + kc) / 2:
            add("Evening Star", "Bearish",
                "Large green candle, then an indecisive small candle, then a strong red candle closing below the "
                "midpoint of the first: a three-session top reversal.")
        if all(c[j] > o[j] for j in (i - 2, i - 1, i)) and c[i] > c[i - 1] > c[i - 2] \
                and all(abs(c[j] - o[j]) >= 0.5 * (h[j] - l[j]) for j in (i - 2, i - 1, i)):
            add("Three White Soldiers", "Bullish",
                "Three consecutive strong green candles with rising closes: sustained buying pressure.")
        if all(c[j] < o[j] for j in (i - 2, i - 1, i)) and c[i] < c[i - 1] < c[i - 2] \
                and all(abs(c[j] - o[j]) >= 0.5 * (h[j] - l[j]) for j in (i - 2, i - 1, i)):
            add("Three Black Crows", "Bearish",
                "Three consecutive strong red candles with falling closes: sustained selling pressure.")
    return out


def _pivots(series: np.ndarray, kind: str, w: int = PIVOT_WINDOW) -> List[int]:
    idx = []
    for i in range(w, len(series) - w):
        window = series[i - w:i + w + 1]
        if kind == "high" and series[i] == window.max():
            idx.append(i)
        if kind == "low" and series[i] == window.min():
            idx.append(i)
    return idx


def detect_chart_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Head & shoulders, inverse head & shoulders, double top, double bottom, using confirmed pivots.
    'Forming' means the pattern has its shape but the neckline has not been broken.
    'Confirmed' means the latest close is through the neckline.
    """
    if df is None or len(df) < 2 * PIVOT_WINDOW + 20:
        return []
    start = max(0, len(df) - CHART_LOOKBACK)
    sub = df.iloc[start:]
    h = sub["High"].to_numpy(float)
    l = sub["Low"].to_numpy(float)
    c = sub["Close"].to_numpy(float)
    last_close = c[-1]
    dates = sub.index
    highs = _pivots(h, "high")
    lows = _pivots(l, "low")
    out: List[Dict[str, Any]] = []

    # Head and shoulders (bearish): three peaks, middle highest, shoulders roughly level
    for a, b, d in zip(highs, highs[1:], highs[2:]):
        ls, hd, rs = h[a], h[b], h[d]
        if not (hd > ls and hd > rs and abs(ls - rs) / hd <= SHOULDER_TOLERANCE):
            continue
        troughs = [t for t in lows if a < t < d]
        if len(troughs) < 2:
            continue
        neck = (l[troughs[0]] + l[troughs[-1]]) / 2
        status = "Confirmed" if last_close < neck else ("Forming" if d >= len(h) - 20 else None)
        if status:
            out.append({"pattern": "Head and Shoulders", "bias": "Bearish", "status": status,
                        "date": dates[d].strftime("%Y-%m-%d"), "trend_before": "Uptrend",
                        "level": round(float(neck), 2),
                        "description": f"Left shoulder, head at {hd:.2f}, right shoulder. "
                                       f"Neckline {neck:.2f}; a close below it confirms the reversal."})
            break

    # Inverse head and shoulders (bullish): mirror image
    for a, b, d in zip(lows, lows[1:], lows[2:]):
        ls, hd, rs = l[a], l[b], l[d]
        if not (hd < ls and hd < rs and abs(ls - rs) / max(abs(hd), 1e-9) <= SHOULDER_TOLERANCE):
            continue
        peaks = [p for p in highs if a < p < d]
        if len(peaks) < 2:
            continue
        neck = (h[peaks[0]] + h[peaks[-1]]) / 2
        status = "Confirmed" if last_close > neck else ("Forming" if d >= len(l) - 20 else None)
        if status:
            out.append({"pattern": "Inverse Head and Shoulders", "bias": "Bullish", "status": status,
                        "date": dates[d].strftime("%Y-%m-%d"), "trend_before": "Downtrend",
                        "level": round(float(neck), 2),
                        "description": f"Left shoulder, head at {hd:.2f}, right shoulder. "
                                       f"Neckline {neck:.2f}; a close above it confirms the reversal."})
            break

    # Double top (bearish) and double bottom (bullish)
    recent_highs = highs[-6:]
    for a, b in zip(recent_highs, recent_highs[1:]):
        if abs(h[a] - h[b]) / max(h[a], h[b]) > DOUBLE_TOLERANCE or b - a < 2 * PIVOT_WINDOW:
            continue
        troughs = [t for t in lows if a < t < b]
        if not troughs:
            continue
        neck = min(l[t] for t in troughs)
        if (min(h[a], h[b]) - neck) / min(h[a], h[b]) < NECKLINE_MIN_DEPTH:
            continue
        status = "Confirmed" if last_close < neck else ("Forming" if b >= len(h) - 20 else None)
        if status:
            out.append({"pattern": "Double Top", "bias": "Bearish", "status": status,
                        "date": dates[b].strftime("%Y-%m-%d"), "trend_before": "Uptrend",
                        "level": round(float(neck), 2),
                        "description": f"Two peaks near {max(h[a], h[b]):.2f}; a close below the trough at {neck:.2f} confirms."})
            break

    recent_lows = lows[-6:]
    for a, b in zip(recent_lows, recent_lows[1:]):
        if abs(l[a] - l[b]) / max(abs(l[a]), abs(l[b])) > DOUBLE_TOLERANCE or b - a < 2 * PIVOT_WINDOW:
            continue
        peaks = [p for p in highs if a < p < b]
        if not peaks:
            continue
        neck = max(h[p] for p in peaks)
        if (neck - max(l[a], l[b])) / neck < NECKLINE_MIN_DEPTH:
            continue
        status = "Confirmed" if last_close > neck else ("Forming" if b >= len(l) - 20 else None)
        if status:
            out.append({"pattern": "Double Bottom", "bias": "Bullish", "status": status,
                        "date": dates[b].strftime("%Y-%m-%d"), "trend_before": "Downtrend",
                        "level": round(float(neck), 2),
                        "description": f"Two troughs near {min(l[a], l[b]):.2f}; a close above the peak at {neck:.2f} confirms."})
            break
    return out


def detect_all_patterns(df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    candles = detect_candlestick_patterns(df)
    charts = detect_chart_patterns(df)
    return {"candlestick": candles, "chart": charts, "all": candles + charts}
