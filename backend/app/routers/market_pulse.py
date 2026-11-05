from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional
from app.services.market_pulse_service import MarketPulseService

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
