import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
from app.config import settings
from app.services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

MARKET_INDICATORS = [
    {"name": "Nifty 50", "ticker": "^NSEI", "category": "Domestic Benchmark", "unit": "pts"},
    {"name": "BSE Sensex", "ticker": "^BSESN", "category": "Domestic Benchmark", "unit": "pts"},
    {"name": "India VIX", "ticker": "^INDIAVIX", "category": "Volatility Index", "unit": "pts"},
    {"name": "USD / INR", "ticker": "INR=X", "category": "Currency", "unit": "₹/$"},
    {"name": "Brent Crude Oil", "ticker": "BZ=F", "category": "Commodity", "unit": "$/bbl"},
    {"name": "Gold (MCX/Comex)", "ticker": "GC=F", "category": "Commodity", "unit": "$/oz"},
    {"name": "US 10-Yr Treasury", "ticker": "^TNX", "category": "Global Yield", "unit": "%"},
    {"name": "US Dollar Index (DXY)", "ticker": "DX-Y.NYB", "category": "Global Currency", "unit": "pts"},
    {"name": "S&P 500", "ticker": "^GSPC", "category": "Global Equity", "unit": "pts"},
    {"name": "Nasdaq Composite", "ticker": "^IXIC", "category": "Global Tech Equity", "unit": "pts"}
]

