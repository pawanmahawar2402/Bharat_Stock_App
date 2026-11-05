"""
Common interface every data source implements.

A source declares which capabilities it provides:
  "fundamentals" -> fetch_fundamentals(symbol, context) returns a snake_case dict (INR absolute)
  "history"      -> fetch_history(symbol, period, interval) returns an OHLCV DataFrame
  "statements"   -> fetch_statements(symbol) returns {income_statement, balance_sheet, cash_flow}

Sources may return None or partial data. The registry fills gaps from the next source, so a
source only needs to supply the fields it actually has.
"""
from abc import ABC
from typing import Any, Dict, Optional

import pandas as pd


class DataSource(ABC):
    name: str = "base"
    capabilities: frozenset = frozenset()

    def fetch_fundamentals(self, symbol: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def fetch_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        return None

    def fetch_statements(self, symbol: str) -> Optional[Dict[str, Any]]:
        return None
