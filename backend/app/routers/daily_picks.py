import threading
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.db.session import get_db
from app.services.daily_picks_service import DailyPicksEngine, ist_today

router = APIRouter(prefix="/daily-picks", tags=["Daily Two Picks"])


@router.get("/today")
def get_today_picks(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Latest persisted two-pick shortlist (today's if generated, otherwise the most recent),
    plus the state of any run in progress.
    """
    latest = DailyPicksEngine.latest(db)
    return {
        "today_ist": ist_today(),
        "is_current": bool(latest and latest.get("date") == ist_today()),
        "status": DailyPicksEngine.status(),
        "result": latest,
    }


@router.post("/refresh")
def refresh_picks() -> Dict[str, Any]:
    """Starts a background run of the screen. Returns immediately; poll /today for the result."""
    status = DailyPicksEngine.status()
    if status.get("state") == "running":
        return {"started": False, "reason": "A run is already in progress.", "status": status}
    threading.Thread(target=DailyPicksEngine.run_safe, daemon=True).start()
    return {"started": True, "reason": "Run started in the background.", "status": DailyPicksEngine.status()}
