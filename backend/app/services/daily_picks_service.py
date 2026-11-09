"""
Best Recommended Picks: the strongest names from today's screen, refreshed once per trading day.
Only the ranked names and their trade levels are stored and returned.
"""

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DailyPickModel, StockMaster
from app.db.session import SessionLocal
from app.services.darvas_service import DarvasScanner
from app.services.macro_service import MacroService
from app.sources.registry import SourceRegistry

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
PICK_COUNT = 10
DISCLAIMER = "Model-generated research shortlist for education. Not SEBI-registered advice. Verify before trading."


def ist_today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _pick_rows(scan: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for i, d in enumerate(scan.get("picks", [])[:PICK_COUNT], 1):
        plan = d.get("plan") or {}
        box = d.get("box") or {}
        rows.append({
            "rank": i,
            "symbol": d["symbol"],
            "company_name": d.get("company_name", d["symbol"]),
            "sector": d.get("sector", ""),
            "signal": d.get("signal", ""),
            "current_price": box.get("last_close"),
            "entry": plan.get("entry"),
            "stop_loss": plan.get("stop_loss"),
            "target": plan.get("target"),
        })
    return rows


class DailyPicksEngine:
    _lock = threading.Lock()
    _status: Dict[str, Any] = {"state": "idle", "started_at": None, "finished_at": None,
                               "processed": 0, "total": 0, "error": None}

    @classmethod
    def status(cls) -> Dict[str, Any]:
        return dict(cls._status)

    @staticmethod
    def universe(db: Session, limit: int) -> List[tuple]:
        rows = (db.query(StockMaster)
                .filter(StockMaster.is_nifty500 == True, StockMaster.is_active == True)
                .order_by(StockMaster.symbol).limit(limit).all())
        return [(r.symbol, r.name, r.sector or "") for r in rows]

    @classmethod
    def run(cls, db: Session, universe_size: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Screens the universe, stores today's list, and returns it. Returns None if a run is already in progress."""
        if not cls._lock.acquire(blocking=False):
            return None
        try:
            universe = cls.universe(db, universe_size or settings.DAILY_UNIVERSE_SIZE)
            cls._status.update({"state": "running", "started_at": datetime.utcnow().isoformat(),
                                "finished_at": None, "processed": 0, "total": len(universe), "error": None})

            market_inds = MacroService.get_market_indicators()
            nifty_1m = next((m.get("change_1m_pct") for m in market_inds if m.get("name") == "Nifty 50"), None)
            reg = SourceRegistry.from_settings()
            scan = DarvasScanner.scan(universe, nifty_1m, history_loader=lambda s: reg.history(s, "1y", "1d"))

            payload = {
                "date": ist_today(),
                "generated_at": datetime.now(IST).isoformat(),
                "picks": _pick_rows(scan),
                "disclaimer": DISCLAIMER,
            }

            row = db.query(DailyPickModel).filter(DailyPickModel.date_key == payload["date"]).first()
            if row is None:
                row = DailyPickModel(date_key=payload["date"])
                db.add(row)
            row.generated_at = datetime.utcnow()
            row.payload = json.dumps(payload)
            row.eligible_count = len(payload["picks"])
            db.commit()

            cls._status.update({"state": "idle", "processed": len(universe),
                                "finished_at": datetime.utcnow().isoformat()})
            return payload
        except Exception as e:
            logger.exception("Best picks run failed")
            cls._status.update({"state": "error", "error": str(e), "finished_at": datetime.utcnow().isoformat()})
            raise
        finally:
            cls._lock.release()

    @classmethod
    def run_safe(cls) -> None:
        """Entry point for the scheduler and background threads (owns its DB session)."""
        db = SessionLocal()
        try:
            cls.run(db)
        except Exception:
            pass
        finally:
            db.close()

    @staticmethod
    def latest(db: Session) -> Optional[Dict[str, Any]]:
        row = db.query(DailyPickModel).order_by(DailyPickModel.date_key.desc()).first()
        return json.loads(row.payload) if row else None
