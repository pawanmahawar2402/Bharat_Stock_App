from fastapi import APIRouter, Depends
from typing import Dict, Any, List
from app.services.macro_service import MacroService
from app.services.research_service import stock_macro_sentiment
from app.services.data_fetcher import DataFetcher

router = APIRouter(prefix="/macro", tags=["Macro Economy Outlook"])

@router.get("/overview")
def get_macro_overview() -> Dict[str, Any]:
    """
    Returns complete Macro Economy Outlook data:
    1. 10 Yahoo Finance market indicators with sparklines
    2. Official macro indicators (RBI Repo, CPI, GDP, Forex, G-Sec, FII/DII)
    3. Macro Regime classification (Risk-On / Neutral / Risk-Off)
    4. Sector Rotation Heatmap
    5. AI-driven institutional narrative bullets
    """
    market_inds = MacroService.get_market_indicators()
    macro_data = MacroService.get_official_macro_indicators()
    regime = MacroService.calculate_regime_classification(market_inds, macro_data)
    sectors = MacroService.get_sector_rotation_heatmap()
    narrative = MacroService.generate_narrative(regime, market_inds, macro_data, sectors)

    return {
        "regime": regime,
        "market_indicators": market_inds,
        "macro_indicators": macro_data,
        "sector_heatmap": sectors,
        "narrative_bullets": narrative,
        "disclaimer": "For educational purposes only. Free/Yahoo data may be delayed or approximate. Not SEBI registered advice."
    }

@router.get("/sectors")
def get_sector_heatmap() -> List[Dict[str, Any]]:
    return MacroService.get_sector_rotation_heatmap()

@router.get("/regime")
def get_regime() -> Dict[str, Any]:
    market_inds = MacroService.get_market_indicators()
    macro_data = MacroService.get_official_macro_indicators()
    return MacroService.calculate_regime_classification(market_inds, macro_data)


@router.get("/stock-sentiment/{symbol}")
def get_stock_macro_sentiment(symbol: str) -> Dict[str, Any]:
    """
    Positive / negative macro sentiment for one stock, from current market indicators
    scored with the sector sensitivity profiles in config/sector_macro_profiles.json, scaled by beta and leverage, plus relative strength vs Nifty.
    """
    norm = DataFetcher.normalize_symbol(symbol)
    fund = DataFetcher.fetch_quote_and_fundamentals(norm)
    market_inds = MacroService.get_market_indicators()
    result = stock_macro_sentiment(fund, market_inds)
    result.update({"symbol": norm, "company_name": fund.get("company_name", norm),
                   "sector": fund.get("sector"), "industry": fund.get("industry")})
    return result
