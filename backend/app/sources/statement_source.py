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
        # Market and cash-flow measures derived from the statements and the current price
        revenue = _latest(stmts.get("income_statement"), "Total Revenue") or _latest(stmts.get("income_statement"), "Operating Revenue")
        ebitda = _latest(stmts.get("income_statement"), "EBITDA") or _latest(stmts.get("income_statement"), "Normalized EBITDA")
        cfo = _latest(stmts.get("cash_flow"), "Operating Cash Flow")
        capex = _latest(stmts.get("cash_flow"), "Capital Expenditure")
        dividends = _latest(stmts.get("cash_flow"), "Cash Dividends Paid")
        cash = _latest(stmts.get("balance_sheet"), "Cash Cash Equivalents And Short Term Investments") or _latest(stmts.get("balance_sheet"), "Cash And Cash Equivalents")
        minority = _latest(stmts.get("balance_sheet"), "Minority Interest") or 0.0
        if price:
            mcap = price * shares
            out["market_cap"] = round(mcap, 0)
            if revenue and revenue > 0:
                out["price_to_sales"] = round(mcap / revenue, 2)
                out["revenue"] = revenue
            if ebitda is not None:
                out["ebitda"] = ebitda
            if debt is not None:
                ev = mcap + debt - (cash or 0.0) + minority
                out["enterprise_value"] = round(ev, 0)
                if ebitda and ebitda > 0:
                    out["enterprise_to_ebitda"] = round(ev / ebitda, 2)
                if revenue and revenue > 0:
                    out["enterprise_to_revenue"] = round(ev / revenue, 2)
            if cfo is not None:
                out["operating_cashflow"] = cfo
                if capex is not None:
                    out["free_cashflow"] = cfo + capex   # capex is reported negative
            if dividends is not None and mcap > 0:
                out["dividend_yield"] = round(abs(dividends) / mcap * 100, 2)   # percent, as Yahoo reports it
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
