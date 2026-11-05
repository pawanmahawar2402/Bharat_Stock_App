import json
import math
import logging
import requests
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import numpy as np
import yfinance as yf
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import PriceCache

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com/",
    "Connection": "keep-alive"
}

def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

_FX_CACHE: Dict[str, Any] = {}


def get_fx_rate(pair: str) -> Optional[float]:
    """Latest rate for a Yahoo FX pair such as 'USDINR=X' (1 unit of the first currency in the second). Cached 1 hour."""
    cached = _FX_CACHE.get(pair)
    if cached and (datetime.utcnow() - cached[1]).total_seconds() < 3600:
        return cached[0]
    try:
        hist = yf.Ticker(pair).history(period="5d", interval="1d", auto_adjust=False)
        rate = float(hist["Close"].dropna().iloc[-1]) if not hist.empty else None
    except Exception as e:
        logger.warning(f"FX rate {pair} unavailable: {e}")
        rate = None
    if rate:
        _FX_CACHE[pair] = (rate, datetime.utcnow())
    return rate


# Statement line items that are NOT currency amounts and must not be converted
_NON_CURRENCY_MARKERS = ("shares", "number", "rate", "ratio", "percent")


def _info_fx(info: Dict[str, Any]) -> float:
    """Factor converting Yahoo's currency-amount fields to the quote currency (1.0 when they already match)."""
    fin_ccy = info.get("financialCurrency")
    quote_ccy = info.get("currency") or "INR"
    if not fin_ccy or fin_ccy == quote_ccy:
        return 1.0
    return get_fx_rate(f"{fin_ccy}{quote_ccy}=X") or float("nan")


def _info_amount(info: Dict[str, Any], key: str):
    v = info.get(key)
    if not isinstance(v, (int, float)):
        return "N/A"
    fx = _info_fx(info)
    return float(v) * fx if not math.isnan(fx) else "N/A"


def _ev_to_ebitda(info: Dict[str, Any]):
    """EV / EBITDA with both sides in the quote currency. Yahoo's own ratio can mix currencies."""
    ev = info.get("enterpriseValue")
    ebitda = _info_amount(info, "ebitda")
    if isinstance(ev, (int, float)) and isinstance(ebitda, (int, float)) and ebitda > 0:
        return round(float(ev) / ebitda, 3)
    return info.get("enterpriseToEbitda", "N/A")


