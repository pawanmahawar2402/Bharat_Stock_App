"""
Recent corporate actions (dividends and stock splits) for the Nifty 500, from Yahoo Finance's
dividend and split history. A refresh job stores the last LOOKBACK_DAYS of events in
data/corporate_actions.json; the Market Pulse page reads only that recent file.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 120
STORE = Path(__file__).resolve().parents[3] / "data" / "corporate_actions.json"
_lock = threading.Lock()
_status: Dict[str, Any] = {"state": "idle", "updated": None, "count": 0, "error": None}


def _recent(series: pd.Series, cutoff: pd.Timestamp) -> List[tuple]:
    if series is None or series.empty:
        return []
    out = []
    for ts, value in series.items():
        t = pd.Timestamp(ts)
        if t.tzinfo is not None:
            t = t.tz_convert(None)
        if t >= cutoff and value:
            out.append((t.strftime("%Y-%m-%d"), float(value)))
    return out


def _events_for(symbol: str, name: str, cutoff: pd.Timestamp) -> List[Dict[str, Any]]:
    t = yf.Ticker(symbol)
    rows = []
    for date, amount in _recent(t.dividends, cutoff):
        rows.append({"symbol": symbol.replace(".NS", ""), "company_name": name, "action_type": "Dividend",
                     "details": f"Dividend of ₹{amount:.2f} per share", "ex_date": date,
                     "record_date": None, "signal": "Neutral", "signal_reason": "Cash distribution to shareholders."})
    for date, ratio in _recent(t.splits, cutoff):
        rows.append({"symbol": symbol.replace(".NS", ""), "company_name": name, "action_type": "Split",
                     "details": f"Stock split, {ratio:g} new shares for each share held", "ex_date": date,
                     "record_date": None, "signal": "Neutral", "signal_reason": "Share count change; price adjusts."})
    return rows


def refresh(members: List[tuple], workers: int = 2) -> Dict[str, Any]:
    """Fetches recent events for (symbol, name) pairs and saves them. Runs once at a time."""
    if not _lock.acquire(blocking=False):
        return dict(_status)
    try:
        _status.update({"state": "running", "error": None})
        cutoff = pd.Timestamp(datetime.now(timezone.utc).date() - timedelta(days=LOOKBACK_DAYS))
        events: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_events_for, sym, name, cutoff): sym for sym, name in members}
            for fut in as_completed(futures):
                try:
                    events.extend(fut.result())
                except Exception as e:
                    logger.debug(f"corporate actions failed for {futures[fut]}: {e}")
        events.sort(key=lambda e: e["ex_date"], reverse=True)
        for i, e in enumerate(events):
            e["id"] = f"ca-{i}"
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "events": events}
        STORE.parent.mkdir(parents=True, exist_ok=True)
        with open(STORE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        _status.update({"state": "idle", "updated": payload["generated_at"], "count": len(events)})
        return dict(_status)
    except Exception as e:
        _status.update({"state": "error", "error": str(e)})
        raise
    finally:
        _lock.release()


def recent_events(symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Events from the stored refresh, limited to the last LOOKBACK_DAYS."""
    if not STORE.exists():
        return []
    with open(STORE, "r", encoding="utf-8") as f:
        events = json.load(f).get("events", [])
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    events = [e for e in events if e.get("ex_date", "") >= cutoff]
    if symbol:
        sym = symbol.upper().replace(".NS", "").replace(".BO", "")
        events = [e for e in events if e["symbol"].upper() == sym]
    return events


def status() -> Dict[str, Any]:
    return dict(_status)
