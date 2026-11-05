import csv
import os
from pathlib import Path
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.db.models import StockMaster
from app.db.session import SessionLocal

NIFTY50_SYMBOLS = {
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "ADANIENT.NS", "SUNPHARMA.NS", "MARUTI.NS", "TATAMOTORS.NS",
    "BAJFINANCE.NS", "HINDUNILVR.NS", "M&M.NS", "WIPRO.NS", "NTPC.NS",
    "HCLTECH.NS", "POWERGRID.NS", "ASIANPAINT.NS", "TITAN.NS", "BAJAJFINSV.NS",
    "ULTRACEMCO.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "GRASIM.NS", "HINDALCO.NS",
    "BAJAJ-AUTO.NS", "NESTLEIND.NS", "TECHM.NS", "COALINDIA.NS", "ADANIPORTS.NS",
    "BRITANNIA.NS", "EICHERMOT.NS", "DRREDDY.NS", "CIPLA.NS", "ZOMATO.NS",
    "BPCL.NS", "ONGC.NS", "HEROMOTOCO.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "SHRIRAMFIN.NS", "TRENT.NS", "BEL.NS", "HAL.NS", "SBILIFE.NS"
}

def seed_stock_master(db: Session) -> int:
    """
    Populates StockMaster table from data/nifty500.csv and curated list.
    """
    count = db.query(StockMaster).count()
    if count > 400:
        return count

    csv_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "nifty500.csv"
    if not csv_path.exists():
        csv_path = Path("data/nifty500.csv")

    stocks_to_add = []
    seen = set()

    if csv_path.exists():
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_sym = row.get("Symbol", "").strip()
                name = row.get("Company Name", "").strip()
                industry = row.get("Industry", "").strip()
                isin = row.get("ISIN Code", "").strip()

                if not raw_sym or not name:
                    continue

                full_sym = f"{raw_sym}.NS"
                if full_sym in seen:
                    continue
                seen.add(full_sym)

                is_nifty50 = full_sym in NIFTY50_SYMBOLS
                category = "Large Cap" if is_nifty50 or len(seen) <= 100 else ("Mid Cap" if len(seen) <= 250 else "Small Cap")

                stock = StockMaster(
                    symbol=full_sym,
                    name=name,
                    clean_symbol=raw_sym,
                    isin=isin,
                    sector=industry or "Diversified",
                    industry=industry,
                    market_cap_category=category,
                    is_nifty50=is_nifty50,
                    is_nifty500=True,
                    is_active=True
                )
                stocks_to_add.append(stock)

    # Add any missing popular tickers (e.g. Jio Financial, Suzlon, IREDA, RVNL)
    extra_stocks = [
        ("JIOFIN.NS", "Jio Financial Services Ltd.", "JIOFIN", "Financial Services", "Large Cap"),
        ("SUZLON.NS", "Suzlon Energy Ltd.", "SUZLON", "Energy / Capital Goods", "Mid Cap"),
        ("IREDA.NS", "Indian Renewable Energy Development Agency", "IREDA", "Financial Services", "Mid Cap"),
        ("RVNL.NS", "Rail Vikas Nigam Ltd.", "RVNL", "Infrastructure", "Mid Cap"),
        ("IRFC.NS", "Indian Railway Finance Corporation", "IRFC", "Financial Services", "Large Cap"),
        ("MAHABANK.NS", "Bank of Maharashtra", "MAHABANK", "Banking", "Small Cap"),
        ("KALYANKJIL.NS", "Kalyan Jewellers India Ltd.", "KALYANKJIL", "Consumer Goods", "Mid Cap"),
        ("YESBANK.NS", "Yes Bank Ltd.", "YESBANK", "Banking", "Mid Cap"),
        ("IDEA.NS", "Vodafone Idea Ltd.", "IDEA", "Telecommunications", "Mid Cap"),
        ("HUDCO.NS", "Housing & Urban Development Corp Ltd.", "HUDCO", "Financial Services", "Mid Cap")
    ]

    for sym, name, clean, sector, cat in extra_stocks:
        if sym not in seen:
            seen.add(sym)
            stocks_to_add.append(StockMaster(
                symbol=sym,
                name=name,
                clean_symbol=clean,
                isin="",
                sector=sector,
                industry=sector,
                market_cap_category=cat,
                is_nifty50=sym in NIFTY50_SYMBOLS,
                is_nifty500=True,
                is_active=True
            ))

    if stocks_to_add:
        db.bulk_save_objects(stocks_to_add)
        db.commit()

    return db.query(StockMaster).count()

def search_stocks(query: str, db: Session, limit: int = 15) -> List[Dict]:
    """
    Searches stocks by company name or ticker.
    """
    if not query:
        # Default top Nifty 50
        stocks = db.query(StockMaster).filter(StockMaster.is_nifty50 == True).limit(limit).all()
    else:
        q = query.strip().upper()
        # Exact clean symbol match first, then partial match
        stocks = db.query(StockMaster).filter(
            (StockMaster.clean_symbol.ilike(f"{q}%")) |
            (StockMaster.name.ilike(f"%{query}%")) |
            (StockMaster.symbol.ilike(f"{q}%"))
        ).limit(limit).all()

    return [
        {
            "symbol": s.symbol,
            "name": s.name,
            "clean_symbol": s.clean_symbol,
            "sector": s.sector,
            "category": s.market_cap_category,
            "is_nifty50": s.is_nifty50
        }
        for s in stocks
    ]

def get_stock_by_symbol(symbol: str, db: Session) -> Optional[StockMaster]:
    sym = symbol.strip().upper()
    if not sym.endswith(".NS") and not sym.endswith(".BO") and not sym.startswith("^"):
        sym = f"{sym}.NS"
    return db.query(StockMaster).filter(StockMaster.symbol == sym).first()
