from typing import Any, Dict, Optional

import pandas as pd

from app.sources.base import DataSource
from app.services.data_fetcher import DataFetcher


class YahooSource(DataSource):
    """Yahoo Finance via yfinance: quotes, ratios, OHLCV history and annual statements."""
    name = "yahoo"
    capabilities = frozenset({"fundamentals", "history", "statements"})

    def fetch_fundamentals(self, symbol: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return DataFetcher.fetch_quote_and_fundamentals(symbol)

    def fetch_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        return DataFetcher.fetch_history(symbol, period=period, interval=interval)

    def fetch_statements(self, symbol: str) -> Optional[Dict[str, Any]]:
        return DataFetcher.fetch_financial_statements(symbol)
