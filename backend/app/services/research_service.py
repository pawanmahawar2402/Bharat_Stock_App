"""
Equity research layer: triangulation of fundamental, technical and macro evidence,
stock-specific macro sentiment, and the full research note for a single company.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import StockMaster
from app.services import fundamental_engine as fe
from app.services.data_fetcher import DataFetcher
from app.services.macro_service import MacroService
from app.services.technical_service import TechnicalEngine
from app.services.valuation_service import ValuationEngine
from app.sources.registry import SourceRegistry

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

# Evidence weights for the composite (fundamental carries the most weight; macro is an overlay)
WEIGHTS = {"fundamental": 0.45, "technical": 0.35, "macro": 0.20}
REGIME_SCORE = {"Risk-On": 65.0, "Neutral": 50.0, "Risk-Off": 35.0}

_PROFILES_CACHE: Optional[List[Dict[str, Any]]] = None
MARKET_FACTOR_POINTS = 25.0   # points for a full-strength (+/-1) sensitivity at a full-strength (+/-2) move
RS_POINTS = 15.0              # max points for one-month relative strength vs Nifty


def _load_profiles() -> List[Dict[str, Any]]:
    global _PROFILES_CACHE
    if _PROFILES_CACHE is None:
        with open(CONFIG_DIR / "sector_macro_profiles.json", "r", encoding="utf-8") as f:
            _PROFILES_CACHE = json.load(f)["profiles"]
    return _PROFILES_CACHE


def _profile_for(sector: Optional[str], industry: Optional[str]) -> Dict[str, Any]:
    text = f"{sector or ''} {industry or ''}".lower()
    fallback = None
    for prof in _load_profiles():
        if not prof["match"]:
            fallback = prof
            continue
        if any(k in text for k in prof["match"]):
            return prof
    return fallback or {"name": "Default (unclassified)", "sensitivities": {"nifty": 0.5, "vix": -0.4}}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def stock_macro_sentiment(fund: Dict[str, Any], market_inds: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Stock-specific macro sentiment. Score in [-100, 100]; each contribution is listed.

      market factors  : sector sensitivity x indicator move, scaled by the stock's own beta
                        (nifty, vix) and leverage (us_yield)
      relative strength: the stock's 1M return minus Nifty's 1M return, in points

    Two stocks in the same sector therefore differ whenever their beta, leverage or price
    momentum differ.
    """
    by_name = {m["name"]: m for m in market_inds}
    profile = _profile_for(fund.get("sector"), fund.get("industry"))
    sens = profile["sensitivities"]

    beta = fe.num(fund.get("beta"))
    beta_adj = (0.67 * beta + 0.33) if beta is not None else 1.0
    beta_adj = _clamp(beta_adj, 0.6, 1.6)

    de = fe.num(fund.get("debt_to_equity"))
    de_ratio = (de / 100.0) if (de is not None and de > 5.0) else (de or 0.0)
    leverage_mult = 1.0 + _clamp(de_ratio, 0.0, 2.0) / 2.0   # 1.0 (no debt) to 2.0 (D/E >= 2)

    def indicator(name: str):
        return by_name.get(name)

    moves = {}
    crude = indicator("Brent Crude Oil")
    usd = indicator("USD / INR")
    us10 = indicator("US 10-Yr Treasury")
    vix = indicator("India VIX")
    nifty = indicator("Nifty 50")
    nasdaq = indicator("Nasdaq Composite")
    if crude: moves["crude"] = (_clamp((crude.get("change_1m_pct") or 0.0) / 5.0, -2, 2), crude)
    if usd: moves["usd_inr"] = (_clamp((usd.get("change_1m_pct") or 0.0) / 2.0, -2, 2), usd)
    if us10 and us10.get("current_value"):
        moves["us_yield"] = (_clamp((us10["current_value"] - 4.0) / 1.0, -2, 2), us10)
    if vix and vix.get("current_value"):
        moves["vix"] = (_clamp((vix["current_value"] - 15.0) / 5.0, -2, 2), vix)
    if nifty: moves["nifty"] = (_clamp((nifty.get("change_1m_pct") or 0.0) / 3.0, -2, 2), nifty)
    if nasdaq: moves["nasdaq"] = (_clamp((nasdaq.get("change_1m_pct") or 0.0) / 4.0, -2, 2), nasdaq)

    factors: List[Dict[str, Any]] = []
    score = 0.0
    for factor, s_val in sens.items():
        if factor not in moves:
            continue
        move, ind = moves[factor]
        scale = beta_adj if factor in ("nifty", "vix") else (leverage_mult if factor == "us_yield" else 1.0)
        points = s_val * move * MARKET_FACTOR_POINTS * scale
        if abs(points) < 2.0:
            continue
        score += points
        ind_value = ind.get("current_value") if factor in ("us_yield", "vix") else ind.get("change_1m_pct")
        metric = "current_value" if factor in ("us_yield", "vix") else "change_1m_pct"
        factors.append({
            "rule": factor,
            "indicator": ind["name"],
            "indicator_value": ind_value,
            "metric": metric,
            "stance": "positive" if points > 0 else "negative",
            "points": round(points, 1),
            "explanation": (f"{profile['name']} stocks are {'helped' if s_val > 0 else 'hurt'} by this factor "
                            f"(sensitivity {s_val:+.1f}); scaled by {'beta ' if factor in ('nifty', 'vix') else ('leverage ' if factor == 'us_yield' else '')}"
                            f"{scale:.2f}" if scale != 1.0 else
                            f"{profile['name']} stocks are {'helped' if s_val > 0 else 'hurt'} by this factor "
                            f"(sensitivity {s_val:+.1f})."),
        })

    # Stock-specific momentum relative to the market
    stock_1m = fe.num(fund.get("change_1m_pct"))
    nifty_1m = nifty.get("change_1m_pct") if nifty else None
    if stock_1m is not None and nifty_1m is not None:
        rel = stock_1m - float(nifty_1m)
        rs_points = _clamp(rel / 5.0, -1, 1) * RS_POINTS
        if abs(rs_points) >= 2.0:
            score += rs_points
            factors.append({
                "rule": "relative_strength",
                "indicator": "Stock vs Nifty 50 (1M)",
                "indicator_value": round(rel, 2),
                "metric": "change_1m_pct_vs_nifty",
                "stance": "positive" if rs_points > 0 else "negative",
                "points": round(rs_points, 1),
                "explanation": (f"The stock returned {stock_1m:+.1f}% over one month against Nifty's {float(nifty_1m):+.1f}%, "
                                f"{'outperforming' if rel > 0 else 'underperforming'} the market."),
            })

    score = round(_clamp(score, -100, 100), 1)
    if score >= 15:
        label = "Positive"
    elif score <= -15:
        label = "Negative"
    elif factors:
        label = "Mixed"
    else:
        label = "Neutral"
    return {
        "sentiment": label,
        "score": score,
        "net_score": score,
        "profile": profile["name"],
        "beta_used": round(beta_adj, 2),
        "leverage_multiplier": round(leverage_mult, 2),
        "factors": sorted(factors, key=lambda f: abs(f["points"]), reverse=True),
        "note": ("Score combines this sector's macro sensitivities (scaled by the stock's beta and leverage) "
                 "with its one-month performance relative to Nifty. Official macro series (repo, CPI, GDP) "
                 "are static fallbacks and are not used here."),
    }


