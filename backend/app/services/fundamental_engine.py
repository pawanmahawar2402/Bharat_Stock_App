"""
Statement-driven equity valuation engine.

Method selection (one primary method per company, the way a sell-side analyst would choose):
  * Financials (banks, NBFCs, insurers)            -> FCFE, sustainable-growth, Ke-discounted
  * Non-financials with positive normalised FCFF   -> FCFF 2-stage DCF with value-driver terminal value
  * Non-financials with negative FCFF, EBITDA > 0  -> EV/EBITDA relative valuation (peer or sector multiple)
  * Anything else                                  -> "Not applicable" (no number is fabricated)

Every input is read from the annual financial statements (income statement, balance sheet,
cash-flow statement). Missing inputs are recorded in `data_gaps` and lower the confidence
rating; they are never silently replaced with invented figures.

All monetary values are kept in INR (absolute). Per-share values are in INR.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Assumption bounds (documented so the analyst can audit every number)
# ---------------------------------------------------------------------------
TERMINAL_GROWTH = 0.045          # nominal INR terminal growth (below India 10Y G-Sec)
STAGE1_YEARS = 5
STAGE2_YEARS = 5
MIN_WACC_SPREAD = 0.02           # WACC/Ke must exceed terminal growth by at least 2pp
TAX_BOUNDS = (0.15, 0.35)
TAX_DEFAULT = 0.2517             # Indian statutory corporate rate (sec. 115BAA)
BETA_BOUNDS = (0.8, 2.0)         # floor 0.8: raw Yahoo betas for Indian large caps are often <0.5 and understate Ke
BETA_DEFAULT = 1.0
REV_CAGR_BOUNDS = (-0.05, 0.15)  # historical growth is clamped; no extrapolating hype
REV_CAGR_DEFAULT = 0.08
RONIC_CAP = 0.25                 # return on new invested capital cap (moat-adjusted)
SUSTAINABLE_G_CAP = 0.15         # ROE x retention cap for financials
MAX_NET_DEBT_SHARE_OF_EV = 0.5    # relative value unreliable when debt dominates the enterprise value
MAX_MARKET_TO_BENCHMARK_MULTIPLE = 2.5  # market EV/EBITDA more than 2.5x the benchmark = growth not captured
DEFAULT_PAYOUT = 0.20            # used only when dividend history is unavailable (flagged)
FINANCIAL_KEYWORDS = (
    "bank", "financial", "nbfc", "insurance", "lending", "housing finance",
    "asset management", "credit", "finance",
)

_SECTOR_MULTIPLES_PATH = Path(__file__).resolve().parent.parent / "config" / "sector_ev_ebitda.json"


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def num(x: Any) -> Optional[float]:
    """Coerce to a finite float, returning None for 'N/A', None, NaN, inf, or booleans."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def is_financial(sector: Optional[str], industry: Optional[str]) -> bool:
    text = f"{sector or ''} {industry or ''}".lower()
    return any(k in text for k in FINANCIAL_KEYWORDS)


def _sector_default_multiple(sector: Optional[str]) -> float:
    try:
        with open(_SECTOR_MULTIPLES_PATH, "r", encoding="utf-8") as f:
            table = json.load(f)
        return float(table.get(sector or "", table.get("default", 15.0)))
    except Exception:
        return 15.0


class StatementView:
    """Read-only accessor over {period_end: {line_item: value}} dicts, most recent period first."""

    def __init__(self, stmt: Optional[Dict[str, Dict[str, Any]]]):
        if stmt:
            self.periods: List[Dict[str, Any]] = [stmt[k] for k in sorted(stmt.keys(), reverse=True)]
        else:
            self.periods = []

    def get(self, names: List[str], i: int = 0) -> Optional[float]:
        if i >= len(self.periods):
            return None
        for n in names:
            v = num(self.periods[i].get(n))
            if v is not None:
                return v
        return None

    def series(self, names: List[str], n: int = 4) -> List[Optional[float]]:
        return [self.get(names, i) for i in range(min(n, len(self.periods)))]

    def __len__(self) -> int:
        return len(self.periods)


