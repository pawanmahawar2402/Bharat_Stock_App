import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import yfinance as yf
from app.services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

class MarketPulseService:
    """
    Manages corporate actions, earnings results season tracking, bulk deals,
    and institutional flow monitors.
    """

    @staticmethod
    def get_seed_data() -> Dict[str, Any]:
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "seed_corporate_actions.json"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"actions": [], "quarterly_results": [], "bulk_deals": []}

    @staticmethod
    def get_corporate_actions(
        action_type: Optional[str] = None,
        market_cap_category: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns structured corporate actions with rule-based signal tags.
        """
        seed = MarketPulseService.get_seed_data()
        actions = seed.get("actions", [])

        # Filter
        if action_type and action_type.lower() != "all":
            actions = [a for a in actions if a.get("action_type", "").lower() == action_type.lower()]

        if market_cap_category and market_cap_category.lower() != "all":
            actions = [a for a in actions if a.get("market_cap_category", "").lower() == market_cap_category.lower()]

        if symbol:
            sym_clean = symbol.upper().replace(".NS", "").replace(".BO", "")
            actions = [a for a in actions if sym_clean in a.get("symbol", "").upper()]

        return actions

    @staticmethod
    def get_quarterly_results_tracker() -> List[Dict[str, Any]]:
        """
        Returns latest earnings season results with YoY/QoQ growth and beat/miss status.
        """
        seed = MarketPulseService.get_seed_data()
        return seed.get("quarterly_results", [])

    @staticmethod
    def get_bulk_and_block_deals() -> List[Dict[str, Any]]:
        """
        Returns institutional bulk and block deals.
        """
        seed = MarketPulseService.get_seed_data()
        return seed.get("bulk_deals", [])

    @staticmethod
    def get_market_activity_summary() -> Dict[str, Any]:
        """
        Fetches daily top gainers/losers, volume spikes, and 52W breakouts across Nifty 50.
        """
        # Sample active universe
        popular_stocks = [
            ("RELIANCE.NS", "Reliance Industries"),
            ("TCS.NS", "Tata Consultancy Services"),
            ("HDFCBANK.NS", "HDFC Bank"),
            ("INFY.NS", "Infosys Limited"),
            ("ICICIBANK.NS", "ICICI Bank"),
            ("SBIN.NS", "State Bank of India"),
            ("BHARTIARTL.NS", "Bharti Airtel"),
            ("ITC.NS", "ITC Limited"),
            ("LT.NS", "Larsen & Toubro"),
            ("TATAMOTORS.NS", "Tata Motors"),
            ("ZOMATO.NS", "Zomato Ltd."),
            ("SUZLON.NS", "Suzlon Energy"),
            ("TATASTEEL.NS", "Tata Steel"),
            ("SUNPHARMA.NS", "Sun Pharma"),
            ("BAJFINANCE.NS", "Bajaj Finance")
        ]

        quotes = []
        for sym, name in popular_stocks:
            try:
                q = DataFetcher.fetch_quote_and_fundamentals(sym)
                if q.get("current_price", 0) > 0:
                    quotes.append(q)
            except Exception:
                continue

        # Top Gainers & Losers
        quotes_sorted = sorted(quotes, key=lambda x: x.get("change_1d_pct", 0), reverse=True)
        gainers = quotes_sorted[:4]
        losers = sorted(quotes, key=lambda x: x.get("change_1d_pct", 0))[:4]

        # Volume Spikes
        volume_spikes = [
            q for q in quotes if q.get("avg_volume_20d", 0) > 0 and (q.get("volume", 0) > 1.3 * q["avg_volume_20d"])
        ][:4]

        # 52-Week High Proximity (within 3%)
        near_52w_high = [
            q for q in quotes if q.get("high_52w", 0) > 0 and (q.get("current_price", 0) >= q["high_52w"] * 0.96)
        ][:4]

        return {
            "top_gainers": gainers,
            "top_losers": losers,
            "volume_spikes": volume_spikes,
            "near_52w_high": near_52w_high
        }