def triangulate(valuation: Dict[str, Any], technical_score: float, quality_score: Optional[float],
                regime: str, sentiment_net: int) -> Dict[str, Any]:
    """
    Combines fundamental, technical and macro evidence into one 0-100 composite and an action label.
    """
    mos = valuation.get("margin_of_safety_pct")
    if mos is None:
        val_score = 50.0
        val_note = "No valid intrinsic value; scored neutral."
    else:
        val_score = max(0.0, min(100.0, 50.0 + float(mos)))
        val_note = f"Margin of safety {mos:+.1f}% mapped to {val_score:.0f}/100."
    q = float(quality_score) if quality_score is not None else 50.0
    fundamental = 0.6 * val_score + 0.4 * q

    macro = REGIME_SCORE.get(regime, 50.0) + max(-15.0, min(15.0, sentiment_net * 5.0))
    tech = float(technical_score or 50.0)

    composite = (WEIGHTS["fundamental"] * fundamental
                 + WEIGHTS["technical"] * tech
                 + WEIGHTS["macro"] * macro)

    if mos is None:
        action = "Not rated (no valid valuation)"
    elif composite >= 70:
        action = "Strong Buy"
    elif composite >= 60:
        action = "Buy"
    elif composite >= 45:
        action = "Hold"
    elif composite >= 35:
        action = "Reduce"
    else:
        action = "Sell"

    fund_bull = fundamental >= 55
    tech_bull = tech >= 55
    fund_bear = fundamental <= 45
    tech_bear = tech <= 45
    if (fund_bull and tech_bull) or (fund_bear and tech_bear):
        agreement = "Aligned"
    elif (fund_bull and tech_bear) or (fund_bear and tech_bull):
        agreement = "Divergent"
    else:
        agreement = "Mixed"

    return {
        "composite_score": round(composite, 1),
        "action": action,
        "agreement": agreement,
        "components": {
            "fundamental": {"score": round(fundamental, 1), "weight": WEIGHTS["fundamental"], "note": val_note},
            "technical": {"score": round(tech, 1), "weight": WEIGHTS["technical"]},
            "macro": {"score": round(macro, 1), "weight": WEIGHTS["macro"], "regime": regime},
        },
    }


