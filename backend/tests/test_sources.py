"""Source registry merge rules, tested offline with fake sources."""
import pandas as pd
from app.sources.base import DataSource
from app.sources.registry import SourceRegistry
from app.sources.statement_source import StatementDerivedSource


class Primary(DataSource):
    name = "primary"
    capabilities = frozenset({"fundamentals", "history", "statements"})

    def fetch_fundamentals(self, symbol, context):
        return {"current_price": 100.0, "trailing_pe": "N/A", "sector": "Technology", "shares_outstanding": 1e7}

    def fetch_history(self, symbol, period="1y", interval="1d"):
        return pd.DataFrame({"Close": [1.0]})

    def fetch_statements(self, symbol):
        return {"income_statement": {"2025-03-31": {"Net Income Common Stockholders": 5e8}},
                "balance_sheet": {"2025-03-31": {"Stockholders Equity": 2e9, "Total Debt": 4e8}},
                "cash_flow": {}}


class Broken(DataSource):
    name = "broken"
    capabilities = frozenset({"fundamentals", "history"})

    def fetch_fundamentals(self, symbol, context):
        raise RuntimeError("network down")

    def fetch_history(self, symbol, period="1y", interval="1d"):
        raise RuntimeError("network down")


def test_first_source_wins_and_gaps_are_filled_with_provenance():
    reg = SourceRegistry([Primary(), StatementDerivedSource()])
    f = reg.fundamentals("X.NS")
    assert f["current_price"] == 100.0
    assert f["field_sources"]["current_price"] == "primary"
    # trailing_pe was N/A from primary, so the statement-derived source fills it: 100 / (5e8/1e7) = 2
    assert f["trailing_pe"] == 2.0
    assert f["field_sources"]["trailing_pe"] == "statement_derived"
    # price_to_book = 100 / (2e9/1e7) = 0.5
    assert f["price_to_book"] == 0.5
    assert f["debt_to_equity"] == 20.0
    assert "_statements" not in f
    assert f["sources_used"] == ["primary", "statement_derived"]


def test_a_failing_source_does_not_break_the_chain():
    reg = SourceRegistry([Broken(), Primary()])
    f = reg.fundamentals("X.NS")
    assert f["current_price"] == 100.0
    assert f["sources_used"] == ["primary"]
    df = reg.history("X.NS")
    assert not df.empty


def test_history_falls_through_to_next_source():
    reg = SourceRegistry([Broken(), Primary()])
    assert len(reg.history("X.NS")) == 1


def test_statement_source_never_overrides_existing_values():
    reg = SourceRegistry([Primary(), StatementDerivedSource()])
    f = reg.fundamentals("X.NS")
    assert f["sector"] == "Technology"
    assert f["field_sources"].get("sector") == "primary"
