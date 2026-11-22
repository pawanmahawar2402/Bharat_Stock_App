from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional
import threading
from app.services.market_pulse_service import MarketPulseService
from app.services import corporate_actions as ca
from app.db.session import SessionLocal
from app.db.models import StockMaster

router = APIRouter(prefix="/market-pulse", tags=["Market Pulse & Corporate Actions"])

@router.get("/actions")
def get_corporate_actions(
    action_type: Optional[str] = Query(None, description="Filter by Dividend, Split, Bonus, Buyback, Earnings, Board Meeting"),
    market_cap: Optional[str] = Query(None, description="Filter by Large Cap, Mid Cap, Small Cap"),
    symbol: Optional[str] = Query(None, description="Filter by stock symbol")
) -> List[Dict[str, Any]]:
    return MarketPulseService.get_corporate_actions(
        action_type=action_type,
        market_cap_category=market_cap,
        symbol=symbol
    )

@router.get("/results")
def get_quarterly_results() -> List[Dict[str, Any]]:
    return MarketPulseService.get_quarterly_results_tracker()

@router.get("/deals")
def get_bulk_deals() -> List[Dict[str, Any]]:
    return MarketPulseService.get_bulk_and_block_deals()

@router.get("/activity")
def get_market_activity() -> Dict[str, Any]:
    return MarketPulseService.get_market_activity_summary()


@router.post("/actions/refresh")
def refresh_corporate_actions() -> Dict[str, Any]:
    """Starts a background refresh of the last 120 days of dividends and splits for the Nifty 500."""
    if ca.status().get("state") == "running":
        return {"started": False, "status": ca.status()}
    def job():
        db = SessionLocal()
        try:
            members = [(r.symbol, r.name) for r in db.query(StockMaster).filter(StockMaster.is_nifty500 == True).all()]
        finally:
            db.close()
        ca.refresh(members)
    threading.Thread(target=job, daemon=True).start()
    return {"started": True, "status": ca.status()}

@router.get("/actions/status")
def corporate_actions_status() -> Dict[str, Any]:
    return ca.status()
