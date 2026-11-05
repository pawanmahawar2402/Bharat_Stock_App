from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.services.swing_service import SwingScanner

router = APIRouter(prefix="/swing-scanner", tags=["Top Picks for Short-Term Profit Booking"])

class WatchlistAlertRequest(BaseModel):
    symbols: List[str]

@router.get("/picks")
def get_swing_picks(
    regime: str = Query("Risk-On", description="Macro Regime (Risk-On / Neutral / Risk-Off)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns filtered short-term swing trade setups across the liquid NSE universe.
    """
    picks = SwingScanner.run_scan(db=db, macro_regime=regime)
    return {
        "macro_regime_used": regime,
        "total_picks": len(picks),
        "picks": picks,
        "min_risk_reward": 1.5,
        "disclaimer": "Short-term swing setups involve market risk. Strictly respect ATR-based stop losses."
    }

@router.get("/backtest")
def get_backtest_stats() -> Dict[str, Any]:
    """
    Returns 2-year empirical backtest metrics for each setup type.
    """
    return SwingScanner.get_backtest_statistics()

@router.post("/watchlist-alerts")
def get_watchlist_alerts(payload: WatchlistAlertRequest) -> List[Dict[str, Any]]:
    """
    Checks if any watchlist stocks triggered profit-booking or stop-loss alerts.
    """
    return SwingScanner.check_watchlist_alerts(payload.symbols)
