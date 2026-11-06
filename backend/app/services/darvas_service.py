"""
Darvas Box analysis (after Nicolas Darvas).

Rules implemented:
  * Box top    : a new high that is not exceeded for CONFIRM_DAYS consecutive sessions.
  * Box bottom : the lowest low after the top, not undercut for CONFIRM_DAYS sessions.
  * Breakout   : a session closes above a completed box top, ideally on volume expansion.
  * Stop-loss  : just below the box bottom.
  * Target     : measured move, i.e. box top plus the box height.

The scanner keeps only actionable setups: a breakout within the last few sessions, or price
pressing against the box top. It requires an intact long-term uptrend (close above the 200-day
average) and enough liquidity to trade the position.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

CONFIRM_DAYS = 3
LOOKBACK_BARS = 150          # search window for the most recent box
BOX_MAX_AGE = 60             # a box must have completed within this many sessions
BREAKOUT_FRESH_BARS = 3      # a breakout counts as live for this many sessions
NEAR_TOP_PCT = 0.03          # within 3% below the top = "near breakout"
MAX_BOX_HEIGHT_PCT = 25.0    # wider boxes are not Darvas-style tight consolidations
WATCHLIST_MAX_HEIGHT_PCT = 12.0     # watchlist: tight box only
WATCHLIST_MAX_DISTANCE_PCT = 10.0   # watchlist: price within 10% of the box top
VOLUME_CONFIRM_RATIO = 1.5   # breakout volume vs 20-day average
MIN_DAILY_TRADED_VALUE_INR = 1e8


def find_darvas_box(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Finds the most recent completed Darvas box and classifies the latest session.
    Returns None when no completed box exists in the lookback window.
    """
    if df is None or df.empty or len(df) < 30:
        return None
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)
    vol = df["Volume"].to_numpy(dtype=float) if "Volume" in df.columns else np.zeros(len(df))
    n = len(df)
    start = max(0, n - LOOKBACK_BARS)

    cur: Optional[Dict[str, Any]] = None
    stored_complete: Optional[Dict[str, Any]] = None  # last box that was finished before a new high began

    for i in range(start, n):
        if cur is None or high[i] > cur["top"]:
            if cur is not None and cur["complete"]:
                # Preserve the finished box; a close above its top marks a breakout.
                stored_complete = dict(cur)
                stored_complete["breakout_i"] = i if close[i] > cur["top"] else None
                if close[i] > cur["top"]:
                    avg_vol = vol[max(0, cur["top_i"] - 19):i].mean() if i > 0 else 0.0
                    stored_complete["breakout_volume_ratio"] = (
                        round(float(vol[i] / avg_vol), 2) if avg_vol and avg_vol > 0 else None)
            cur = {"top": high[i], "top_i": i, "since_top": 0, "confirmed": False,
                   "bottom": None, "bottom_i": None, "since_bottom": 0, "complete": False}
            continue

        if not cur["confirmed"]:
            cur["since_top"] += 1
            if cur["since_top"] >= CONFIRM_DAYS:
                cur["confirmed"] = True
                seg = low[cur["top_i"] + 1:i + 1]
                if len(seg):
                    j = cur["top_i"] + 1 + int(np.argmin(seg))
                    cur["bottom"], cur["bottom_i"] = float(low[j]), j
                    cur["since_bottom"] = i - j
        elif not cur["complete"]:
            # Bottom is only discovered while the box forms; once complete it is fixed,
            # so a later lower low is read as a breakdown rather than a new bottom.
            if low[i] < cur["bottom"]:
                cur["bottom"], cur["bottom_i"], cur["since_bottom"] = float(low[i]), i, 0
            else:
                cur["since_bottom"] += 1
        if cur["confirmed"] and not cur["complete"] and cur["since_bottom"] >= CONFIRM_DAYS:
            cur["complete"] = True
            cur["end_i"] = i

    # Choose the most recent completed box
    box = None
    if cur is not None and cur["complete"]:
        box = dict(cur)
        box["breakout_i"] = None
        box["breakout_volume_ratio"] = None
    elif stored_complete is not None:
        box = stored_complete
    if box is None:
        return None

    end_i = box.get("end_i", box["bottom_i"])
    if (n - 1) - end_i > BOX_MAX_AGE:
        return None

    top, bottom = box["top"], box["bottom"]
    height_pct = (top - bottom) / top * 100
    last = float(close[-1])
    breakout_i = box.get("breakout_i")
    fresh_breakout = breakout_i is not None and (n - 1 - breakout_i) <= BREAKOUT_FRESH_BARS

    if last < bottom:
        status = "Breakdown"
    elif last > top and fresh_breakout:
        status = "Breakout"
    elif last > top:
        status = "Extended above box"
    elif last >= top * (1 - NEAR_TOP_PCT):
        status = "Near breakout"
    else:
        status = "Inside box"

    return {
        "status": status,
        "box_top": round(top, 2),
        "box_bottom": round(bottom, 2),
        "box_height_pct": round(height_pct, 2),
        "box_top_date": df.index[box["top_i"]].strftime("%Y-%m-%d"),
        "box_bottom_date": df.index[box["bottom_i"]].strftime("%Y-%m-%d"),
        "breakout_date": df.index[breakout_i].strftime("%Y-%m-%d") if breakout_i is not None else None,
        "breakout_volume_ratio": box.get("breakout_volume_ratio"),
        "last_close": round(last, 2),
        "stop_loss": round(bottom * 0.995, 2),
        "target": round(top + (top - bottom), 2),
        "distance_to_top_pct": round((top - last) / top * 100, 2),
    }


