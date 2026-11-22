"""
Beta from price history: covariance of the stock's daily returns with the Nifty 50's, over one year.
Used only when the quote source has no beta (for example when Yahoo's company data is unavailable).
"""
from typing import Any, Dict, Optional

import numpy as np

from app.sources.base import DataSource
from app.services.data_fetcher import DataFetcher

NIFTY = "^NSEI"


class HistoryBetaSource(DataSource):
    name = "history_beta"
    capabilities = frozenset({"fundamentals"})

    def fetch_fundamentals(self, symbol: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        stock = DataFetcher.fetch_history(symbol, period="1y", interval="1d")
        market = DataFetcher.fetch_history(NIFTY, period="1y", interval="1d")
        if stock is None or market is None or stock.empty or market.empty:
            return None
        r_s = stock["Close"].pct_change().dropna()
        r_m = market["Close"].pct_change().dropna()
        joined = r_s.to_frame("s").join(r_m.to_frame("m"), how="inner").dropna()
        if len(joined) < 60:
            return None
        var_m = float(np.var(joined["m"], ddof=1))
        if var_m <= 0:
            return None
        beta = float(np.cov(joined["s"], joined["m"], ddof=1)[0, 1] / var_m)
        return {"beta": round(beta, 3)}