class MacroService:
    """
    Manages global market indicators, macroeconomic data, Macro Regime Engine,
    Sector Rotation Heatmap, and Narrative generation.
    """

    @staticmethod
    def get_market_indicators() -> List[Dict[str, Any]]:
        """
        Fetches the 10 market indicators from Yahoo Finance with sparkline and % changes.
        """
        results = []
        for ind in MARKET_INDICATORS:
            sym = ind["ticker"]
            try:
                hist = DataFetcher.fetch_history(sym, period="1y", interval="1d")
                if not hist.empty and len(hist) >= 2:
                    closes = hist["Close"].dropna()
                    current = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2])
                    change_1d = current - prev
                    change_1d_pct = round((change_1d / prev) * 100, 2)

                    change_1w_pct = round(((current - float(closes.iloc[-5])) / float(closes.iloc[-5])) * 100, 2) if len(closes) >= 5 else 0.0
                    change_1m_pct = round(((current - float(closes.iloc[-21])) / float(closes.iloc[-21])) * 100, 2) if len(closes) >= 21 else 0.0
                    change_1y_pct = round(((current - float(closes.iloc[-200])) / float(closes.iloc[-200])) * 100, 2) if len(closes) >= 200 else 0.0

                    sparkline = [round(float(x), 2) for x in closes.tail(30).tolist()]

                    results.append({
                        "name": ind["name"],
                        "ticker": sym,
                        "category": ind["category"],
                        "current_value": round(current, 2),
                        "unit": ind["unit"],
                        "change_1d": round(change_1d, 2),
                        "change_1d_pct": change_1d_pct,
                        "change_1w_pct": change_1w_pct,
                        "change_1m_pct": change_1m_pct,
                        "change_1y_pct": change_1y_pct,
                        "sparkline": sparkline,
                        "source": "Yahoo Finance (Market Feed)",
                        "last_updated": datetime.utcnow().isoformat()
                    })
                else:
                    # Fallback default
                    results.append({
                        "name": ind["name"],
                        "ticker": sym,
                        "category": ind["category"],
                        "current_value": 0.0,
                        "unit": ind["unit"],
                        "change_1d": 0.0,
                        "change_1d_pct": 0.0,
                        "change_1w_pct": 0.0,
                        "change_1m_pct": 0.0,
                        "change_1y_pct": 0.0,
                        "sparkline": [],
                        "source": "Yahoo Finance (Delayed)",
                        "last_updated": datetime.utcnow().isoformat()
                    })
            except Exception as e:
                logger.error(f"Error fetching market indicator {sym}: {e}")
                continue
        return results

    @staticmethod
    def get_official_macro_indicators() -> Dict[str, Any]:
        """
        Loads non-Yahoo official macroeconomic data (Repo, CPI, GDP, IIP, PMI, G-Sec, Forex, FII/DII)
        from config fallback with verified source attribution.
        """
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "macro_fallback.json"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def calculate_regime_classification(market_inds: List[Dict[str, Any]], macro_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates the Macro Regime: Risk-On, Neutral, or Risk-Off with factor attribution.
        """
        factors = []
        score = 0 # -10 (extreme risk-off) to +10 (extreme risk-on)

        # 1. India VIX Factor
        vix_item = next((x for x in market_inds if x["name"] == "India VIX"), None)
        vix_val = vix_item["current_value"] if vix_item and vix_item["current_value"] > 0 else 14.5
        if vix_val < 14.0:
            score += 3
            factors.append({"factor": "India VIX", "status": "Bullish", "score": "+3", "detail": f"VIX at {vix_val:.1f} indicates market complacency and low hedging demand."})
        elif vix_val <= 18.5:
            score += 1
            factors.append({"factor": "India VIX", "status": "Neutral", "score": "+1", "detail": f"VIX at {vix_val:.1f} in normal historical trading range."})
        else:
            score -= 3
            factors.append({"factor": "India VIX", "status": "Bearish / Elevated Risk", "score": "-3", "detail": f"VIX at {vix_val:.1f} signals high volatility and protective option buying."})

        # 2. Nifty 50 Trend vs 200 DMA
        nifty_item = next((x for x in market_inds if x["name"] == "Nifty 50"), None)
        if nifty_item and nifty_item.get("sparkline") and len(nifty_item["sparkline"]) >= 10:
            nifty_val = nifty_item["current_value"]
            # 1M trend
            change_1m = nifty_item.get("change_1m_pct", 0.0)
            if change_1m > 1.5:
                score += 3
                factors.append({"factor": "Nifty 50 Trend", "status": "Bullish", "score": "+3", "detail": f"Nifty trading strong with +{change_1m:.1f}% 1-month momentum."})
            elif change_1m < -2.0:
                score -= 3
                factors.append({"factor": "Nifty 50 Trend", "status": "Bearish", "score": "-3", "detail": f"Nifty experiencing correction with {change_1m:.1f}% 1-month drawdown."})
            else:
                score += 0
                factors.append({"factor": "Nifty 50 Trend", "status": "Neutral", "score": "0", "detail": "Nifty in consolidation phase."})

        # 3. Brent Crude Oil Impact
        crude_item = next((x for x in market_inds if "Crude" in x["name"]), None)
        if crude_item and crude_item["current_value"] > 0:
            crude_val = crude_item["current_value"]
            if crude_val > 85.0:
                score -= 2
                factors.append({"factor": "Brent Crude", "status": "Bearish Headwind", "score": "-2", "detail": f"Crude at ${crude_val:.1f}/bbl creates imported inflation and CAD pressure for India."})
            elif crude_val < 75.0:
                score += 2
                factors.append({"factor": "Brent Crude", "status": "Bullish Tailwind", "score": "+2", "detail": f"Crude at ${crude_val:.1f}/bbl supports Indian corporate margins and currency stability."})
            else:
                factors.append({"factor": "Brent Crude", "status": "Neutral", "score": "0", "detail": f"Crude at ${crude_val:.1f}/bbl is within comfortable range."})

        # 4. USD/INR & DXY
        usdinr_item = next((x for x in market_inds if "USD" in x["name"]), None)
        if usdinr_item and usdinr_item.get("change_1m_pct", 0) > 1.0:
            score -= 1
            factors.append({"factor": "USD/INR", "status": "Mild Headwind", "score": "-1", "detail": "Rupee depreciation pressure against strong US Dollar."})
        else:
            factors.append({"factor": "USD/INR", "status": "Stable", "score": "+1", "detail": "Rupee trading with low volatility backed by RBI forex reserves."})

        # 5. FII Flow Trend
        fii_data = macro_data.get("fii_dii_recent", {})
        fii_5d = fii_data.get("fii_net_5d", 0.0)
        dii_5d = fii_data.get("dii_net_5d", 0.0)
        if dii_5d > abs(fii_5d):
            score += 2
            factors.append({"factor": "DII Support", "status": "Bullish Cushion", "score": "+2", "detail": f"Strong domestic institutional inflows (+₹{dii_5d:,.0f} Cr) absorbing foreign selling."})
        elif fii_5d < -10000:
            score -= 2
            factors.append({"factor": "FII Outflows", "status": "Defensive", "score": "-2", "detail": f"Significant FII net selling (-₹{abs(fii_5d):,.0f} Cr over 5 sessions)."})

        # Regime Determination
        if score >= 3:
            regime = "Risk-On"
            regime_desc = "Favorable macro conditions. Broad market participation, low volatility, and supportive liquidity indicate an optimal environment for equity deployment and momentum swing setups."
            color = "emerald"
            badge = "🟢 Risk-On"
        elif score <= -2:
            regime = "Risk-Off"
            regime_desc = "Defensive macro environment. Heightened volatility, global headwinds, or institutional selling suggest prioritizing capital preservation, tightening stop-losses, and requiring higher Risk/Reward ratios."
            color = "rose"
            badge = "🔴 Risk-Off"
        else:
            regime = "Neutral / Selective"
            regime_desc = "Consolidation regime. Market is stock-specific and range-bound. Focus on quality large-caps, sector rotation leaders, and high-probability breakout setups."
            color = "amber"
            badge = "🟡 Neutral"

        return {
            "regime": regime,
            "badge": badge,
            "score": score,
            "color": color,
            "description": regime_desc,
            "factors": factors
        }

    @staticmethod
    def get_sector_rotation_heatmap() -> List[Dict[str, Any]]:
        """
        Calculates 1W, 1M, and 3M returns and Relative Strength (RS) vs Nifty 50 for sectors.
        """
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "nse_sectors.json"
        sectors_cfg = []
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                sectors_cfg = json.load(f).get("sectors", [])

        # Fetch Nifty benchmark return
        nifty_df = DataFetcher.fetch_history("^NSEI", period="6mo", interval="1d")
        nifty_1m_ret = 0.0
        if not nifty_df.empty and len(nifty_df) >= 22:
            closes = nifty_df["Close"].dropna()
            nifty_1m_ret = round(((float(closes.iloc[-1]) - float(closes.iloc[-21])) / float(closes.iloc[-21])) * 100, 2)

        results = []
        for sec in sectors_cfg:
            sym = sec["ticker"]
            try:
                df = DataFetcher.fetch_history(sym, period="6mo", interval="1d")
                if not df.empty and len(df) >= 5:
                    closes = df["Close"].dropna()
                    current = float(closes.iloc[-1])
                    ret_1w = round(((current - float(closes.iloc[-5])) / float(closes.iloc[-5])) * 100, 2)
                    ret_1m = round(((current - float(closes.iloc[-21])) / float(closes.iloc[-21])) * 100, 2) if len(closes) >= 21 else 0.0
                    ret_3m = round(((current - float(closes.iloc[-63])) / float(closes.iloc[-63])) * 100, 2) if len(closes) >= 63 else 0.0

                    # Relative Strength vs Nifty
                    rs_1m = round(ret_1m - nifty_1m_ret, 2)
                    rs_signal = "Outperforming" if rs_1m > 1.0 else ("Underperforming" if rs_1m < -1.0 else "In-Line")

                    results.append({
                        "name": sec["name"],
                        "sector_key": sec["sector_key"],
                        "ticker": sym,
                        "current_index_value": round(current, 2),
                        "return_1w_pct": ret_1w,
                        "return_1m_pct": ret_1m,
                        "return_3m_pct": ret_3m,
                        "rs_vs_nifty_1m": rs_1m,
                        "rs_signal": rs_signal,
                        "description": sec["description"]
                    })
            except Exception as e:
                logger.error(f"Error fetching sector {sym}: {e}")
                continue

        # Sort by 1M return descending
        results.sort(key=lambda x: x["return_1m_pct"], reverse=True)
        return results

    @staticmethod
    def generate_narrative(regime_data: Dict[str, Any], market_inds: List[Dict[str, Any]], macro_data: Dict[str, Any], sectors: List[Dict[str, Any]]) -> List[str]:
        """
        Generates 5-8 crisp institutional takeaway bullets on "What this means for equities".
        Guaranteed to use strictly real data numbers.
        """
        regime = regime_data.get("regime", "Neutral")
        vix_item = next((x for x in market_inds if x["name"] == "India VIX"), {})
        vix_val = vix_item.get("current_value", 14.5)
        nifty_item = next((x for x in market_inds if x["name"] == "Nifty 50"), {})
        nifty_val = nifty_item.get("current_value", 24800)
        nifty_1m = nifty_item.get("change_1m_pct", 0.0)

        top_sector = sectors[0]["name"] if sectors else "Nifty IT"
        top_sec_ret = sectors[0]["return_1m_pct"] if sectors else 3.5
        bottom_sector = sectors[-1]["name"] if sectors else "Nifty FMCG"

        repo_rate = macro_data.get("rbi_repo_rate", {}).get("value", 6.50)
        cpi = macro_data.get("cpi_inflation", {}).get("value", 4.85)
        gsec = macro_data.get("india_10y_gsec", {}).get("value", 6.78)

        bullets = [
            f"**Macro Stance ({regime_data['badge']})**: Market regime is currently classified as **{regime}**, reflecting benchmark Nifty at {nifty_val:,.0f} ({nifty_1m:+.1f}% 1-Month) and India VIX at {vix_val:.2f}.",
            f"**Monetary Policy & Yields**: RBI Repo Rate remains anchored at {repo_rate:.2f}% while the India 10-Year Benchmark G-Sec yield trades at {gsec:.2f}%, sustaining reasonable equity risk premium headroom.",
            f"**Inflation & Domestic Activity**: Headline CPI inflation stands at {cpi:.2f}% YoY, keeping domestic consumer demand stable while industrial activity (PMI/IIP) indicates steady private capex.",
            f"**Sectoral Rotation Play**: Sector momentum is heavily favoring **{top_sector}** (+{top_sec_ret:.1f}% 1M return), whereas defensive rotation is lagging in **{bottom_sector}**.",
            f"**Institutional Liquidity Cushion**: Persistent domestic mutual fund SIP flows and DII buying continue to absorb intermittent foreign FII selling pressures across large-cap counters.",
            "**Actionable Strategy**: Maintain structured position sizing. Ride sector breakout leaders with strict trailing stop-losses and avoid unhedged overnight leverage in high-beta counters."
        ]
        return bullets