def peer_median_ev_ebitda(sector: Optional[str], db: Session, exclude_symbol: str, limit: int = 5) -> Optional[float]:
    """Live median EV/EBITDA of up to `limit` same-sector stocks from the stock master."""
    if not sector or sector == "Diversified":
        return None
    peers = (db.query(StockMaster)
             .filter(StockMaster.sector == sector, StockMaster.symbol != exclude_symbol)
             .limit(limit * 2).all())
    multiples = []
    for p in peers:
        if len(multiples) >= limit:
            break
        try:
            q = DataFetcher.fetch_quote_and_fundamentals(p.symbol)
            m = fe.num(q.get("enterprise_to_ebitda"))
            if m is not None and 3.0 <= m <= 60.0:
                multiples.append(m)
        except Exception as e:
            logger.debug(f"Peer multiple failed for {p.symbol}: {e}")
    if len(multiples) < 2:
        return None
    multiples.sort()
    mid = len(multiples) // 2
    return round(multiples[mid] if len(multiples) % 2 else (multiples[mid - 1] + multiples[mid]) / 2, 2)


def build_research_note(symbol: str, db: Optional[Session] = None, market_inds: Optional[List[Dict[str, Any]]] = None,
                        regime: Optional[str] = None) -> Dict[str, Any]:
    """Full single-company research note: valuation, technicals, macro sentiment and triangulated verdict."""
    norm = DataFetcher.normalize_symbol(symbol)
    reg = SourceRegistry.from_settings()
    fund, fin = reg.fundamentals_with_statements(norm)
    fin = fin or {}

    # Peer group comes from the stock master (same labelling as the peer endpoint), not Yahoo's sector
    peer_mult = None
    if db is not None:
        master = db.query(StockMaster).filter(StockMaster.symbol == norm).first()
        group = master.sector if master and master.sector else None
        peer_mult = peer_median_ev_ebitda(group, db, norm)
    val = ValuationEngine.calculate_valuation_summary(fund, fin, peer_ev_ebitda=peer_mult)

    df = reg.history(norm, period="1y", interval="1d")
    tech = TechnicalEngine.analyze(df) if not df.empty else {"status": "error", "message": "No price history"}

    if market_inds is None:
        market_inds = MacroService.get_market_indicators()
    if regime is None:
        regime = MacroService.calculate_regime_classification(
            market_inds, MacroService.get_official_macro_indicators()).get("regime", "Neutral")

    sentiment = stock_macro_sentiment(fund, market_inds)
    tri = triangulate(
        val,
        tech.get("technical_score", 50),
        val.get("quality_scorecard", {}).get("quality_score"),
        regime,
        sentiment["score"] / 20.0,
    )

    return {
        "symbol": norm,
        "company_name": fund.get("company_name", norm),
        "sector": fund.get("sector"),
        "industry": fund.get("industry"),
        "current_price": fund.get("current_price"),
        "fundamentals": fund,
        "valuation": val,
        "peer_median_ev_ebitda": peer_mult,
        "technical": tech,
        "macro_sentiment": sentiment,
        "market_regime": regime,
        "triangulation": tri,
        "disclaimer": "Analytical research output for education. Not SEBI-registered investment advice.",
    }
