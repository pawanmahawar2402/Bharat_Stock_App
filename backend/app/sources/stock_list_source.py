"""
Sector and industry from the bundled Nifty 500 list (data/nifty500.csv).
Used only to fill sector/industry when the quote source has none, so banks and insurers are
classified correctly even when Yahoo's company profile is unavailable.
"""
import csv
import functools
from pathlib import Path
from typing import Any, Dict, Optional

from app.sources.base import DataSource

_CSV = Path(__file__).resolve().parents[3] / "data" / "nifty500.csv"


@functools.lru_cache(maxsize=1)
def _industry_by_symbol() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not _CSV.exists():
        return out
    with open(_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("Symbol") or "").strip().upper()
            if sym:
                out[sym] = (row.get("Industry") or "").strip()
    return out


class StockListSource(DataSource):
    name = "stock_list"
    capabilities = frozenset({"fundamentals"})

    def fetch_fundamentals(self, symbol: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        base = symbol.upper().split(".")[0]
        industry = _industry_by_symbol().get(base)
        if not industry:
            return None
        title = industry.title()
        return {"sector": title, "industry": title}
