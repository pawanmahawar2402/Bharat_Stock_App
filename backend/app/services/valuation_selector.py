"""
Chooses the valuation method that fits each company and reports the intrinsic value per share.

Primary method, in order:
  * Financial institutions        -> justified P/B from ROE (book value adjusted for returns)
  * Profitable companies          -> P/E at the sector peer median, applied to trailing EPS
  * Positive EBITDA only         -> EV/EBITDA at the sector peer median, bridged to equity
  * Revenue, no earnings         -> P/S at the sector peer median
  * Otherwise                    -> book value per share (asset-based)

Cash-flow and growth models (DCF, FCFE, value-driver, DDM) stay as cross-checks so the
headline value can be compared with the model that reflects cash generation.
The result is flagged whenever it departs from the market price by more than 50%.
"""

from typing import Any, Dict, Optional

from app.services import fundamental_engine as fe

LARGE_GAP_PCT = 50.0


def _num(x) -> Optional[float]:
    return fe.num(x)


def value_company(fund: Dict[str, Any], fin: Dict[str, Any], peers: Optional[Dict[str, Optional[float]]] = None) -> Dict[str, Any]:
    peers = peers or {}
    base = fe.run_valuation(fund, fin, peer_ev_ebitda=peers.get("ev_ebitda"))
    cross = dict(base.get("cross_checks", {}))
    gaps = list(base.get("data_gaps", []))
    price = _num(fund.get("current_price")) or 0.0
    shares_cr = _num(base.get("shares_outstanding_cr"))
    shares = shares_cr * 1e7 if shares_cr else None

    hist = fe.extract_inputs(fin)["history"] if fin else []
    c0 = hist[0] if hist else {}
    eps = _num(fund.get("eps_trailing"))
    if eps is None and c0.get("net_income") and shares:
        eps = c0["net_income"] / shares
    bvps = _num(fund.get("book_value"))
    if bvps is None and c0.get("equity") and shares:
        bvps = c0["equity"] / shares
    sps = (c0["revenue"] / shares) if (c0.get("revenue") and shares) else None
    inputs = base.get("inputs", {})

    value = None
    code = None
    label = None
    rationale = None

    if base.get("is_financial_institution") and "P_B_ROE" in cross:
        value = cross["P_B_ROE"]["value_per_share"]
        code, label = "JUSTIFIED_PB", "Justified P/B (ROE model)"
        rationale = "Lender: value follows the return on equity relative to the cost of equity, applied to book value."
    elif eps and eps > 0 and peers.get("pe"):
        value = eps * peers["pe"]
        code, label = "RELATIVE_PE", "Relative P/E (sector peers)"
        rationale = "Profitable company: earnings priced at the sector's median P/E."
    elif c0.get("ebitda") and c0["ebitda"] > 0 and peers.get("ev_ebitda") and shares:
        ebitda_cr = c0["ebitda"] / 1e7
        eq_cr = (peers["ev_ebitda"] * ebitda_cr - inputs.get("total_debt_cr", 0)
                 + inputs.get("cash_cr", 0) - inputs.get("minority_interest_cr", 0))
        value = eq_cr * 1e7 / shares
        code, label = "RELATIVE_EV_EBITDA", "Relative EV/EBITDA (sector peers)"
        rationale = "Earnings are not yet positive: enterprise value at the sector's median EV/EBITDA, less net debt."
    elif sps and peers.get("ps"):
        value = sps * peers["ps"]
        code, label = "RELATIVE_PS", "Relative price to sales (sector peers)"
        rationale = "Loss-making company: revenue priced at the sector's median price-to-sales."
    elif bvps and bvps > 0 and price > 0 and price / bvps <= 1.5:
        # Asset-based value is meaningful only for businesses that trade close to their book value
        value = bvps
        code, label = "ASSET_BASED", "Book value (asset-based)"
        rationale = "Trades close to net asset value with no reliable earnings or revenue multiple."

    if value is None or value <= 0:
        # No comparable companies: fall back to the company's own cash-flow models, so a value is always reported
        fallbacks = [
            ("FCFF", "DCF_FALLBACK", "Discounted cash flow (no comparable companies)",
             "No comparable companies were available, so the value comes from the company's own cash flows."),
            ("FCFE", "FCFE_FALLBACK", "Equity cash flow (no comparable companies)",
             "No comparable companies were available, so the value comes from the company's own equity cash flows."),
            ("P_B_ROE", "JUSTIFIED_PB", "Justified P/B (ROE model)",
             "Value follows the return on equity relative to the cost of equity, applied to book value."),
        ]
        vd = cross.get("VALUE_DRIVER", {}).get("scenarios", {}).get("base", {}).get("value_per_share")
        for key, fcode, flabel, frat in fallbacks:
            v = cross.get(key, {}).get("value_per_share") if key != "VALUE_DRIVER" else None
            if v and v > 0:
                value, code, label, rationale = v, fcode, flabel, frat
                break
        if (value is None or value <= 0) and vd and vd > 0:
            value, code, label = vd, "VALUE_DRIVER_FALLBACK", "Normalised earnings (no comparable companies)"
            rationale = "No comparable companies were available, so the value comes from normalised operating profit."
        if (value is None or value <= 0) and bvps and bvps > 0:
            value, code, label = bvps, "ASSET_BASED", "Book value (asset-based)"
            rationale = "Only net asset value per share was available."

    if not peers and code not in ("JUSTIFIED_PB", "ASSET_BASED"):
        gaps.append("Sector peer multiples unavailable; intrinsic value uses the company's own figures")

    if value is None or value <= 0:
        base["is_applicable"] = False
        base["intrinsic_value"] = None
        base["blended_intrinsic_value"] = None
        base["margin_of_safety_pct"] = None
        base["method_code"] = "NA"
        base["primary_method"] = "Not applicable"
        base["method_rationale"] = ("Not enough comparable companies to set a reliable value. "
                                    "No intrinsic value is reported.")
        base["confidence"] = "Low"
        base["confidence_reason"] = base["method_rationale"]
        base["data_gaps"] = gaps
        return base

    intrinsic = round(value, 2)
    cross.update({
        "PE_PEERS": {"value_per_share": round(eps * peers["pe"], 2) if eps and peers.get("pe") else None,
                     "peer_pe": peers.get("pe")},
        "PB_PEERS": {"value_per_share": round(bvps * peers["pb"], 2) if bvps and peers.get("pb") else None,
                     "peer_pb": peers.get("pb")},
        "PS_PEERS": {"value_per_share": round(sps * peers["ps"], 2) if sps and peers.get("ps") else None,
                     "peer_ps": peers.get("ps")},
    })
    mos = round((intrinsic - price) / intrinsic * 100, 2) if price > 0 and intrinsic > 0 else None
    gap_pct = round((intrinsic - price) / price * 100, 2) if price > 0 else None
    if gap_pct is not None and abs(gap_pct) > LARGE_GAP_PCT:
        gaps.append("Intrinsic value differs from the market price by more than 50%; review the assumptions")
    vlabel, vcolor = fe._valuation_label(mos)
    base.update({
        "method_code": code,
        "primary_method": label,
        "method_rationale": rationale,
        "is_applicable": True,
        "intrinsic_value": intrinsic,
        "blended_intrinsic_value": intrinsic,
        "margin_of_safety_pct": mos,
        "market_gap_pct": gap_pct,
        "valuation_label": vlabel,
        "verdict_color": vcolor,
        "data_gaps": gaps,
        "confidence": "High" if len(gaps) == 0 else ("Medium" if len(gaps) <= 2 else "Low"),
        "confidence_reason": ("Primary value and inputs are consistent with the sector." if not gaps
                              else f"{len(gaps)} input gap(s) or assumption(s) affect this estimate."),
        "cross_checks": cross,
    })
    return base
