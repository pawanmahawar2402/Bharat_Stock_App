"""
Derives valuation ratios from reported statements when a quote source leaves them blank.
Only fills gaps; it never overrides a value another source supplied. Uses the price and
share count already in the merge context, so it adds no new market-data dependency.
"""
import math
from typing import Any, Dict, Optional

from app.sources.base import DataSource


def _num(x):
    try:
        v = float(x)
        return None if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


def _latest(stmt: Optional[Dict[str, Dict[str, Any]]], item: str) -> Optional[float]:
    if not stmt:
        return None
    for period in sorted(stmt.keys(), reverse=True):
        v = _num(stmt[period].get(item))
        if v is not None:
            return v
    return None


class StatementDerivedSource(DataSource):
    name = "statement_derived"
    capabilities = frozenset({"fundamentals"})

    def fetch_fundamentals(self, symbol: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        stmts = context.get("_statements")
        price = _num(context.get("current_price"))
        shares = _num(context.get("shares_outstanding")) or _latest(
            (stmts or {}).get("balance_sheet"), "Ordinary Shares Number")
        if not stmts or not shares or shares <= 0:
            return None

        ni = _latest(stmts.get("income_statement"), "Net Income Common Stockholders") or \
            _latest(stmts.get("income_statement"), "Net Income")
        equity = _latest(stmts.get("balance_sheet"), "Stockholders Equity") or \
            _latest(stmts.get("balance_sheet"), "Common Stock Equity")
        debt = _latest(stmts.get("balance_sheet"), "Total Debt")

        out: Dict[str, Any] = {}
        if ni is not None:
            eps = ni / shares
            out["eps_trailing"] = round(eps, 2)
            if price and eps > 0:
                out["trailing_pe"] = round(price / eps, 2)
        if equity:
            bvps = equity / shares
            out["book_value"] = round(bvps, 2)
            if price and bvps > 0:
                out["price_to_book"] = round(price / bvps, 2)
            if ni is not None:
                out["return_on_equity"] = round(ni / equity, 4)   # decimal, Yahoo convention
            if debt is not None:
                out["debt_to_equity"] = round(debt / equity * 100, 2)  # percent, Yahoo convention
        return out or None
