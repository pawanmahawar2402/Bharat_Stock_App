"""
Source registry: runs enabled sources in priority order and merges their output.

Merge rule: for each field, the first source that supplies a usable value wins; later
sources only fill fields still missing. Missing means None, NaN, or the string "N/A".
Every merged result records which source supplied each field (field_sources).
"""
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.config import settings
from app.sources.base import DataSource
from app.sources.statement_source import StatementDerivedSource
from app.sources.yahoo_source import YahooSource

logger = logging.getLogger(__name__)

AVAILABLE_SOURCES = {
    "yahoo": YahooSource,
    "statement_derived": StatementDerivedSource,
}


def _missing(v: Any) -> bool:
    if v is None or v == "N/A":
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return False


class SourceRegistry:
    def __init__(self, sources: List[DataSource]):
        self.sources = sources

    @classmethod
    def from_settings(cls) -> "SourceRegistry":
        names = [n.strip() for n in settings.DATA_SOURCES.split(",") if n.strip()]
        built = []
        for n in names:
            if n in AVAILABLE_SOURCES:
                built.append(AVAILABLE_SOURCES[n]())
            else:
                logger.warning(f"DATA_SOURCES contains unknown source '{n}'; skipped.")
        return cls(built)

    def _with(self, capability: str) -> List[DataSource]:
        return [s for s in self.sources if capability in s.capabilities]

    def statements(self, symbol: str) -> Optional[Dict[str, Any]]:
        for src in self._with("statements"):
            try:
                data = src.fetch_statements(symbol)
                if data and any(data.get(k) for k in ("income_statement", "balance_sheet", "cash_flow")):
                    return data
            except Exception as e:
                logger.warning(f"{src.name} statements failed for {symbol}: {e}")
        return None

    def fundamentals(self, symbol: str) -> Dict[str, Any]:
        return self.fundamentals_with_statements(symbol)[0]

    def fundamentals_with_statements(self, symbol: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        merged: Dict[str, Any] = {}
        provenance: Dict[str, str] = {}
        used: List[str] = []
        stmts = None
        if any("statements" in s.capabilities for s in self.sources):
            stmts = self.statements(symbol)
        for src in self._with("fundamentals"):
            ctx = dict(merged)
            ctx["_statements"] = stmts
            try:
                data = src.fetch_fundamentals(symbol, ctx)
            except Exception as e:
                logger.warning(f"{src.name} fundamentals failed for {symbol}: {e}")
                continue
            if not data:
                continue
            contributed = False
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                if _missing(merged.get(k)) and not _missing(v):
                    merged[k] = v
                    provenance[k] = src.name
                    contributed = True
            if contributed:
                used.append(src.name)
        merged.setdefault("symbol", symbol)
        merged["field_sources"] = provenance
        merged["sources_used"] = used
        return merged, stmts

    def history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        for src in self._with("history"):
            try:
                df = src.fetch_history(symbol, period=period, interval=interval)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"{src.name} history failed for {symbol}: {e}")
        return pd.DataFrame()
