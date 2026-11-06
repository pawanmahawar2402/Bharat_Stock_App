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


def test_infers_usd_for_infosys_like_figures(monkeypatch):
    # Infosys: revenue 2.0158e10 (USD), 4.05e9 shares, price Rs 1169, USD/INR 94.5
    res = df_mod._infer_factor(2.0158e10, 4.05e9, 1169.0, 94.5)
    assert res == ("USD", 94.5)


def test_infers_inr_for_tcs_like_figures():
    # TCS: revenue 2.67e12 (INR), 3.62e9 shares, price Rs 2500
    res = df_mod._infer_factor(2.67e12, 3.62e9, 2500.0, 94.5)
    assert res == ("INR", 1.0)


def test_ambiguous_or_missing_inputs_return_none():
    assert df_mod._infer_factor(None, 1e9, 100.0, 94.5) is None
    assert df_mod._infer_factor(1e10, 1e9, 100.0, None) is None
