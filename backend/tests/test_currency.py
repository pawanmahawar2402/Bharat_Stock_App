"""Statements reported in USD must be converted before they meet an INR share price."""
from app.services import data_fetcher as df_mod


def test_usd_amounts_convert_to_inr_and_ev_ebitda_is_consistent(monkeypatch):
    monkeypatch.setattr(df_mod, "get_fx_rate", lambda pair: 90.0 if pair == "USDINR=X" else None)
    info = {"financialCurrency": "USD", "currency": "INR", "ebitda": 5.0e9,
            "enterpriseValue": 4.5e12, "enterpriseToEbitda": 900.0}
    assert df_mod._info_amount(info, "ebitda") == 5.0e9 * 90.0
    # Yahoo's own ratio mixes currencies (900x); the recomputed one must be EV / converted EBITDA
    assert round(df_mod._ev_to_ebitda(info), 2) == round(4.5e12 / (5.0e9 * 90.0), 2)


def test_same_currency_is_untouched(monkeypatch):
    monkeypatch.setattr(df_mod, "get_fx_rate", lambda pair: 1 / 0)  # must not be called
    info = {"financialCurrency": "INR", "currency": "INR", "ebitda": 1.0e11}
    assert df_mod._info_amount(info, "ebitda") == 1.0e11


def test_missing_fx_rate_yields_no_value_not_a_wrong_one(monkeypatch):
    monkeypatch.setattr(df_mod, "get_fx_rate", lambda pair: None)
    info = {"financialCurrency": "USD", "currency": "INR", "ebitda": 5.0e9}
    assert df_mod._info_amount(info, "ebitda") == "N/A"
