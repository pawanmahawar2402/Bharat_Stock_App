"""
NSE daily price files (bhavcopy): high, low, close and volume for every equity on each trading day.
Used to apply the 52-week and volume rules to the whole market with about 250 file downloads,
instead of thousands of per-stock requests to Yahoo Finance.
"""
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import requests

from app.services.ttl_cache import ttl_cache

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
BHAV_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{ddmmyyyy}.csv"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*", "Referer": "https://www.nseindia.com/"}
TRADING_DAYS = 252
MAX_CALENDAR_DAYS = 420


@ttl_cache(6 * 3600)
def bhavcopy_series() -> Dict[str, List[Tuple[float, float, float, float]]]:
    """Per symbol, (high, low, close, volume) for each trading day, most recent first."""
    series: Dict[str, List[Tuple[float, float, float, float]]] = {}
    today = datetime.now(IST).date()
    got = 0
    for back in range(MAX_CALENDAR_DAYS):
        d = today - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        try:
            r = requests.get(BHAV_URL.format(ddmmyyyy=d.strftime("%d%m%Y")), headers=HEADERS, timeout=20)
        except Exception as e:
            logger.debug(f"bhavcopy {d} failed: {e}")
            continue
        if r.status_code != 200 or len(r.content) < 1000:
            continue  # market holiday or file not yet published
        got += 1
        reader = csv.reader(io.StringIO(r.text))
        header = [h.strip() for h in next(reader)]
        idx = {h: i for i, h in enumerate(header)}
        for row in reader:
            if len(row) < len(header) or row[idx["SERIES"]].strip() != "EQ":
                continue
            try:
                rec = (float(row[idx["HIGH_PRICE"]]), float(row[idx["LOW_PRICE"]]),
                       float(row[idx["CLOSE_PRICE"]]), float(row[idx["TTL_TRD_QNTY"]]))
            except ValueError:
                continue
            series.setdefault(row[idx["SYMBOL"]].strip(), []).append(rec)
        if got >= TRADING_DAYS:
            break
    logger.info(f"bhavcopy: {got} trading days loaded, {len(series)} equities")
    return series


def price_volume_survivors(names: Dict[str, str], below_high_max: float = 10.0, above_low_min: float = 50.0,
                           min_volume: float = 100_000) -> List[Tuple[str, str, str]]:
    """Symbols that pass the 52-week-high, 52-week-low and volume rules (all from NSE daily files)."""
    out = []
    for sym, recs in bhavcopy_series().items():
        if len(recs) < 60:
            continue
        window = recs[:TRADING_DAYS]
        last = recs[0][2]
        high = max(r[0] for r in window)
        low = min(r[1] for r in window)
        avg_vol = sum(r[3] for r in recs[:20]) / min(20, len(recs))
        if high <= 0 or low <= 0:
            continue
        below_high = 100.0 * (high - last) / high
        above_low = 100.0 * (last / low - 1.0)
        if 0 < below_high < below_high_max and above_low > above_low_min and avg_vol > min_volume:
            out.append((f"{sym}.NS", names.get(sym, sym), ""))
    return out
