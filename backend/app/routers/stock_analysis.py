from app.config import settings
from app.services.ttl_cache import ttl_cache
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import StockMaster
from app.services.stock_master import search_stocks, get_stock_by_symbol
from app.services.research_service import build_research_note
from app.services.macro_service import MacroService
from app.services.data_fetcher import DataFetcher
from app.sources.registry import SourceRegistry
from app.services.valuation_service import ValuationEngine
from app.services.peer_multiples import peers_for, top_peers_by_market_cap
from app.services.technical_service import TechnicalEngine
from app.services.market_pulse_service import MarketPulseService
from app.services.macro_service import MacroService

router = APIRouter(prefix="/stock-analysis", tags=["Stock Analysis"])

class DCFSimRequest(BaseModel):
    fcf_cr: float
    shares_cr: float
    growth_rate_stage1: float = 0.12
    growth_rate_stage2: float = 0.07
    terminal_growth: float = 0.045
    wacc: float = 0.115
    cash_cr: float = 0.0
    debt_cr: float = 0.0
    margin_of_safety_pct: float = 0.20

@router.get("/search")
def search_stock_autocomplete(
    q: Optional[str] = Query("", description="Company name or ticker"),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Local Nifty 500 master first, then Yahoo Finance symbol search so any listed equity
    (NSE, BSE, US, etc.) can be found. Results carry the full Yahoo symbol to analyse.
    """
    local = search_stocks(query=q, db=db, limit=15)
    seen = {r["symbol"] for r in local}
    results = list(local)
    if q and q.strip():
        for hit in DataFetcher.yahoo_symbol_search(q.strip(), limit=15):
            if hit["symbol"] not in seen:
                seen.add(hit["symbol"])
                results.append(hit)
    return results[:20]

@router.get("/overview/{symbol}")
def get_stock_overview(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    norm_sym = DataFetcher.normalize_symbol(symbol)
    stock_info = get_stock_by_symbol(norm_sym, db)
    # Source layer: fills missing ratios (P/E, P/B, EPS, book value) from statements when a quote source omits them
    fundamentals = SourceRegistry.from_settings().fundamentals(norm_sym)
    
    # Financials for valuation
    financials = DataFetcher.fetch_financial_statements(norm_sym)
    val_summary = ValuationEngine.calculate_valuation_summary(fundamentals, financials, peers_for(db, norm_sym, _num_mc(fundamentals)))
    # Show the same enterprise value the valuation uses (statement-based formula)
    ev_cr = (val_summary.get("valuation_multiples") or {}).get("enterprise_value_cr")
    if ev_cr:
        fundamentals["enterprise_value"] = ev_cr * 1e7
        ev_mult = (val_summary.get("valuation_multiples") or {}).get("ev_to_ebitda")
        if isinstance(ev_mult, (int, float)):
            fundamentals["enterprise_to_ebitda"] = ev_mult
    
    # Technical rating
    df = DataFetcher.fetch_history(norm_sym, period="6mo", interval="1d")
    tech_summary = TechnicalEngine.analyze(df) if not df.empty else {}
    
    # Upcoming corporate actions
    actions = MarketPulseService.get_corporate_actions(symbol=norm_sym)

    # Combined Verdict
    mos = val_summary.get("margin_of_safety_pct")
    mos_text = f"Margin of Safety: {mos:+.1f}%" if mos is not None else "Margin of Safety: n/a"
    verdict_text = (
        f"{fundamentals.get('company_name', norm_sym)} is rated **{val_summary.get('valuation_label')}** "
        f"({mos_text}) "
        f"with a **{tech_summary.get('overall_rating', 'Neutral')}** technical structure. "
        f"Quality score {val_summary.get('quality_scorecard', {}).get('quality_score', 'n/a')}/100."
    )

    return {
        "symbol": norm_sym,
        "name": fundamentals.get("company_name", norm_sym),
        "sector": fundamentals.get("sector", "Diversified"),
        "industry": fundamentals.get("industry", "Diversified"),
        "category": stock_info.market_cap_category if stock_info else "Large Cap",
        "fundamentals": fundamentals,
        "valuation_summary": {
            "blended_intrinsic_value": val_summary.get("intrinsic_value"),
            "primary_method": val_summary.get("primary_method"),
            "method_code": val_summary.get("method_code"),
            "method_rationale": val_summary.get("method_rationale"),
            "confidence": val_summary.get("confidence"),
            "margin_of_safety_pct": val_summary.get("margin_of_safety_pct"),
            "valuation_label": val_summary.get("valuation_label"),
            "verdict_color": val_summary.get("verdict_color"),
            "quality_score": val_summary.get("quality_scorecard", {}).get("quality_score"),
            "grade": val_summary.get("quality_scorecard", {}).get("grade")
        },
        "technical_summary": {
            "overall_rating": tech_summary.get("overall_rating", "Neutral"),
            "technical_score": tech_summary.get("technical_score", 50),
            "nearest_support": tech_summary.get("nearest_support"),
            "nearest_resistance": tech_summary.get("nearest_resistance"),
            "rating_color": tech_summary.get("rating_color", "blue")
        },
        "upcoming_actions": actions,
        "combined_verdict": verdict_text
    }

@router.get("/research/{symbol}")
def get_research_note(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Full equity research note: primary valuation method with cross-checks and sensitivity,
    technicals, stock-specific macro sentiment, and the triangulated Buy/Hold/Sell verdict.
    """
    return build_research_note(symbol, db=db)

@router.get("/valuation/{symbol}")
def get_stock_valuation(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    norm_sym = DataFetcher.normalize_symbol(symbol)
    # Source layer: fills missing ratios (P/E, P/B, EPS, book value) from statements when a quote source omits them
    fundamentals = SourceRegistry.from_settings().fundamentals(norm_sym)
    financials = DataFetcher.fetch_financial_statements(norm_sym)
    return ValuationEngine.calculate_valuation_summary(fundamentals, financials, peers_for(db, norm_sym, _num_mc(fundamentals)))

@router.post("/dcf-recalculate")
def recalculate_dcf(payload: DCFSimRequest) -> Dict[str, Any]:
    """
    Live DCF recalculation endpoint when user tweaks UI sliders.
    """
    return ValuationEngine.calculate_dcf(
        fcf_cr=payload.fcf_cr,
        shares_cr=payload.shares_cr,
        growth_rate_stage1=payload.growth_rate_stage1,
        growth_rate_stage2=payload.growth_rate_stage2,
        terminal_growth=payload.terminal_growth,
        wacc=payload.wacc,
        cash_cr=payload.cash_cr,
        debt_cr=payload.debt_cr,
        margin_of_safety_pct=payload.margin_of_safety_pct
    )

@router.get("/technical/{symbol}")
def get_stock_technicals(
    symbol: str,
    period: str = Query("1y", description="1mo, 3mo, 6mo, 1y, 2y, 5y"),
    interval: str = Query("1d", description="1d, 1wk, 1mo")
) -> Dict[str, Any]:
    norm_sym = DataFetcher.normalize_symbol(symbol)
    df = DataFetcher.fetch_history(norm_sym, period=period, interval=interval)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No OHLCV historical data found for {symbol}")

    analysis = TechnicalEngine.analyze(df)
    
    # Format Candlestick data for TradingView Lightweight Charts
    candlesticks = []
    for idx, row in df.iterrows():
        candlesticks.append({
            "time": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": float(row.get("Volume", 0))
        })

    analysis["candlesticks"] = candlesticks
    return analysis

@router.get("/financials/{symbol}")
def get_stock_financials(symbol: str) -> Dict[str, Any]:
    norm_sym = DataFetcher.normalize_symbol(symbol)
    return DataFetcher.fetch_financial_statements(norm_sym)

@router.get("/peers/{symbol}")
@ttl_cache(settings.CACHE_TTL_PRICES)
def get_stock_peers(symbol: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Top 10 companies in the same sector by market capitalisation, with their key multiples."""
    norm_sym = DataFetcher.normalize_symbol(symbol)
    rows = []
    for p in top_peers_by_market_cap(db, norm_sym, limit=10):
        try:
            q = DataFetcher.fetch_quote_and_fundamentals(p["symbol"])
        except Exception:
            q = {}
        rows.append({
            "symbol": p["symbol"],
            "name": q.get("company_name") or p["name"],
            "is_selected": p["is_selected"],
            "market_cap_cr": round(p["market_cap_inr"] / 1e7, 2),
            "price": q.get("current_price"),
            "change_1d_pct": q.get("change_1d_pct"),
            "trailing_pe": q.get("trailing_pe"),
            "price_to_book": q.get("price_to_book"),
            "ev_to_ebitda": q.get("enterprise_to_ebitda"),
            "return_on_equity": q.get("return_on_equity"),
            "change_1y_pct": q.get("change_1y_pct"),
        })
    return rows


def _num_mc(fund):
    try:
        v = float(fund.get("market_cap"))
        return v if v == v and v > 0 else None
    except (TypeError, ValueError):
        return None