class DataFetcher:
    """
    Resilient data fetcher for Indian equities and macro benchmarks with multi-tier fallbacks.
    """

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        s = symbol.strip().upper()
        if s.startswith("^") or "=" in s or "-" in s or s.endswith(".NYB"):
            return s  # index, FX/commodity futures, or global ticker (e.g. DX-Y.NYB)
        if not s.endswith(".NS") and not s.endswith(".BO"):
            return f"{s}.NS"
        return s

    @staticmethod
    def yahoo_symbol_search(query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Searches Yahoo Finance for listed equities and ETFs by name or ticker.
        Returns Yahoo symbols (e.g. NEOGEN.NS, NEOG) that the rest of the app can analyse directly.
        """
        url = ("https://query1.finance.yahoo.com/v1/finance/search?"
               + urllib.parse.urlencode({"q": query, "quotesCount": limit, "newsCount": 0}))
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            logger.warning(f"Yahoo symbol search failed for '{query}': {e}")
            return []
        out = []
        for q in data.get("quotes", []):
            if q.get("quoteType") not in ("EQUITY", "ETF") or not q.get("symbol"):
                continue
            name = q.get("longname") or q.get("shortname") or q["symbol"]
            out.append({
                "symbol": q["symbol"],
                "name": name,
                "clean_symbol": q["symbol"].split(".")[0],
                "sector": q.get("sectorDisp") or q.get("sector") or "Diversified",
                "category": "Listed (Yahoo Finance)",
                "is_nifty50": False,
                "exchange": q.get("exchDisp") or q.get("exchange"),
            })
        return out

    @staticmethod
    def fetch_history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """
        Fetches historical OHLCV data and returns clean pandas DataFrame with DatetimeIndex.
        """
        sym = DataFetcher.normalize_symbol(symbol)
        try:
            ticker = yf.Ticker(sym, session=get_session())
            df = ticker.history(period=period, interval=interval, auto_adjust=False)

            if df is None or df.empty:
                # Fallback to direct yfinance download
                df = yf.download(sym, period=period, interval=interval, progress=False)

            if df is None or df.empty:
                # Fallback to .BO if .NS failed
                if sym.endswith(".NS"):
                    alt_sym = sym.replace(".NS", ".BO")
                    df = yf.download(alt_sym, period=period, interval=interval, progress=False)

            if df is None or df.empty:
                logger.warning(f"No OHLCV history fetched for {symbol}")
                return pd.DataFrame()

            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            # Standardize column names
            col_map = {c: c.capitalize() for c in df.columns}
            df = df.rename(columns=col_map)

            req_cols = ["Open", "High", "Low", "Close", "Volume"]
            avail_cols = [c for c in req_cols if c in df.columns]
            if len(avail_cols) < 4:
                return pd.DataFrame()

            df = df[avail_cols].copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            df = df[~df.index.duplicated(keep="last")]
            df = df.dropna(subset=["Open", "High", "Low", "Close"])

            for col in avail_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            return df.dropna()
        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {e}")
            return pd.DataFrame()

    @staticmethod
    def fetch_quote_and_fundamentals(symbol: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Multi-tier fundamental extraction:
        Tier 1: yf.Ticker fast_info + info
        Tier 2: Direct Yahoo Finance quoteSummary REST API
        Tier 3: Mathematical derivation (PE = Price/EPS, MarketCap = Shares * Price)
        """
        sym = DataFetcher.normalize_symbol(symbol)

        # Check Cache in DB
        # NOTE: the cache stores price fields only. Serving it here dropped sector, industry, beta,
        # EBITDA and share count, which corrupted valuations, so the full fetch is always used.
        if db and False:
            cached = db.query(PriceCache).filter(PriceCache.symbol == sym).first()
            if cached and cached.last_updated and (datetime.utcnow() - cached.last_updated).total_seconds() < settings.CACHE_TTL_PRICES:
                try:
                    sparkline = json.loads(cached.sparkline_data) if cached.sparkline_data else []
                except:
                    sparkline = []
                # If we have valid price and market cap cached, return
                if cached.current_price and cached.current_price > 0:
                    return {
                        "symbol": sym,
                        "current_price": cached.current_price,
                        "prev_close": cached.prev_close,
                        "change_1d": cached.change_1d,
                        "change_1d_pct": cached.change_1d_pct,
                        "change_1w_pct": cached.change_1w_pct,
                        "change_1m_pct": cached.change_1m_pct,
                        "change_1y_pct": cached.change_1y_pct,
                        "market_cap": cached.market_cap,
                        "high_52w": cached.high_52w,
                        "low_52w": cached.low_52w,
                        "volume": cached.volume,
                        "avg_volume_20d": cached.avg_volume_20d,
                        "sparkline": sparkline,
                        "is_cached": True
                    }

        session = get_session()
        ticker = yf.Ticker(sym, session=session)
        
        info = {}
        fast_info = {}
        
        try:
            fast_info = getattr(ticker, "fast_info", {}) or {}
        except Exception:
            fast_info = {}

        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        # Direct REST quoteSummary fallback if info is sparse
        if not info or len(info) < 5:
            try:
                url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules=financialData,defaultKeyStatistics,summaryDetail,price"
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode())
                    result = data.get("quoteSummary", {}).get("result", [{}])[0]
                    fin = result.get("financialData", {})
                    stats = result.get("defaultKeyStatistics", {})
                    sum_det = result.get("summaryDetail", {})
                    price_sec = result.get("price", {})
                    
                    def unwrap(d, k):
                        val = d.get(k, {})
                        return val.get("raw") if isinstance(val, dict) else val

                    info = {
                        "currentPrice": unwrap(fin, "currentPrice") or unwrap(price_sec, "regularMarketPrice"),
                        "regularMarketPreviousClose": unwrap(sum_det, "previousClose") or unwrap(price_sec, "regularMarketPreviousClose"),
                        "marketCap": unwrap(sum_det, "marketCap") or unwrap(price_sec, "marketCap"),
                        "trailingPE": unwrap(sum_det, "trailingPE"),
                        "forwardPE": unwrap(sum_det, "forwardPE"),
                        "pegRatio": unwrap(stats, "pegRatio"),
                        "priceToBook": unwrap(stats, "priceToBook") or unwrap(sum_det, "priceToBook"),
                        "enterpriseValue": unwrap(stats, "enterpriseValue"),
                        "enterpriseToEbitda": unwrap(stats, "enterpriseToEbitda"),
                        "enterpriseToRevenue": unwrap(stats, "enterpriseToRevenue"),
                        "ebitda": unwrap(fin, "ebitda"),
                        "freeCashflow": unwrap(fin, "freeCashflow"),
                        "operatingCashflow": unwrap(fin, "operatingCashflow"),
                        "returnOnEquity": unwrap(fin, "returnOnEquity"),
                        "returnOnAssets": unwrap(fin, "returnOnAssets"),
                        "debtToEquity": unwrap(fin, "debtToEquity"),
                        "dividendYield": unwrap(sum_det, "dividendYield"),
                        "beta": unwrap(stats, "beta"),
                        "trailingEps": unwrap(stats, "trailingEps"),
                        "forwardEps": unwrap(stats, "forwardEps"),
                        "bookValue": unwrap(stats, "bookValue"),
                        "fiftyTwoWeekHigh": unwrap(sum_det, "fiftyTwoWeekHigh"),
                        "fiftyTwoWeekLow": unwrap(sum_det, "fiftyTwoWeekLow"),
                        "currency": price_sec.get("currency", "INR")
                    }
            except Exception as e:
                logger.debug(f"Direct REST quoteSummary fallback failed for {sym}: {e}")

        # Price Resolution
        current_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice") or
            getattr(fast_info, "last_price", None) or
            getattr(fast_info, "regular_market_price", None) or
            0.0
        )
        prev_close = (
            info.get("regularMarketPreviousClose") or
            info.get("previousClose") or
            getattr(fast_info, "previous_close", None) or
            current_price
        )

        # 52-Week High & Low
        high_52w = info.get("fiftyTwoWeekHigh") or getattr(fast_info, "year_high", None) or current_price * 1.15
        low_52w = info.get("fiftyTwoWeekLow") or getattr(fast_info, "year_low", None) or current_price * 0.85
        market_cap = info.get("marketCap") or getattr(fast_info, "market_cap", None) or 0.0

        # Shares outstanding
        shares = info.get("sharesOutstanding") or getattr(fast_info, "shares", None) or 0.0
        if market_cap == 0 and shares > 0 and current_price > 0:
            market_cap = shares * current_price

        # Fetch recent 1M history for sparklines & accurate percentage changes
        hist_df = DataFetcher.fetch_history(sym, period="1y", interval="1d")
        sparkline = []
        change_1w_pct = 0.0
        change_1m_pct = 0.0
        change_1y_pct = 0.0
        avg_volume_20d = float(info.get("averageVolume") or 0.0)
        volume = float(info.get("volume") or getattr(fast_info, "last_volume", 0.0) or 0.0)

        if not hist_df.empty:
            closes = hist_df["Close"].dropna()
            if len(closes) > 0:
                if current_price == 0.0:
                    current_price = float(closes.iloc[-1])
                if len(closes) >= 2 and prev_close == 0.0:
                    prev_close = float(closes.iloc[-2])

                # Sparkline (last 30 closes)
                sparkline = [round(float(p), 2) for p in closes.tail(30).tolist()]
                
                # Returns
                if len(closes) >= 5:
                    change_1w_pct = round(((current_price - float(closes.iloc[-5])) / float(closes.iloc[-5])) * 100, 2)
                if len(closes) >= 21:
                    change_1m_pct = round(((current_price - float(closes.iloc[-21])) / float(closes.iloc[-21])) * 100, 2)
                if len(closes) >= 200:
                    change_1y_pct = round(((current_price - float(closes.iloc[-200])) / float(closes.iloc[-200])) * 100, 2)

                # Volumes
                if "Volume" in hist_df.columns:
                    vols = hist_df["Volume"].dropna()
                    if len(vols) >= 20:
                        avg_volume_20d = float(vols.tail(20).mean())
                    if len(vols) > 0 and volume == 0.0:
                        volume = float(vols.iloc[-1])

        change_1d = current_price - prev_close if prev_close else 0.0
        change_1d_pct = round((change_1d / prev_close) * 100, 2) if prev_close else 0.0

        # Mathematical Derivations for Fundamental Metrics
        trailing_eps = info.get("trailingEps")
        forward_eps = info.get("forwardEps")
        book_value = info.get("bookValue")
        
        trailing_pe = info.get("trailingPE")
        if (trailing_pe is None or trailing_pe == "N/A") and trailing_eps and trailing_eps > 0 and current_price > 0:
            trailing_pe = round(current_price / trailing_eps, 2)

        forward_pe = info.get("forwardPE")
        if (forward_pe is None or forward_pe == "N/A") and forward_eps and forward_eps > 0 and current_price > 0:
            forward_pe = round(current_price / forward_eps, 2)

        price_to_book = info.get("priceToBook")
        if (price_to_book is None or price_to_book == "N/A") and book_value and book_value > 0 and current_price > 0:
            price_to_book = round(current_price / book_value, 2)

        result_dict = {
            "symbol": sym,
            "company_name": info.get("longName") or info.get("shortName") or sym,
            "sector": info.get("sector", "Diversified"),
            "industry": info.get("industry", "Diversified"),
            "current_price": round(float(current_price), 2),
            "prev_close": round(float(prev_close), 2),
            "change_1d": round(float(change_1d), 2),
            "change_1d_pct": change_1d_pct,
            "change_1w_pct": change_1w_pct,
            "change_1m_pct": change_1m_pct,
            "change_1y_pct": change_1y_pct,
            "market_cap": float(market_cap),
            "shares_outstanding": float(shares) if shares else None,
            "high_52w": round(float(high_52w), 2),
            "low_52w": round(float(low_52w), 2),
            "volume": volume,
            "avg_volume_20d": avg_volume_20d,
            "sparkline": sparkline,
            # Ratios
            "trailing_pe": trailing_pe if trailing_pe is not None else "N/A",
            "forward_pe": forward_pe if forward_pe is not None else "N/A",
            "peg_ratio": info.get("pegRatio", "N/A"),
            "price_to_book": price_to_book if price_to_book is not None else "N/A",
            "price_to_sales": info.get("priceToSalesTrailing12Months", "N/A"),
            "enterprise_value": info.get("enterpriseValue", "N/A"),
            "enterprise_to_ebitda": _ev_to_ebitda(info),
            "enterprise_to_revenue": info.get("enterpriseToRevenue", "N/A"),
            "ebitda": _info_amount(info, "ebitda"),
            "free_cashflow": _info_amount(info, "freeCashflow"),
            "operating_cashflow": _info_amount(info, "operatingCashflow"),
            "return_on_equity": info.get("returnOnEquity", "N/A"),
            "return_on_assets": info.get("returnOnAssets", "N/A"),
            "debt_to_equity": info.get("debtToEquity", "N/A"),
            "dividend_yield": info.get("dividendYield", "N/A"),
            "beta": info.get("beta", "N/A"),
            "eps_trailing": trailing_eps if trailing_eps is not None else "N/A",
            "eps_forward": forward_eps if forward_eps is not None else "N/A",
            "book_value": book_value if book_value is not None else "N/A",
            "currency": info.get("currency", "INR"),
            "last_updated": datetime.utcnow().isoformat()
        }

        # Update DB Cache
        if db and current_price > 0:
            try:
                cache_obj = db.query(PriceCache).filter(PriceCache.symbol == sym).first()
                if not cache_obj:
                    cache_obj = PriceCache(symbol=sym)
                    db.add(cache_obj)
                
                cache_obj.current_price = result_dict["current_price"]
                cache_obj.prev_close = result_dict["prev_close"]
                cache_obj.change_1d = result_dict["change_1d"]
                cache_obj.change_1d_pct = result_dict["change_1d_pct"]
                cache_obj.change_1w_pct = result_dict["change_1w_pct"]
                cache_obj.change_1m_pct = result_dict["change_1m_pct"]
                cache_obj.change_1y_pct = result_dict["change_1y_pct"]
                cache_obj.market_cap = result_dict["market_cap"]
                cache_obj.high_52w = result_dict["high_52w"]
                cache_obj.low_52w = result_dict["low_52w"]
                cache_obj.volume = result_dict["volume"]
                cache_obj.avg_volume_20d = result_dict["avg_volume_20d"]
                cache_obj.sparkline_data = json.dumps(sparkline)
                cache_obj.last_updated = datetime.utcnow()
                db.commit()
            except Exception as e:
                logger.error(f"Error caching price data for {sym}: {e}")
                db.rollback()

        return result_dict

    @staticmethod
    def fetch_financial_statements(symbol: str) -> Dict[str, Any]:
        """
        Fetches Income Statement, Balance Sheet, and Cash Flow Statement (Annual & Quarterly).
        """
        sym = DataFetcher.normalize_symbol(symbol)
        ticker = yf.Ticker(sym, session=get_session())

        # Statements can be reported in a different currency from the share price (e.g. Infosys
        # reports in USD while trading in INR). Convert amounts so every figure is in the quote currency.
        fx = 1.0
        currency_meta = {"reported_currency": None, "display_currency": "INR", "fx_rate": None,
                         "converted": False}
        try:
            info = ticker.info or {}
            fin_ccy = info.get("financialCurrency")
            quote_ccy = info.get("currency") or "INR"
            currency_meta["reported_currency"] = fin_ccy or quote_ccy
            currency_meta["display_currency"] = quote_ccy
            if fin_ccy and fin_ccy != quote_ccy:
                rate = get_fx_rate(f"{fin_ccy}{quote_ccy}=X")
                if not rate:
                    logger.error(f"{sym}: statements in {fin_ccy}, no FX rate; statements withheld.")
                    return {k: {} for k in ("income_statement", "income_statement_quarterly", "balance_sheet",
                                            "balance_sheet_quarterly", "cash_flow", "cash_flow_quarterly")}
                fx = rate
                currency_meta.update({"fx_rate": round(rate, 4), "converted": True})
        except Exception as e:
            logger.warning(f"Currency check failed for {sym}: {e}")

        def clean_df(df):
            if df is None or df.empty:
                return {}
            data = {}
            # Columns are dates, index are metric names
            for col in df.columns:
                date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
                data[date_str] = {}
                for idx in df.index:
                    val = df.loc[idx, col]
                    if pd.notna(val) and isinstance(val, (int, float, np.number)):
                        name = str(idx)
                        is_amount = not any(m in name.lower() for m in _NON_CURRENCY_MARKERS)
                        data[date_str][name] = float(val) * (fx if is_amount else 1.0)
            return data

        try:
            return {
                "income_statement": clean_df(ticker.financials),
                "income_statement_quarterly": clean_df(ticker.quarterly_financials),
                "balance_sheet": clean_df(ticker.balance_sheet),
                "balance_sheet_quarterly": clean_df(ticker.quarterly_balance_sheet),
                "cash_flow": clean_df(ticker.cashflow),
                "cash_flow_quarterly": clean_df(ticker.quarterly_cashflow),
                "currency": currency_meta,
            }
        except Exception as e:
            logger.error(f"Error fetching financial statements for {symbol}: {e}")
            return {
                "income_statement": {},
                "income_statement_quarterly": {},
                "balance_sheet": {},
                "balance_sheet_quarterly": {},
                "cash_flow": {},
                "cash_flow_quarterly": {}
            }