def darvas_trade_plan(d: Dict[str, Any]) -> Dict[str, Any]:
    """Entry at the box top (breakout) or the last close, stop below the box, target = measured move."""
    entry = d["box_top"] if d["status"] in ("Near breakout", "Inside box") else d["last_close"]
    risk = entry - d["stop_loss"]
    rr = round((d["target"] - entry) / risk, 2) if risk > 0 else None
    return {"entry": round(entry, 2), "stop_loss": d["stop_loss"], "target": d["target"],
            "risk_reward": rr,
            "rule": ("Buy on a close above the box top with volume expansion; stop just below the box bottom."
                     if d["status"] != "Breakout" else
                     "Breakout already triggered; enter only with the stop at the box bottom, or wait for a retest of the top.")}


def _chart_breakout_signal(df: pd.DataFrame) -> str:
    """Confirmed chart-pattern breakout on the same history, or blank."""
    from app.services.technical_patterns import detect_chart_patterns
    for p in detect_chart_patterns(df):
        if p.get("status") == "Confirmed":
            return f"{p['pattern']} breakout"
    return ""


def score_darvas(d: Dict[str, Any], trend_ok: bool, rs_1m_vs_nifty: Optional[float]) -> float:
    base = {"Breakout": 60.0, "Near breakout": 45.0, "Inside box": 20.0}.get(d["status"], 0.0)
    vol = d.get("breakout_volume_ratio") or 0.0
    base += min(vol, 3.0) * 8.0
    if d["box_height_pct"] <= 10:
        base += 15.0
    elif d["box_height_pct"] <= 18:
        base += 6.0
    if rs_1m_vs_nifty is not None:
        base += max(-10.0, min(10.0, rs_1m_vs_nifty / 2.0))
    return round(base + (10.0 if trend_ok else 0.0), 1)


class DarvasScanner:
    @staticmethod
    def analyse(symbol: str, nifty_1m: Optional[float], history_loader=None) -> Optional[Dict[str, Any]]:
        loader = history_loader or (lambda s: DataFetcher.fetch_history(s, period="1y", interval="1d"))
        df = loader(symbol)
        if df is None or df.empty or len(df) < 60:
            return None
        close = df["Close"]
        last = float(close.iloc[-1])
        turnover = float(df["Volume"].tail(20).mean() * last) if "Volume" in df.columns else 0.0
        if turnover < MIN_DAILY_TRADED_VALUE_INR:
            return None
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float(close.mean())
        trend_ok = last > sma200

        box = find_darvas_box(df)
        if box is None or box["status"] not in ("Breakout", "Near breakout", "Inside box"):
            return None
        if not trend_ok or box["box_height_pct"] > MAX_BOX_HEIGHT_PCT:
            return None
        if box["status"] == "Inside box":
            # Watchlist tier: tight box, price drifting toward the top, not yet triggered
            if box["box_height_pct"] > WATCHLIST_MAX_HEIGHT_PCT or box["distance_to_top_pct"] > WATCHLIST_MAX_DISTANCE_PCT:
                return None
        stock_1m = (last / float(close.iloc[-22]) - 1) * 100 if len(close) >= 22 else None
        rs = (stock_1m - nifty_1m) if (stock_1m is not None and nifty_1m is not None) else None
        plan = darvas_trade_plan(box)
        # Risk:reward is reported but not gated: with the box top as entry and the measured move
        # as target it is structurally ~1.0, and Darvas managed winners with a trailing stop.
        if plan["risk_reward"] is None:
            return None
        return {
            "symbol": symbol,
            "status": box["status"],
            "signal": _chart_breakout_signal(df),
            "tier": "Actionable" if box["status"] in ("Breakout", "Near breakout") else "Watchlist (not triggered)",
            "score": score_darvas(box, trend_ok, rs),
            "trend_above_200dma": trend_ok,
            "box": box,
            "plan": plan,
            "relative_strength_1m_vs_nifty": round(rs, 2) if rs is not None else None,
        }

    @staticmethod
    def scan(symbols_with_meta: List[Tuple[str, str, str]], nifty_1m: Optional[float], workers: int = 6,
             history_loader=None) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        analysed = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(DarvasScanner.analyse, sym, nifty_1m, history_loader): (sym, name, sector)
                       for sym, name, sector in symbols_with_meta}
            for fut in as_completed(futures):
                sym, name, sector = futures[fut]
                try:
                    res = fut.result()
                    analysed += 1
                    if res:
                        res.update({"company_name": name, "sector": sector})
                        results.append(res)
                except Exception as e:
                    logger.error(f"Darvas analysis failed for {sym}: {e}")
        results.sort(key=lambda r: r["score"], reverse=True)
        return {"considered": len(symbols_with_meta), "analysed": analysed,
                "setups_found": len(results), "picks": results[:10]}