# Yahoo Finance line-item names (first match wins)
_IS = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "cogs": ["Cost Of Revenue"],
    "ebit": ["EBIT", "Operating Income"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "pretax": ["Pretax Income"],
    "tax": ["Tax Provision"],
    "interest": ["Interest Expense", "Interest Expense Non Operating"],
    "net_income": ["Net Income Common Stockholders", "Net Income"],
}
_CF = {
    "cfo": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capex": ["Capital Expenditure"],
    "dep": ["Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation"],
    "dividends": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
    "net_borrowing": ["Net Issuance Payments Of Debt"],
}
_BS = {
    "total_debt": ["Total Debt"],
    "cash": ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Financial"],
    "equity": ["Stockholders Equity", "Common Stock Equity"],
    "minority": ["Minority Interest"],
    "total_assets": ["Total Assets"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "shares": ["Ordinary Shares Number", "Share Issued"],
}


def _period_metrics(IS: StatementView, CF: StatementView, BS: StatementView, i: int) -> Dict[str, Optional[float]]:
    """Extract one fiscal period's metrics; fallbacks are derived from related lines where possible."""
    m: Dict[str, Optional[float]] = {}
    m["revenue"] = IS.get(_IS["revenue"], i)
    m["cogs"] = IS.get(_IS["cogs"], i)
    m["pretax"] = IS.get(_IS["pretax"], i)
    m["tax"] = IS.get(_IS["tax"], i)
    interest = IS.get(_IS["interest"], i)
    m["interest"] = abs(interest) if interest is not None else None
    m["net_income"] = IS.get(_IS["net_income"], i)

    dep = CF.get(_CF["dep"], i)
    m["dep"] = abs(dep) if dep is not None else None

    ebit = IS.get(_IS["ebit"], i)
    if ebit is None and m["pretax"] is not None and m["interest"] is not None:
        ebit = m["pretax"] + m["interest"]
    m["ebit"] = ebit

    ebitda = IS.get(_IS["ebitda"], i)
    if ebitda is None and ebit is not None and m["dep"] is not None:
        ebitda = ebit + m["dep"]
    m["ebitda"] = ebitda

    cfo = CF.get(_CF["cfo"], i)
    capex = CF.get(_CF["capex"], i)
    m["cfo"] = cfo
    m["capex"] = abs(capex) if capex is not None else None
    div = CF.get(_CF["dividends"], i)
    m["dividends"] = abs(div) if div is not None else None
    m["net_borrowing"] = CF.get(_CF["net_borrowing"], i)

    m["total_debt"] = BS.get(_BS["total_debt"], i)
    m["cash"] = BS.get(_BS["cash"], i)
    m["equity"] = BS.get(_BS["equity"], i)
    m["minority"] = BS.get(_BS["minority"], i) or 0.0
    m["total_assets"] = BS.get(_BS["total_assets"], i)
    m["current_assets"] = BS.get(_BS["current_assets"], i)
    m["current_liabilities"] = BS.get(_BS["current_liabilities"], i)
    m["shares"] = BS.get(_BS["shares"], i)
    return m


def extract_inputs(financials: Dict[str, Any]) -> Dict[str, Any]:
    """Builds the per-period history (most recent first) used by every valuation model."""
    IS = StatementView(financials.get("income_statement"))
    CF = StatementView(financials.get("cash_flow"))
    BS = StatementView(financials.get("balance_sheet"))
    n = max(len(IS), len(CF), len(BS), 0)
    n = min(n, 4)
    history = [_period_metrics(IS, CF, BS, i) for i in range(n)]
    return {"periods": n, "history": history}


# ---------------------------------------------------------------------------
# Cost of capital
# ---------------------------------------------------------------------------
def cost_of_equity(beta: Optional[float], rf: float, erp: float) -> Dict[str, Any]:
    """CAPM cost of equity with a Blume-adjusted beta (0.67 x raw + 0.33), bounded to 0.8-2.0."""
    if beta is None:
        b, src = BETA_DEFAULT, "default 1.0 (beta unavailable)"
    else:
        adjusted = 0.67 * beta + 0.33
        b = clamp(adjusted, *BETA_BOUNDS)
        src = f"Yahoo raw beta {beta:.2f}, Blume-adjusted {adjusted:.2f}, bounded to 0.8-2.0"
    return {"ke": rf + b * erp, "beta": b, "beta_source": src}


def wacc_build(mcap: Optional[float], debt: Optional[float], interest: Optional[float],
               tax: float, rf: float, ke: float) -> Dict[str, Any]:
    d = debt or 0.0
    e = mcap or 0.0
    if d > 0 and interest:
        kd = clamp(interest / d, rf, rf + 0.05)
        kd_src = "Interest expense / total debt"
    else:
        kd = rf + 0.015
        kd_src = "Risk-free + 1.5pp (no reliable interest/debt data)"
    if e + d <= 0:
        return {"wacc": ke, "kd": kd, "kd_source": kd_src, "weight_equity": 1.0}
    we = e / (e + d)
    wacc = we * ke + (1 - we) * kd * (1 - tax)
    return {"wacc": wacc, "kd": kd, "kd_source": kd_src, "weight_equity": we}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
def fcff_dcf(rev0: float, margin: float, nopat0: Optional[float], g1: float, wacc: float,
             ronic: float, g_term: float) -> Dict[str, Any]:
    """
    Two-stage FCFF DCF.
      Years 1-5: revenue grows at g1; FCFF = normalised FCFF margin x revenue.
      Years 6-10: growth fades linearly to g_term.
      Terminal: value-driver formula  FCFF_{T+1} = NOPAT_{T+1} x (1 - g/RONIC),
                TV = FCFF_{T+1} / (WACC - g).
    """
    rev = rev0
    g = g1
    pv_explicit = 0.0
    rows = []
    fcff = 0.0
    total_years = STAGE1_YEARS + STAGE2_YEARS
    for t in range(1, total_years + 1):
        if t > STAGE1_YEARS:
            g = g1 + (g_term - g1) * ((t - STAGE1_YEARS) / STAGE2_YEARS)
        rev *= (1 + g)
        fcff = rev * margin
        df = (1 + wacc) ** -t
        pv_explicit += fcff * df
        rows.append({"year": t, "growth_pct": round(g * 100, 2), "revenue_cr": round(rev / 1e7, 2),
                     "fcff_cr": round(fcff / 1e7, 2), "pv_cr": round(fcff * df / 1e7, 2)})

    nopat_margin = (nopat0 / rev0) if (nopat0 is not None and rev0 > 0) else None
    if nopat_margin and nopat_margin > 0:
        nopat_T = nopat_margin * rev
        fcff_T1 = nopat_T * (1 + g_term) * (1 - g_term / ronic)
        terminal_method = "Value-driver (NOPAT x (1 - g/RONIC))"
    else:
        fcff_T1 = fcff * (1 + g_term)
        terminal_method = "Gordon growth on final FCFF (NOPAT unavailable)"

    tv = fcff_T1 / (wacc - g_term)
    pv_tv = tv * (1 + wacc) ** -total_years
    return {
        "enterprise_value": pv_explicit + pv_tv,
        "pv_explicit": pv_explicit,
        "pv_terminal": pv_tv,
        "terminal_fcff": fcff_T1,
        "terminal_method": terminal_method,
        "projections": rows,
    }


def fcfe_equity(ni0: float, roe: float, g1: float, ke: float, g_term: float) -> Dict[str, Any]:
    """
    FCFE for financial institutions: FCFE_t = NI_t x (1 - g_t / ROE).
    Reinvestment needed to fund growth is g/ROE of earnings (equity retention identity).
    """
    ni = ni0
    g = g1
    pv = 0.0
    rows = []
    total_years = STAGE1_YEARS + STAGE2_YEARS
    for t in range(1, total_years + 1):
        if t > STAGE1_YEARS:
            g = g1 + (g_term - g1) * ((t - STAGE1_YEARS) / STAGE2_YEARS)
        ni *= (1 + g)
        reinvest = clamp(g / roe, 0.0, 1.0)
        fcfe = ni * (1 - reinvest)
        df = (1 + ke) ** -t
        pv += fcfe * df
        rows.append({"year": t, "growth_pct": round(g * 100, 2), "net_income_cr": round(ni / 1e7, 2),
                     "fcfe_cr": round(fcfe / 1e7, 2), "pv_cr": round(fcfe * df / 1e7, 2)})
    fcfe_T1 = ni * (1 + g_term) * (1 - clamp(g_term / roe, 0.0, 1.0))
    tv = fcfe_T1 / (ke - g_term)
    pv_tv = tv * (1 + ke) ** -total_years
    return {"equity_value": pv + pv_tv, "pv_explicit": pv, "pv_terminal": pv_tv,
            "terminal_fcfe": fcfe_T1, "projections": rows}


def value_driver_ev(nopat0: float, g1: float, wacc: float, ronic: float, g_term: float) -> float:
    """
    Growth-consistent enterprise value for a capital-intensive company.
    Each year NOPAT grows at g; reinvestment is g / RONIC of NOPAT, so growth must be paid for.
    The explicit growth fades to the terminal rate over years 6-10. Terminal value uses the same identity.
    """
    nop = nopat0
    g = g1
    pv = 0.0
    total = STAGE1_YEARS + STAGE2_YEARS
    for t in range(1, total + 1):
        if t > STAGE1_YEARS:
            g = g1 + (g_term - g1) * ((t - STAGE1_YEARS) / STAGE2_YEARS)
        nop *= (1 + g)
        fcff = nop * (1 - clamp(g / ronic, 0.0, 1.0))
        pv += fcff * (1 + wacc) ** -t
    tv = nop * (1 + g_term) * (1 - clamp(g_term / ronic, 0.0, 1.0)) / (wacc - g_term)
    return pv + tv * (1 + wacc) ** -total


def _implied_nopat_multiple(market_ev: float, nopat0: float, g1: float, wacc: float, ronic: float,
                            g_term: float) -> float:
    """Multiple k of today's normalised NOPAT such that value_driver_ev(k * NOPAT) equals market EV."""
    lo, hi = 0.01, 5000.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if value_driver_ev(mid * nopat0, g1, wacc, ronic, g_term) < market_ev:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _bridge_to_equity(ev: float, debt: float, cash: float, minority: float) -> float:
    return ev - debt + cash - minority


def _valuation_label(mos_pct: Optional[float]):
    if mos_pct is None:
        return "Not Applicable", "slate"
    if mos_pct >= 25.0:
        return "Deeply Undervalued", "emerald"
    if mos_pct >= 10.0:
        return "Undervalued", "green"
    if mos_pct >= -10.0:
        return "Fairly Valued", "blue"
    if mos_pct >= -25.0:
        return "Modestly Overvalued", "amber"
    return "Significantly Overvalued", "rose"


# ---------------------------------------------------------------------------
# Quality, Piotroski F-score (computed from statements, no synthetic defaults)
# ---------------------------------------------------------------------------
def piotroski_fscore(financials: Dict[str, Any]) -> Dict[str, Any]:
    """Standard 9-point Piotroski F-score. Checks lacking data are excluded and reported."""
    inp = extract_inputs(financials)
    h = inp["history"]
    checks: List[Dict[str, Any]] = []

    def add(name: str, passed: Optional[bool], detail: str):
        checks.append({"check": name, "passed": passed, "detail": detail})

    if len(h) < 2:
        return {"score": None, "max_score": 9, "checks_available": 0, "checks": [],
                "rating": "Insufficient data", "note": "Needs at least two fiscal years of statements."}

    c, p = h[0], h[1]

    def ratio(a, b):
        return (a / b) if (a is not None and b not in (None, 0)) else None

    roa_c = ratio(c["net_income"], c["total_assets"])
    roa_p = ratio(p["net_income"], p["total_assets"])
    add("ROA > 0", None if roa_c is None else roa_c > 0, f"ROA {roa_c:.2%}" if roa_c is not None else "n/a")
    add("CFO > 0", None if c["cfo"] is None else c["cfo"] > 0, f"CFO {c['cfo']/1e7:,.0f} Cr" if c["cfo"] is not None else "n/a")
    add("ROA improving", None if (roa_c is None or roa_p is None) else roa_c > roa_p,
        f"ROA {roa_p:.2%} -> {roa_c:.2%}" if roa_c is not None and roa_p is not None else "n/a")
    add("CFO > Net income (accruals)", None if (c["cfo"] is None or c["net_income"] is None) else c["cfo"] > c["net_income"],
        "Earnings backed by cash" if (c["cfo"] is not None and c["net_income"] is not None and c["cfo"] > c["net_income"]) else "Accrual-heavy or n/a")
    lev_c = ratio(c["total_debt"], c["total_assets"])
    lev_p = ratio(p["total_debt"], p["total_assets"])
    add("Leverage falling", None if (lev_c is None or lev_p is None) else lev_c < lev_p,
        f"Debt/Assets {lev_p:.2%} -> {lev_c:.2%}" if lev_c is not None and lev_p is not None else "n/a")
    cr_c = ratio(c["current_assets"], c["current_liabilities"])
    cr_p = ratio(p["current_assets"], p["current_liabilities"])
    add("Current ratio improving", None if (cr_c is None or cr_p is None) else cr_c > cr_p,
        f"CR {cr_p:.2f} -> {cr_c:.2f}" if cr_c is not None and cr_p is not None else "n/a")
    add("No dilution", None if (c["shares"] is None or p["shares"] is None) else c["shares"] <= p["shares"],
        "Share count not increased" if (c["shares"] is not None and p["shares"] is not None and c["shares"] <= p["shares"]) else "Share count increased or n/a")
    gm_c = ratio((c["revenue"] or 0) - (c["cogs"] or 0), c["revenue"]) if c["cogs"] is not None else None
    gm_p = ratio((p["revenue"] or 0) - (p["cogs"] or 0), p["revenue"]) if p["cogs"] is not None else None
    add("Gross margin improving", None if (gm_c is None or gm_p is None) else gm_c > gm_p,
        f"GM {gm_p:.2%} -> {gm_c:.2%}" if gm_c is not None and gm_p is not None else "n/a")
    at_c = ratio(c["revenue"], c["total_assets"])
    at_p = ratio(p["revenue"], p["total_assets"])
    add("Asset turnover improving", None if (at_c is None or at_p is None) else at_c > at_p,
        f"Turnover {at_p:.2f} -> {at_c:.2f}" if at_c is not None and at_p is not None else "n/a")

    available = [x for x in checks if x["passed"] is not None]
    score = sum(1 for x in available if x["passed"])
    if len(available) < 5:
        rating = "Insufficient data"
    elif score >= 7:
        rating = "Strong"
    elif score >= 4:
        rating = "Moderate"
    else:
        rating = "Weak"
    return {"score": score, "max_score": len(available), "checks_available": len(available),
            "checks": checks, "rating": rating,
            "note": "Scored out of the checks that could be computed from reported statements."}


def quality_metrics(fundamentals: Dict[str, Any], financials: Dict[str, Any]) -> Dict[str, Any]:
    """Core quality ratios from the latest reported year, all derived from statements where possible."""
    inp = extract_inputs(financials)
    h = inp["history"]
    out: Dict[str, Any] = {}
    if not h:
        return out
    c = h[0]
    equity = c["equity"]
    if c["net_income"] is not None and equity:
        out["roe_pct"] = round(c["net_income"] / equity * 100, 2)
    if c["ebit"] is not None and c["total_assets"] is not None and c["current_liabilities"] is not None:
        ce = c["total_assets"] - c["current_liabilities"]
        if ce > 0:
            out["roce_pct"] = round(c["ebit"] / ce * 100, 2)
    if c["total_debt"] is not None and equity:
        out["debt_to_equity"] = round(c["total_debt"] / equity, 2)
    if c["ebit"] is not None and c["interest"]:
        out["interest_coverage"] = round(c["ebit"] / c["interest"], 2)
    if c["revenue"] and c["ebit"] is not None:
        out["ebit_margin_pct"] = round(c["ebit"] / c["revenue"] * 100, 2)
    if c["cfo"] is not None and c["net_income"]:
        out["cash_conversion"] = round(c["cfo"] / c["net_income"], 2)
    revs = [x["revenue"] for x in h if x["revenue"]]
    if len(revs) >= 2 and revs[-1] > 0 and revs[0] > 0:
        out["revenue_cagr_pct"] = round(((revs[0] / revs[-1]) ** (1 / (len(revs) - 1)) - 1) * 100, 2)
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_valuation(fundamentals: Dict[str, Any], financials: Dict[str, Any],
                  peer_ev_ebitda: Optional[float] = None) -> Dict[str, Any]:
    """
    Full research valuation for one company.

    fundamentals: output of DataFetcher.fetch_quote_and_fundamentals (snake_case keys, INR absolute)
    financials:   output of DataFetcher.fetch_financial_statements
    peer_ev_ebitda: optional live peer-median EV/EBITDA; if absent a sector assumption is used and flagged
    """
    gaps: List[str] = []
    assumptions: Dict[str, Any] = {}
    if not (financials.get("currency") or {}).get("reported_currency"):
        gaps.append("Statement currency could not be confirmed; figures are used as reported")

    price = num(fundamentals.get("current_price")) or 0.0
    mcap = num(fundamentals.get("market_cap")) or 0.0
    sector = fundamentals.get("sector")
    industry = fundamentals.get("industry")
    financial = is_financial(sector, industry)
    if not sector or sector == "Diversified":
        gaps.append("Sector unavailable; generic sector multiple used for EV/EBITDA")

    inp = extract_inputs(financials)
    h = inp["history"]
    if not h:
        return _not_applicable("No financial statements available from Yahoo Finance.", financial, price)
    c = h[0]

    shares = num(fundamentals.get("shares_outstanding")) or c["shares"]
    if not shares and price > 0 and mcap > 0:
        shares = mcap / price
        gaps.append("Share count derived as market cap / price")
    if not shares or shares <= 0:
        return _not_applicable("Share count unavailable.", financial, price)
    if not mcap and price:
        mcap = price * shares

    # Cost of capital
    rf = settings.INDIA_10Y_GSEC_DEFAULT / 100.0
    erp = settings.EQUITY_RISK_PREMIUM_DEFAULT / 100.0
    beta = num(fundamentals.get("beta"))
    if beta is None:
        gaps.append("Beta unavailable; default 1.0 used")
    ke_info = cost_of_equity(beta, rf, erp)
    ke = ke_info["ke"]

    tax_raw = None
    if c["pretax"] and c["tax"] is not None and c["pretax"] > 0:
        tax_raw = c["tax"] / c["pretax"]
    tax = clamp(tax_raw, *TAX_BOUNDS) if tax_raw is not None else TAX_DEFAULT
    if tax_raw is None:
        gaps.append("Effective tax rate unavailable; statutory 25.17% used")

    debt = c["total_debt"] or 0.0
    if c["total_debt"] is None:
        gaps.append("Total debt not reported; treated as zero")
    cash = c["cash"] or 0.0
    if c["cash"] is None:
        gaps.append("Cash balance not reported; treated as zero")
    minority = c["minority"] or 0.0

    # Growth from reported revenue history
    revs = [x["revenue"] for x in h if x["revenue"] and x["revenue"] > 0]
    if len(revs) >= 2:
        cagr = (revs[0] / revs[-1]) ** (1 / (len(revs) - 1)) - 1
        g_hist = clamp(cagr, *REV_CAGR_BOUNDS)
        g_src = f"{len(revs)-1}-year revenue CAGR, clamped to -5%..15%"
    else:
        g_hist = REV_CAGR_DEFAULT
        g_src = "default 8% (fewer than two years of revenue)"
        gaps.append("Less than two years of revenue; default growth used")

    result: Dict[str, Any] = {
        "symbol": fundamentals.get("symbol"),
        "company_name": fundamentals.get("company_name"),
        "sector": sector,
        "industry": industry,
        "is_financial_institution": financial,
        "current_price": round(price, 2),
        "shares_outstanding_cr": round(shares / 1e7, 4),
        "inputs": {
            "risk_free_rate_pct": round(rf * 100, 2),
            "equity_risk_premium_pct": round(erp * 100, 2),
            "beta": round(ke_info["beta"], 2),
            "beta_source": ke_info["beta_source"],
            "cost_of_equity_pct": round(ke * 100, 2),
            "tax_rate_pct": round(tax * 100, 2),
            "revenue_growth_pct": round(g_hist * 100, 2),
            "revenue_growth_source": g_src,
            "terminal_growth_pct": round(TERMINAL_GROWTH * 100, 2),
            "total_debt_cr": round(debt / 1e7, 2),
            "cash_cr": round(cash / 1e7, 2),
            "minority_interest_cr": round(minority / 1e7, 2),
        },
        "cross_checks": {},
        "sensitivity": {},
        "history_years": len(h),
    }

    primary = None  # (code, label, value_per_share, detail, rationale)
    notes: List[str] = []

    # ---------- Financials: FCFE ----------
    if financial:
        ni0 = c["net_income"]
        eq_now = c["equity"]
        eq_prev = h[1]["equity"] if len(h) > 1 else None
        avg_eq = (eq_now + eq_prev) / 2 if (eq_now and eq_prev) else eq_now
        if ni0 and ni0 > 0 and avg_eq and avg_eq > 0:
            roe = ni0 / avg_eq
            payout = clamp(c["dividends"] / ni0, 0.0, 0.9) if c["dividends"] is not None else DEFAULT_PAYOUT
            if c["dividends"] is None:
                gaps.append("Dividend history unavailable; 20% payout assumed for sustainable growth")
            g_sust = clamp(roe * (1 - payout), 0.0, SUSTAINABLE_G_CAP)
            if ke > TERMINAL_GROWTH + MIN_WACC_SPREAD:
                fc = fcfe_equity(ni0, roe, g_sust, ke, TERMINAL_GROWTH)
                vps = fc["equity_value"] / shares
                result["cross_checks"]["FCFE"] = {
                    "value_per_share": round(vps, 2),
                    "equity_value_cr": round(fc["equity_value"] / 1e7, 2),
                    "projections": fc["projections"],
                }
                result["inputs"].update({
                    "roe_pct": round(roe * 100, 2), "payout_pct": round(payout * 100, 2),
                    "sustainable_growth_pct": round(g_sust * 100, 2)})
                # P/B-ROE cross-check
                bvps = eq_now / shares if eq_now else None
                if bvps:
                    pb_fair = max(0.0, (roe - TERMINAL_GROWTH) / (ke - TERMINAL_GROWTH))
                    result["cross_checks"]["P_B_ROE"] = {
                        "value_per_share": round(pb_fair * bvps, 2),
                        "target_pb": round(pb_fair, 2),
                        "book_value_per_share": round(bvps, 2)}
                primary = ("FCFE", "FCFE (sustainable-growth, Ke-discounted)", vps, fc,
                           "Financial institution: debt is raw material, so free cash flow to equity is the "
                           "correct cash-flow measure. Growth is capped at ROE x retention.")
            else:
                notes.append("Cost of equity too close to terminal growth for a stable FCFE model.")
        else:
            notes.append("Net income or equity is non-positive; FCFE not meaningful.")
    else:
        # ---------- Non-financials: FCFF ----------
        margins = []
        fcff_hist = []
        for x in h[:3]:
            if x["revenue"] and x["revenue"] > 0 and x["cfo"] is not None and x["capex"] is not None:
                fcff_i = x["cfo"] + (x["interest"] or 0.0) * (1 - tax) - x["capex"]
                fcff_hist.append(round(fcff_i / 1e7, 2))
                margins.append(fcff_i / x["revenue"])
        if margins:
            margin = sum(margins) / len(margins)
        else:
            margin = None

        if margin is not None and margin > 0 and c["revenue"]:
            rev0 = c["revenue"]
            nopat0 = (c["ebit"] * (1 - tax)) if c["ebit"] is not None else None
            ic = (c["equity"] or 0) + debt - cash + minority
            roic = (nopat0 / ic) if (nopat0 and ic > 0) else None
            wi = wacc_build(mcap, debt, c["interest"], tax, rf, ke)
            wacc = wi["wacc"]
            ronic = wacc if roic is None else max(wacc, min(roic, RONIC_CAP))
            if roic is None:
                gaps.append("ROIC unavailable; RONIC set equal to WACC (no value creation on new capital)")
            result["inputs"].update({
                "wacc_pct": round(wacc * 100, 2), "kd_pct": round(wi["kd"] * 100, 2),
                "kd_source": wi["kd_source"], "equity_weight_pct": round(wi["weight_equity"] * 100, 2),
                "normalised_fcff_margin_pct": round(margin * 100, 2),
                "fcff_history_cr": fcff_hist,
                "roic_pct": round(roic * 100, 2) if roic is not None else None,
                "ronic_pct": round(ronic * 100, 2)})
            if wacc - TERMINAL_GROWTH >= MIN_WACC_SPREAD:
                base = fcff_dcf(rev0, margin, nopat0, g_hist, wacc, ronic, TERMINAL_GROWTH)
                ev = base["enterprise_value"]
                eq = _bridge_to_equity(ev, debt, cash, minority)
                vps = eq / shares
                # Sensitivity: WACC +/-1pp (0.5pp steps) x terminal growth +/-0.5pp
                grid = []
                for dw in (-0.01, -0.005, 0.0, 0.005, 0.01):
                    row = []
                    for dg in (-0.005, 0.0, 0.005):
                        w2, g2 = wacc + dw, TERMINAL_GROWTH + dg
                        if w2 - g2 < MIN_WACC_SPREAD:
                            row.append(None)
                            continue
                        r2 = fcff_dcf(rev0, margin, nopat0, g_hist, w2, max(w2, min(roic or w2, RONIC_CAP)), g2)
                        row.append(round(_bridge_to_equity(r2["enterprise_value"], debt, cash, minority) / shares, 2))
                    grid.append(row)
                result["sensitivity"] = {
                    "wacc_pct": [round((wacc + d) * 100, 2) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)],
                    "terminal_growth_pct": [round((TERMINAL_GROWTH + d) * 100, 2) for d in (-0.005, 0.0, 0.005)],
                    "value_per_share_grid": grid}
                result["cross_checks"]["FCFF"] = {
                    "value_per_share": round(vps, 2),
                    "enterprise_value_cr": round(ev / 1e7, 2),
                    "equity_value_cr": round(eq / 1e7, 2),
                    "pv_explicit_cr": round(base["pv_explicit"] / 1e7, 2),
                    "pv_terminal_cr": round(base["pv_terminal"] / 1e7, 2),
                    "terminal_method": base["terminal_method"],
                    "projections": base["projections"],
                }
                primary = ("FCFF", "FCFF (2-stage DCF, value-driver terminal)", vps, base,
                           "Non-financial company with positive normalised free cash flow to the firm. "
                           "FCFF is discounted at WACC, which is independent of the capital structure.")
            else:
                notes.append("WACC too close to terminal growth for a stable DCF.")
        else:
            notes.append("Normalised FCFF is non-positive: growth capex exceeds operating cash flow.")
            nopat_hist = []
            roic_hist = []
            for x in h[:3]:
                if x["ebit"] is not None:
                    nop_i = x["ebit"] * (1 - tax)
                    nopat_hist.append(nop_i)
                    ic_i = (x["equity"] or 0) + (x["total_debt"] or 0) - (x["cash"] or 0) + (x["minority"] or 0)
                    if ic_i > 0:
                        roic_hist.append(nop_i / ic_i)
            if nopat_hist and nopat_hist[0] > 0 and c["revenue"]:
                nopat_norm = sum(nopat_hist) / len(nopat_hist)
                wi_vd = wacc_build(mcap, debt, c["interest"], tax, rf, ke)
                wacc_vd = wi_vd["wacc"]
                roic_avg = (sum(roic_hist) / len(roic_hist)) if roic_hist else None
                ronic_base = max(wacc_vd, min(roic_avg, RONIC_CAP)) if roic_avg is not None else wacc_vd
                ronic_bull = min(ronic_base + 0.05, RONIC_CAP)
                g_vd = min(g_hist, 0.12)
                if wacc_vd - TERMINAL_GROWTH >= MIN_WACC_SPREAD:
                    scen = {}
                    for name, rv in (("bear", wacc_vd), ("base", ronic_base), ("bull", ronic_bull)):
                        ev_s = value_driver_ev(nopat_norm, g_vd, wacc_vd, rv, TERMINAL_GROWTH)
                        eq_s = _bridge_to_equity(ev_s, debt, cash, minority)
                        scen[name] = {"ronic_pct": round(rv * 100, 2),
                                      "value_per_share": round(max(0.0, eq_s / shares), 2),
                                      "enterprise_value_cr": round(ev_s / 1e7, 2)}
                    market_ev = mcap + debt - cash + minority
                    k = _implied_nopat_multiple(market_ev, nopat_norm, g_vd, wacc_vd, ronic_base, TERMINAL_GROWTH)
                    result["cross_checks"]["VALUE_DRIVER"] = {
                        "scenarios": scen,
                        "nopat_normalised_cr": round(nopat_norm / 1e7, 2),
                        "roic_avg_pct": round(roic_avg * 100, 2) if roic_avg is not None else None,
                        "market_implied_nopat_multiple": round(k, 2),
                        "market_implied_nopat_cr": round(k * nopat_norm / 1e7, 2),
                    }
                    result["inputs"].update({
                        "wacc_pct": round(wacc_vd * 100, 2),
                        "revenue_growth_pct": round(g_vd * 100, 2),
                        "normalised_nopat_cr": round(nopat_norm / 1e7, 2),
                        "roic_avg_pct": round(roic_avg * 100, 2) if roic_avg is not None else None,
                    })
                    base_vps = scen["base"]["value_per_share"]
                    primary = ("VALUE_DRIVER", "Normalised-earnings value (capital-intensive)", base_vps, scen,
                               "Free cash flow is negative because growth capex exceeds operating cash flow, so "
                               "value is set by normalised after-tax operating profit net of the reinvestment that "
                               "growth requires. The range reflects the return earned on new capital.")
                    notes.append("Current return on capital is shown against the cost of capital; the market price "
                                 "implies a multiple of today's normalised profit (see cross-checks).")
            if primary is None:
                notes.append("Normalised profit is non-positive; no earnings-based value.")

    # ---------- EV/EBITDA (relative): primary for non-financials with negative FCFF, always a cross-check ----------
    ebitda = c["ebitda"]
    if financial:
        pass  # EV/EBITDA is not meaningful for banks: interest is their operating cost
    elif ebitda and ebitda > 0:
        if peer_ev_ebitda and 3.0 <= peer_ev_ebitda <= 60.0:
            mult, mult_src = peer_ev_ebitda, "Live peer median EV/EBITDA"
        else:
            mult = _sector_default_multiple(sector)
            mult_src = "Sector assumption (no live peer multiple supplied; review before relying on it)"
        ev_rel = mult * ebitda
        eq_rel = _bridge_to_equity(ev_rel, debt, cash, minority)
        vps_rel = eq_rel / shares
        result["cross_checks"]["EV_EBITDA"] = {
            "value_per_share": round(vps_rel, 2),
            "multiple_used": round(mult, 2),
            "multiple_source": mult_src,
            "ebitda_cr": round(ebitda / 1e7, 2),
            "implied_ev_cr": round(ev_rel / 1e7, 2),
        }
        # Reliability checks for a relative multiple. If either fails, the number is not reported as a value.
        reliability_issue = None
        if primary is None and not financial:
            net_debt = debt - cash + minority
            if ev_rel > 0 and net_debt / ev_rel > MAX_NET_DEBT_SHARE_OF_EV:
                reliability_issue = (
                    f"Net debt is {net_debt / ev_rel:.0%} of the implied enterprise value, so the equity value "
                    "is a thin residual that swings sharply with the multiple. No intrinsic value is reported.")
            market_ev = num(fundamentals.get("enterprise_value"))
            if reliability_issue is None and market_ev and ebitda and market_ev / ebitda > MAX_MARKET_TO_BENCHMARK_MULTIPLE * mult:
                reliability_issue = (
                    f"The market prices the company at {market_ev / ebitda:.0f}x trailing EBITDA against a benchmark of "
                    f"{mult:.0f}x. Trailing-earnings multiples cannot explain that gap, so no intrinsic value is reported.")
        if reliability_issue:
            notes.append(reliability_issue)
        elif primary is None and not financial:
            if not mult_src.startswith("Live"):
                gaps.append("EV/EBITDA is the primary method and uses a sector assumption, not a live peer median")
            primary = ("EV_EBITDA", "EV/EBITDA (relative valuation)", vps_rel,
                       {"multiple": mult, "source": mult_src},
                       "FCFF is negative on a normalised basis, so an intrinsic DCF is unreliable. "
                       "Valued on EV/EBITDA against peers, because EBITDA is the more stable earnings base.")
    elif primary is None:
        notes.append("EBITDA is non-positive; relative valuation not meaningful.")

    if primary is None:
        return _not_applicable(" ".join(notes) or "No applicable valuation method.", financial, price, result)

    code, label, vps, detail, rationale = primary
    intrinsic = round(vps, 2)
    if code == "VALUE_DRIVER" and intrinsic <= 0:
        result.update({
            "method_code": code, "primary_method": label, "method_rationale": rationale,
            "is_applicable": True, "intrinsic_value": 0.0, "blended_intrinsic_value": 0.0,
            "margin_of_safety_pct": None, "valuation_label": "No Value on Current Earnings",
            "verdict_color": "rose", "data_gaps": gaps, "confidence": "Low",
            "confidence_reason": ("On current returns the business does not earn its cost of capital after its debt, "
                                  "so equity has no value on present earnings. Value depends on the expansion succeeding."),
            "notes": notes,
        })
        return result
    if intrinsic <= 0:
        # Debt exceeds the modelled enterprise value (or equity is otherwise negative): no meaningful per-share value.
        return _not_applicable(
            f"{label} implies non-positive equity value (net debt exceeds modelled enterprise value). "
            "No intrinsic value is reported.", financial, price, result)
    mos = round((intrinsic - price) / intrinsic * 100, 2) if price > 0 else None
    vlabel, vcolor = _valuation_label(mos)

    result.update({
        "method_code": code,
        "primary_method": label,
        "method_rationale": rationale,
        "is_applicable": True,
        "intrinsic_value": intrinsic,
        "blended_intrinsic_value": intrinsic,  # kept for backward compatibility
        "margin_of_safety_pct": mos,
        "valuation_label": vlabel,
        "verdict_color": vcolor,
        "data_gaps": gaps,
        "confidence": "High" if len(gaps) == 0 else ("Medium" if len(gaps) <= 2 else "Low"),
        "confidence_reason": (
            "All required statement inputs were reported." if not gaps
            else f"{len(gaps)} input gap(s) or assumption(s) affect this estimate."),
        "notes": notes,
    })
    return result


def _not_applicable(reason: str, financial: bool, price: float, partial: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = dict(partial or {})
    base.update({
        "method_code": "NA",
        "primary_method": "Not applicable",
        "method_rationale": reason,
        "is_applicable": False,
        "is_financial_institution": financial,
        "intrinsic_value": None,
        "blended_intrinsic_value": None,
        "margin_of_safety_pct": None,
        "valuation_label": "Not Applicable",
        "verdict_color": "slate",
        "data_gaps": base.get("data_gaps", []),
        "confidence": "Low",
        "confidence_reason": reason,
        "current_price": round(price, 2),
    })
    base.setdefault("cross_checks", {})
    base.setdefault("sensitivity", {})
    return base
