"""
Daily Two Picks engine.

Every evening the engine screens the Nifty 500 universe and selects the two stocks with the
strongest triangulated case (fundamental valuation + quality, technical trend, macro regime).
Picks must clear hard gates before they are ranked; if fewer than two pass, the engine
reports fewer rather than padding the list.

Results are persisted once per IST trading date in the `daily_picks` table.
"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DailyPickModel, StockMaster
from app.db.session import SessionLocal
from app.services import fundamental_engine as fe
from app.services.data_fetcher import DataFetcher
from app.services.darvas_service import DarvasScanner
from app.sources.registry import SourceRegistry
from app.services.macro_service import MacroService
from app.services.research_service import stock_macro_sentiment, triangulate
from app.services.technical_service import TechnicalEngine
from app.services.valuation_service import ValuationEngine

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# Hard gates applied before ranking
MIN_MARGIN_OF_SAFETY_PCT = 15.0
MIN_QUALITY_SCORE = 55
MIN_TECHNICAL_SCORE = 55
MIN_COMPOSITE = 60.0
MIN_RISK_REWARD = 1.5
MIN_DAILY_TRADED_VALUE_INR = 1e8     # Rs 10 crore average daily turnover (liquidity gate)


def ist_today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def build_trade_plan(cmp: float, atr: float, nearest_resistance: Optional[float],
                     intrinsic: Optional[float]) -> Optional[Dict[str, Any]]:
    """
    Stop = 2 x ATR below entry (capped at 10%).
    Target 1 = nearest technical resistance (if >= 3% away) else 2R.
    Target 2 = intrinsic value from the valuation model (if above Target 1) else 3R.
    """
    if cmp <= 0 or atr <= 0:
        return None
    risk = min(2.0 * atr, 0.10 * cmp)
    stop = round(cmp - risk, 2)
    risk = cmp - stop

    t1 = nearest_resistance if (nearest_resistance and nearest_resistance >= cmp * 1.03) else cmp + 2 * risk
    t1 = round(t1, 2)
    t2 = round(intrinsic, 2) if (intrinsic and intrinsic > t1) else round(cmp + 3 * risk, 2)
    rr = round((t1 - cmp) / risk, 2) if risk > 0 else 0.0
    return {
        "entry_zone": f"Rs {cmp * 0.995:,.2f} - Rs {cmp * 1.005:,.2f}",
        "entry_min": round(cmp * 0.995, 2),
        "entry_max": round(cmp * 1.005, 2),
        "stop_loss": stop,
        "stop_loss_pct": round((stop - cmp) / cmp * 100, 2),
        "target_1": t1,
        "target_1_pct": round((t1 - cmp) / cmp * 100, 2),
        "target_2": t2,
        "target_2_pct": round((t2 - cmp) / cmp * 100, 2),
        "risk_reward": rr,
        "holding_period": "1-3 months (valuation convergence)" if intrinsic else "2-4 weeks",
        "profit_plan": (f"Book 50% at Target 1 (Rs {t1:,.2f}), trail stop to breakeven, "
                        f"hold the rest toward Target 2 (Rs {t2:,.2f})."),
    }


def _summary_message(picks: List[Dict[str, Any]], candidates: List[Dict[str, Any]]) -> str:
    if not picks:
        return ("No stock cleared every gate with High conviction today, so no picks are recommended. "
                "See the Darvas Box list for technical setups.")
    if len(picks) == 1:
        return ("Only one stock cleared every gate with High conviction today. "
                "No second pick is recommended.")
    return "Both picks cleared every gate with High conviction."


def _pattern_signal(tech: Dict[str, Any]) -> str:
    """Only a confirmed chart-pattern breakout (head and shoulders, double top/bottom) is reported."""
    for p in tech.get("chart_patterns", []) or []:
        if p.get("status") == "Confirmed":
            return f"{p['pattern']} breakout"
    return ""


def _thesis_points(val: Dict[str, Any], tech: Dict[str, Any], sentiment: Dict[str, Any], tri: Dict[str, Any]) -> List[str]:
    pts = []
    pts.append(f"Intrinsic value Rs {val.get('intrinsic_value'):,.2f} "
               f"vs CMP, a {val.get('margin_of_safety_pct'):.1f}% margin of safety.")
    qm = val.get("quality_scorecard", {}).get("quality_metrics", {})
    if qm.get("roe_pct") is not None:
        pts.append(f"Quality: ROE {qm['roe_pct']:.1f}%, ROCE {qm.get('roce_pct', 'n/a')}%, "
                   f"D/E {qm.get('debt_to_equity', 'n/a')}, Piotroski {val.get('quality_scorecard', {}).get('piotroski_f_score')}/"
                   f"{val.get('quality_scorecard', {}).get('piotroski_max')}.")
    bullish = [s for s in tech.get("signals", []) if s.get("type", "").startswith("Bullish")][:2]
    if bullish:
        pts.append("Technicals: " + "; ".join(s["desc"] for s in bullish) + ".")
    pts.append(f"Triangulated score {tri['composite_score']:.0f}/100 ({tri['action']}, evidence {tri['agreement'].lower()}).")
    if sentiment.get("factors"):
        pos = [f["explanation"] for f in sentiment["factors"] if f["stance"] == "positive"][:1]
        if pos:
            pts.append("Macro tailwind: " + pos[0])
    return pts


def _risk_points(val: Dict[str, Any], tech: Dict[str, Any], sentiment: Dict[str, Any]) -> List[str]:
    risks = []
    for g in val.get("data_gaps", [])[:3]:
        risks.append(f"Data/assumption: {g}.")
    neg = [f["explanation"] for f in sentiment.get("factors", []) if f["stance"] == "negative"][:1]
    if neg:
        risks.append("Macro headwind: " + neg[0])
    rsi = tech.get("indicators", {}).get("rsi_14")
    if rsi and rsi > 70:
        risks.append(f"RSI {rsi:.0f} is overbought; entries may be extended.")
    risks.append("Intrinsic values are model estimates; a change in WACC or growth shifts them materially (see sensitivity grid).")
    return risks


def top_ranked(candidates: List[Dict[str, Any]], n: int = 10) -> List[Dict[str, Any]]:
    """
    Best names by composite score. High-conviction names rank above lower-conviction ones, and each row
    keeps its conviction label, so weaker names are never presented as high conviction.
    """
    order = {"High": 2, "Moderate": 1, "Low": 0}
    ranked = sorted(
        candidates,
        key=lambda c: (order.get(c["conviction"], 0), c["triangulation"]["composite_score"]),
        reverse=True,
    )[:n]
    rows = []
    for i, c in enumerate(ranked, 1):
        plan = c.get("trade_plan") or {}
        rows.append({
            "rank": i,
            "symbol": c["symbol"],
            "company_name": c["company_name"],
            "sector": c["sector"],
            "conviction": c["conviction"],
            "action": c["triangulation"]["action"],
            "composite_score": c["triangulation"]["composite_score"],
            "signal": c.get("signal", ""),
            "current_price": c["current_price"],
            "entry_zone": plan.get("entry_zone"),
            "stop_loss": plan.get("stop_loss"),
            "target_1": plan.get("target_1"),
            "gates_failed": c.get("gate_failures", []),
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
    def universe(db: Session, limit: int) -> List[Tuple[str, str, str]]:
        rows = (db.query(StockMaster)
                .filter(StockMaster.is_nifty500 == True, StockMaster.is_active == True)
                .order_by(StockMaster.symbol).limit(limit).all())
        return [(r.symbol, r.name, r.sector or "Diversified") for r in rows]

    @staticmethod
    def analyse_stock(sym: str, market_inds: List[Dict[str, Any]], regime: str) -> Optional[Dict[str, Any]]:
        """
        Triangulated analysis for one stock.
        Hard exclusions (data quality only): no usable price history, no applicable valuation, illiquid.
        Everything else is a soft gate: the stock is still scored, and any unmet gate is listed.
        """
        reg = SourceRegistry.from_settings()
        fund, fin = reg.fundamentals_with_statements(sym)
        fin = fin or {}
        if not fund or fund.get("current_price", 0) <= 0:
            return None
        cmp_fund = fund["current_price"]
        turnover = (fund.get("avg_volume_20d") or 0) * cmp_fund
        if turnover < MIN_DAILY_TRADED_VALUE_INR:
            return None

        val = ValuationEngine.calculate_valuation_summary(fund, fin)
        if not val.get("is_applicable") or val.get("margin_of_safety_pct") is None:
            return None

        df = reg.history(sym, period="1y", interval="1d")
        if df.empty:
            return None
        tech = TechnicalEngine.analyze(df)
        if tech.get("status") == "error":
            return None
        cmp = tech["current_price"]
        ind = tech["indicators"]

        sentiment = stock_macro_sentiment(fund, market_inds)
        quality = val["quality_scorecard"]["quality_score"]
        tri = triangulate(val, tech["technical_score"], quality, regime, sentiment["score"] / 20.0)
        plan = build_trade_plan(cmp, ind["atr_14"], tech.get("nearest_resistance"), val.get("intrinsic_value"))
        if not plan:
            return None

        mos = val["margin_of_safety_pct"]
        gates = {
            "margin_of_safety": {"pass": mos >= MIN_MARGIN_OF_SAFETY_PCT,
                                 "value": mos, "threshold": MIN_MARGIN_OF_SAFETY_PCT},
            "quality": {"pass": quality >= MIN_QUALITY_SCORE, "value": quality, "threshold": MIN_QUALITY_SCORE},
            "trend": {"pass": cmp > ind["sma_200"], "value": round(cmp, 2), "threshold": ind["sma_200"],
                      "label": "Price above 200-DMA"},
            "technical": {"pass": tech["technical_score"] >= MIN_TECHNICAL_SCORE,
                          "value": tech["technical_score"], "threshold": MIN_TECHNICAL_SCORE},
            "composite": {"pass": tri["composite_score"] >= MIN_COMPOSITE,
                          "value": tri["composite_score"], "threshold": MIN_COMPOSITE},
            "risk_reward": {"pass": plan["risk_reward"] >= MIN_RISK_REWARD,
                            "value": plan["risk_reward"], "threshold": MIN_RISK_REWARD},
            "macro": {"pass": sentiment["sentiment"] != "Negative", "value": sentiment["sentiment"],
                      "threshold": "not Negative"},
            "data_confidence": {"pass": val.get("confidence") != "Low", "value": val.get("confidence"),
                                "threshold": "not Low"},
        }
        failures = [k for k, g in gates.items() if not g["pass"]]
        passed = len(gates) - len(failures)
        if not failures:
            conviction = "High"
        elif passed >= len(gates) - 2:
            conviction = "Moderate"
        else:
            conviction = "Low"

        return {
            "symbol": sym,
            "company_name": fund.get("company_name", sym),
            "sector": fund.get("sector"),
            "industry": fund.get("industry"),
            "current_price": round(cmp, 2),
            "valuation": {
                "method": val.get("primary_method"),
                "method_rationale": val.get("method_rationale"),
                "intrinsic_value": val.get("intrinsic_value"),
                "margin_of_safety_pct": val.get("margin_of_safety_pct"),
                "valuation_label": val.get("valuation_label"),
                "confidence": val.get("confidence"),
                "data_gaps": val.get("data_gaps", []),
                "inputs": val.get("inputs", {}),
                "cross_checks": {k: {"value_per_share": v.get("value_per_share")}
                                 for k, v in val.get("cross_checks", {}).items()},
            },
            "quality_score": quality,
            "signal": _pattern_signal(tech),
            "technical": {"rating": tech["overall_rating"], "score": tech["technical_score"],
                          "rsi_14": ind["rsi_14"], "sma_200": ind["sma_200"]},
            "macro_sentiment": {"sentiment": sentiment["sentiment"], "factors": sentiment["factors"]},
            "triangulation": tri,
            "trade_plan": plan,
            "gates": gates,
            "conviction": conviction,
            "gate_failures": failures,
            "thesis": _thesis_points(val, tech, sentiment, tri),
            "risks": _risk_points(val, tech, sentiment),
        }

    @staticmethod
    def select_two(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Always returns the best two available: fully-gated names first, then by composite score,
        with the two picks drawn from different sectors so they are not one bet.
        """
        ranked = sorted(
            candidates,
            key=lambda c: (len(c["gate_failures"]) == 0, c["triangulation"]["composite_score"]),
            reverse=True,
        )
        picks: List[Dict[str, Any]] = []
        sectors = set()
        for c in ranked:
            if c["sector"] in sectors:
                continue
            picks.append(c)
            sectors.add(c["sector"])
            if len(picks) == 2:
                break
        for i, p in enumerate(picks, 1):
            p["rank"] = i
        return picks

    @classmethod
    def run(cls, db: Session, universe_size: Optional[int] = None, workers: int = 6) -> Optional[Dict[str, Any]]:
        """Generates and stores today's picks. Returns None if a run is already in progress."""
        if not cls._lock.acquire(blocking=False):
            return None
        try:
            size = universe_size or settings.DAILY_UNIVERSE_SIZE
            universe = cls.universe(db, size)
            cls._status.update({"state": "running", "started_at": datetime.utcnow().isoformat(),
                                "finished_at": None, "processed": 0, "total": len(universe), "error": None})

            market_inds = MacroService.get_market_indicators()
            regime = MacroService.calculate_regime_classification(
                market_inds, MacroService.get_official_macro_indicators()).get("regime", "Neutral")

            candidates: List[Dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(cls.analyse_stock, sym, market_inds, regime): sym for sym, _, _ in universe}
                for fut in as_completed(futures):
                    sym = futures[fut]
                    try:
                        res = fut.result()
                        if res:
                            candidates.append(res)
                    except Exception as e:
                        logger.error(f"Daily-pick analysis failed for {sym}: {e}")
                    cls._status["processed"] += 1

            # Only High-conviction names may be recommended; lower-conviction names are reported, never picked.
            high = [c for c in candidates if c["conviction"] == "High"]
            picks = cls.select_two(high)

            reg = SourceRegistry.from_settings()
            nifty_1m = next((m.get("change_1m_pct") for m in market_inds if m.get("name") == "Nifty 50"), None)
            darvas = DarvasScanner.scan(universe, nifty_1m, history_loader=lambda s: reg.history(s, "1y", "1d"))
            payload = {
                "date": ist_today(),
                "generated_at": datetime.now(IST).isoformat(),
                "market_regime": regime,
                "universe_size": len(universe),
                "eligible_count": len(candidates),
                "picks": picks,
                "top_ten": top_ranked(candidates, 10),
                "high_conviction_count": len(high),
                "darvas": darvas,
                "data_sources": [src.name for src in reg.sources],
                "message": _summary_message(picks, candidates),
                "gates_note": {
                    "hard_exclusions": "Usable price history, applicable valuation, liquidity above the threshold below.",
                    "soft_gates": "Margin of safety, quality, 200-DMA trend, technical score, composite, risk-reward, macro, data confidence. Unmet gates lower conviction; they do not drop a stock.",
                    "min_margin_of_safety_pct": MIN_MARGIN_OF_SAFETY_PCT,
                    "min_quality_score": MIN_QUALITY_SCORE,
                    "min_technical_score": MIN_TECHNICAL_SCORE,
                    "min_composite": MIN_COMPOSITE,
                    "min_risk_reward": MIN_RISK_REWARD,
                    "min_daily_traded_value_cr": MIN_DAILY_TRADED_VALUE_INR / 1e7,
                    "trend_filter": "Price above 200-day SMA (soft)",
                    "sector_diversification": "Two picks from different sectors",
                },
                "disclaimer": "Model-generated research shortlist for education. Not SEBI-registered advice. Verify before trading.",
            }

            row = db.query(DailyPickModel).filter(DailyPickModel.date_key == payload["date"]).first()
            if row is None:
                row = DailyPickModel(date_key=payload["date"])
                db.add(row)
            row.generated_at = datetime.utcnow()
            row.payload = json.dumps(payload)
            row.eligible_count = len(candidates)
            db.commit()

            cls._status.update({"state": "idle", "finished_at": datetime.utcnow().isoformat()})
            return payload
        except Exception as e:
            logger.exception("Daily picks run failed")
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
