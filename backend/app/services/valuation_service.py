import math
import logging
from typing import Dict, Any, Optional
from app.config import settings
from app.services import fundamental_engine as fe

logger = logging.getLogger(__name__)


class ValuationEngine:
    """
    Facade over the statement-driven research engine (fundamental_engine.py) plus the
    legacy building blocks (2-stage DCF, Graham formulas, Justified P/B) kept for the
    sensitivity simulator and back-compatibility.

    The primary intrinsic value now comes from ONE method chosen per company:
      FCFE (financials) | FCFF (non-financials, positive FCFF) | EV/EBITDA (negative FCFF).
    """

    @staticmethod
    def is_financial_firm(sector: str, industry: str) -> bool:
        return fe.is_financial(sector, industry)

    @staticmethod
    def calculate_dcf(
        fcf_cr: float,
        shares_cr: float,
        growth_rate_stage1: float = 0.12,
        growth_rate_stage2: float = 0.07,
        terminal_growth: float = 0.045,
        wacc: float = 0.115,
        cash_cr: float = 0.0,
        debt_cr: float = 0.0,
        margin_of_safety_pct: float = 0.20
    ) -> Dict[str, Any]:
        """
        Interactive 2-stage DCF used by the sensitivity simulator (user-supplied inputs).
        Returns intrinsic value per share and safety-margin value.
        """
        if fcf_cr <= 0 or shares_cr <= 0 or wacc <= terminal_growth:
            return {
                "method": "DCF",
                "is_applicable": False,
                "intrinsic_value": 0.0,
                "fair_value_with_mos": 0.0,
                "reason": "Negative or zero Free Cash Flow, or invalid WACC parameters."
            }

        pv_fcf_sum = 0.0
        current_fcf = fcf_cr
        projected_fcfs = []

        for t in range(1, 6):
            current_fcf *= (1 + growth_rate_stage1)
            pv = current_fcf / ((1 + wacc) ** t)
            pv_fcf_sum += pv
            projected_fcfs.append({"year": t, "fcf": round(current_fcf, 2), "pv": round(pv, 2)})

        for t in range(6, 11):
            fade_growth = growth_rate_stage1 - ((growth_rate_stage1 - growth_rate_stage2) * ((t - 5) / 5))
            current_fcf *= (1 + fade_growth)
            pv = current_fcf / ((1 + wacc) ** t)
            pv_fcf_sum += pv
            projected_fcfs.append({"year": t, "fcf": round(current_fcf, 2), "pv": round(pv, 2)})

        terminal_fcf = current_fcf * (1 + terminal_growth)
        terminal_value = terminal_fcf / (wacc - terminal_growth)
        pv_terminal_value = terminal_value / ((1 + wacc) ** 10)

        enterprise_value = pv_fcf_sum + pv_terminal_value
        equity_value = enterprise_value + cash_cr - debt_cr
        intrinsic_value = max(0.0, equity_value / shares_cr)
        fair_value_with_mos = intrinsic_value * (1 - margin_of_safety_pct)

        return {
            "method": "DCF",
            "is_applicable": True,
            "intrinsic_value": round(intrinsic_value, 2),
            "fair_value_with_mos": round(fair_value_with_mos, 2),
            "enterprise_value_cr": round(enterprise_value, 2),
            "equity_value_cr": round(equity_value, 2),
            "pv_fcf_sum_cr": round(pv_fcf_sum, 2),
            "pv_terminal_value_cr": round(pv_terminal_value, 2),
            "wacc": round(wacc * 100, 2),
            "terminal_growth": round(terminal_growth * 100, 2),
            "projected_fcfs": projected_fcfs
        }

    @staticmethod
    def calculate_graham_valuation(
        eps: float,
        book_value: float,
        expected_growth_rate: float = 10.0,
        india_10y_yield: float = 6.80
    ) -> Dict[str, Any]:
        """
        Graham Number (cross-check only; not a primary method).
        Revised Graham Formula: V = EPS * (8.5 + 2g) * 4.4 / Y
        """
        graham_number = 0.0
        if eps > 0 and book_value > 0:
            graham_number = round(math.sqrt(22.5 * eps * book_value), 2)

        graham_formula_value = 0.0
        if eps > 0 and india_10y_yield > 0:
            g = min(expected_growth_rate, 20.0)
            graham_formula_value = round((eps * (8.5 + (2 * g)) * 4.4) / india_10y_yield, 2)

        return {
            "graham_number": graham_number,
            "graham_formula_value": graham_formula_value,
            "is_applicable": graham_number > 0 or graham_formula_value > 0
        }

    @staticmethod
    def calculate_bank_valuation(
        book_value: float,
        roe: float,
        cost_of_equity: float = 0.125,
        long_term_growth: float = 0.06
    ) -> Dict[str, Any]:
        """
        Justified P/B - ROE Model: Target P/B = (ROE - g) / (Ke - g).
        """
        if book_value <= 0 or cost_of_equity <= long_term_growth:
            return {"is_applicable": False, "intrinsic_value": 0.0, "target_pb": 0.0}

        roe_decimal = roe / 100.0 if roe > 1.0 else roe
        target_pb = max(0.0, (roe_decimal - long_term_growth) / (cost_of_equity - long_term_growth))
        intrinsic_value = round(target_pb * book_value, 2)

        return {
            "is_applicable": True,
            "method": "Justified P/B (ROE Model)",
            "target_pb": round(target_pb, 2),
            "book_value": round(book_value, 2),
            "roe_used": round(roe_decimal * 100, 2),
            "intrinsic_value": intrinsic_value
        }

    @staticmethod
    def compute_quality_scorecard(fundamentals: Dict[str, Any], financials: Dict[str, Any]) -> Dict[str, Any]:
        """
        0-100 quality score from reported ratios, plus a real 9-point Piotroski F-score
        computed from the statements. Piotroski is None when statements are unavailable
        (no synthetic default is produced).
        """
        score = 50.0
        breakdown = []

        roe = fe.num(fundamentals.get("return_on_equity"))
        if roe is not None:
            roe_pct = roe * 100 if abs(roe) < 1.0 else roe
            if roe_pct >= 20.0:
                score += 10
                breakdown.append("Exceptional ROE (>20%): +10")
            elif roe_pct >= 15.0:
                score += 6
                breakdown.append("Strong ROE (15-20%): +6")
            elif roe_pct < 8.0:
                score -= 8
                breakdown.append("Subpar ROE (<8%): -8")

        de = fe.num(fundamentals.get("debt_to_equity"))
        if de is not None:
            de_ratio = de / 100.0 if de > 5.0 else de
            if de_ratio < 0.3:
                score += 10
                breakdown.append("Virtually Debt-Free (D/E < 0.3): +10")
            elif de_ratio < 0.8:
                score += 5
                breakdown.append("Manageable Leverage (D/E < 0.8): +5")
            elif de_ratio > 2.0 and not fe.is_financial(fundamentals.get("sector", ""), fundamentals.get("industry", "")):
                score -= 10
                breakdown.append("High Leverage (D/E > 2.0): -10")

        fcf = fe.num(fundamentals.get("free_cashflow"))
        if fcf is not None and fcf > 0:
            score += 10
            breakdown.append("Positive Free Cash Flow Generation: +10")
        elif fcf is not None and fcf < 0:
            score -= 5
            breakdown.append("Negative Free Cash Flow: -5")

        peg = fe.num(fundamentals.get("peg_ratio"))
        if peg is not None and peg > 0:
            if peg < 1.0:
                score += 8
                breakdown.append("Attractive PEG (<1.0): +8")
            elif peg > 2.5:
                score -= 5
                breakdown.append("Expensive PEG (>2.5): -5")

        pio = fe.piotroski_fscore(financials) if financials else {"score": None, "checks": [], "rating": "Insufficient data"}
        pio_score = pio.get("score")
        if pio_score is not None and pio.get("checks_available", 0) >= 5:
            if pio_score >= 7:
                score += 5
                breakdown.append(f"Piotroski F-score {pio_score}/{pio['checks_available']} (strong): +5")
            elif pio_score <= 3:
                score -= 5
                breakdown.append(f"Piotroski F-score {pio_score}/{pio['checks_available']} (weak): -5")

        final_score = max(10, min(95, round(score)))
        return {
            "quality_score": final_score,
            "grade": "A+" if final_score >= 80 else ("A" if final_score >= 70 else ("B" if final_score >= 55 else "C")),
            "breakdown": breakdown,
            "piotroski_f_score": pio_score,
            "piotroski_max": pio.get("checks_available"),
            "piotroski_rating": pio.get("rating"),
            "piotroski_reasons": [f"{c['check']}: {'PASS' if c['passed'] else 'FAIL'} ({c['detail']})"
                                  for c in pio.get("checks", []) if c["passed"] is not None],
            "quality_metrics": fe.quality_metrics(fundamentals, financials) if financials else {},
        }

    @staticmethod
    def calculate_valuation_summary(fundamentals: Dict[str, Any], financials: Dict[str, Any],
                                    peer_ev_ebitda: Optional[float] = None) -> Dict[str, Any]:
        """
        Research valuation: one method per company (see fundamental_engine.run_valuation).
        Response keeps the keys the frontend already consumes.
        """
        res = fe.run_valuation(fundamentals, financials, peer_ev_ebitda=peer_ev_ebitda)
        quality = ValuationEngine.compute_quality_scorecard(fundamentals, financials)
        cmp = res.get("current_price", 0.0)
        inputs = res.get("inputs", {})
        cross = res.get("cross_checks", {})

        # Latest reported cash-flow figures in crores (from statements, not estimates)
        hist = fe.extract_inputs(financials)["history"] if financials else []
        c0 = hist[0] if hist else {}
        to_cr = lambda v: round(v / 1e7, 2) if isinstance(v, (int, float)) else None
        cfo_cr = to_cr(c0.get("cfo"))
        capex_cr = to_cr(c0.get("capex"))
        fcff_cr = round((c0["cfo"] + (c0.get("interest") or 0) * (1 - fe.TAX_DEFAULT) - c0["capex"]) / 1e7, 2) \
            if c0.get("cfo") is not None and c0.get("capex") is not None else None
        fcfe_cr = round((c0["cfo"] - c0["capex"] + (c0.get("net_borrowing") or 0)) / 1e7, 2) \
            if c0.get("cfo") is not None and c0.get("capex") is not None else None
        mcap_cr = (fundamentals.get("market_cap") or 0) / 1e7
        fcf_yield = round((fcfe_cr / mcap_cr) * 100, 2) if fcfe_cr and mcap_cr > 0 else None
        price_to_fcf = round(mcap_cr / fcfe_cr, 2) if fcfe_cr and fcfe_cr > 0 else "N/A"

        ev_raw = fe.num(fundamentals.get("enterprise_value"))
        ebitda_raw = c0.get("ebitda")
        fcff_block = cross.get("FCFF", {})
        legacy_dcf = {
            "method": "FCFF DCF (statement-based)",
            "is_applicable": "FCFF" in cross,
            "intrinsic_value": fcff_block.get("value_per_share", 0.0),
            "fair_value_with_mos": round((fcff_block.get("value_per_share", 0.0)) * (1 - 0.20), 2) if fcff_block else 0.0,
            "enterprise_value_cr": fcff_block.get("enterprise_value_cr"),
            "equity_value_cr": fcff_block.get("equity_value_cr"),
            "pv_fcf_sum_cr": fcff_block.get("pv_explicit_cr"),
            "pv_terminal_value_cr": fcff_block.get("pv_terminal_cr"),
            "wacc": inputs.get("wacc_pct"),
            "terminal_growth": inputs.get("terminal_growth_pct"),
            "projected_fcfs": [{"year": r["year"], "fcf": r["fcff_cr"], "pv": r["pv_cr"]}
                               for r in fcff_block.get("projections", [])],
        }

        return {
            "current_price": cmp,
            "primary_method": res.get("primary_method"),
            "method_code": res.get("method_code"),
            "method_rationale": res.get("method_rationale"),
            "is_applicable": res.get("is_applicable"),
            "intrinsic_value": res.get("intrinsic_value"),
            "blended_intrinsic_value": res.get("intrinsic_value"),
            "margin_of_safety_pct": res.get("margin_of_safety_pct"),
            "valuation_label": res.get("valuation_label"),
            "verdict_color": res.get("verdict_color"),
            "confidence": res.get("confidence"),
            "confidence_reason": res.get("confidence_reason"),
            "data_gaps": res.get("data_gaps", []),
            "models_used": [k for k in cross.keys()],
            "cross_checks": cross,
            "inputs": inputs,
            "sensitivity": res.get("sensitivity", {}),
            "is_financial_institution": res.get("is_financial_institution"),
            "dcf": legacy_dcf,
            "bank_model": cross.get("P_B_ROE", {}),
            "earnings_model": {"fair_pe_multiple": None, "fair_value": None},
            "valuation_multiples": {
                "enterprise_value_cr": round(ev_raw / 1e7, 2) if ev_raw else None,
                "ebitda_cr": to_cr(ebitda_raw),
                "ev_to_ebitda": fundamentals.get("enterprise_to_ebitda", "N/A"),
                "ev_to_sales": fundamentals.get("enterprise_to_revenue", "N/A"),
                "operating_cash_flow_cr": cfo_cr,
                "capex_cr": capex_cr,
                "fcff_cr": fcff_cr,
                "fcfe_cr": fcfe_cr,
                "fcf_yield_pct": fcf_yield,
                "price_to_fcf": price_to_fcf,
            },
            "quality_scorecard": quality,
        }
