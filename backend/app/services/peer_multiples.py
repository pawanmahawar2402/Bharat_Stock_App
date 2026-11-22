"""
Sector peer multiples (median P/E, P/B, EV/EBITDA, P/S) for relative valuation.
Peers come from the same sector group in the stock list, excluding the company being valued.
Results are cached, so the cost is paid once per peer set rather than on every page view.
"""
import logging
import statistics
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models import StockMaster
from app.services.data_fetcher import DataFetcher
from app.services.ttl_cache import ttl_cache
from app.sources.registry import SourceRegistry

logger = logging.getLogger(__name__)

# Sanity bounds: multiples outside these are data errors or distorted by one-off earnings
BOUNDS = {"pe": (3.0, 80.0), "pb": (0.3, 20.0), "ev_ebitda": (3.0, 60.0), "ps": (0.2, 30.0)}
SOURCE_KEYS = {"pe": "trailing_pe", "pb": "price_to_book", "ev_ebitda": "enterprise_to_ebitda", "ps": "price_to_sales"}


def peer_symbols(db: Session, group: Optional[str], exclude: str, limit: int = 8) -> List[str]:
    if not group or group == "Diversified":
        return []
    rows = (db.query(StockMaster)
            .filter(StockMaster.sector == group, StockMaster.symbol != exclude, StockMaster.is_active == True)
            .limit(limit).all())
    return [r.symbol for r in rows]


def _num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


SIZE_BAND = (0.25, 4.0)   # peers within a quarter to four times the company's market cap


@ttl_cache(6 * 3600)
def multiples_for(symbols: Tuple[str, ...], market_cap_inr: Optional[float] = None) -> Dict[str, Optional[float]]:
    """
    Median of each multiple across peers that report a sensible value (needs at least two).
    With a market cap given, only peers of comparable size are used.
    """
    values: Dict[str, List[float]] = {k: [] for k in BOUNDS}
    for sym in symbols:
        try:
            # Same source chain as the company itself, so peers keep their statement-derived ratios
            f = SourceRegistry.from_settings().fundamentals(sym)
        except Exception as e:
            logger.debug(f"peer fetch failed for {sym}: {e}")
            continue
        if market_cap_inr:
            mc = _num(f.get("market_cap"))
            if not mc or not (SIZE_BAND[0] * market_cap_inr <= mc <= SIZE_BAND[1] * market_cap_inr):
                continue
        for key, field in SOURCE_KEYS.items():
            v = _num(f.get(field))
            lo, hi = BOUNDS[key]
            if v is not None and lo <= v <= hi:
                values[key].append(v)
    return {k: (round(statistics.median(v), 2) if len(v) >= 2 else None) for k, v in values.items()}


def peers_for(db: Session, symbol: str, market_cap_inr: Optional[float] = None) -> Dict[str, Optional[float]]:
    """Sector peer medians for one company (same sector group, comparable size)."""
    master = db.query(StockMaster).filter(StockMaster.symbol == symbol).first()
    group = master.sector if master and master.sector else None
    syms = peer_symbols(db, group, symbol, limit=12)
    return multiples_for(tuple(syms), market_cap_inr) if syms else {}


@ttl_cache(3600)
def market_cap_of(symbol: str) -> Optional[float]:
    """Market capitalisation in INR from Yahoo's quick quote (cheap; cached for an hour)."""
    try:
        import yfinance as yf
        value = yf.Ticker(symbol).fast_info["market_cap"]
        return float(value) if value else None
    except Exception:
        return None


def top_peers_by_market_cap(db: Session, symbol: str, limit: int = 10) -> List[Dict]:
    """The largest companies in the same sector group, ranked by market capitalisation."""
    master = db.query(StockMaster).filter(StockMaster.symbol == symbol).first()
    group = master.sector if master and master.sector else None
    if not group or group == "Diversified":
        return []
    members = (db.query(StockMaster)
               .filter(StockMaster.sector == group, StockMaster.is_active == True).all())
    caps = []
    for m in members:
        mc = market_cap_of(m.symbol)
        if mc:
            caps.append((mc, m.symbol, m.name))
    caps.sort(reverse=True)
    return [{"symbol": sym, "name": name, "market_cap_inr": mc, "is_selected": sym == symbol}
            for mc, sym, name in caps[:limit]]
