from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, Index
from datetime import datetime
from app.db.session import Base

class StockMaster(Base):
    __tablename__ = "stock_master"

    symbol = Column(String(30), primary_key=True, index=True) # e.g. RELIANCE.NS
    name = Column(String(200), nullable=False, index=True)
    clean_symbol = Column(String(20), index=True) # e.g. RELIANCE
    isin = Column(String(20), nullable=True)
    sector = Column(String(100), index=True, default="Diversified")
    industry = Column(String(100), nullable=True)
    market_cap_category = Column(String(20), default="Large Cap") # Large Cap, Mid Cap, Small Cap
    is_nifty50 = Column(Boolean, default=False)
    is_nifty500 = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class PriceCache(Base):
    __tablename__ = "price_cache"

    symbol = Column(String(30), primary_key=True, index=True)
    current_price = Column(Float, nullable=True)
    prev_close = Column(Float, nullable=True)
    change_1d = Column(Float, nullable=True)
    change_1d_pct = Column(Float, nullable=True)
    change_1w_pct = Column(Float, nullable=True)
    change_1m_pct = Column(Float, nullable=True)
    change_1y_pct = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True) # In INR
    high_52w = Column(Float, nullable=True)
    low_52w = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    avg_volume_20d = Column(Float, nullable=True)
    sparkline_data = Column(Text, nullable=True) # JSON list of prices
    last_updated = Column(DateTime, default=datetime.utcnow)

class MacroCache(Base):
    __tablename__ = "macro_cache"

    indicator_key = Column(String(50), primary_key=True) # e.g. nifty50, rbi_repo_rate
    name = Column(String(100), nullable=False)
    category = Column(String(50), default="Market") # Market, Monetary, Economy, Flows
    value = Column(Float, nullable=False)
    unit = Column(String(30), default="")
    change_1d = Column(Float, default=0.0)
    change_1w = Column(Float, default=0.0)
    change_1m = Column(Float, default=0.0)
    change_1y = Column(Float, default=0.0)
    sparkline_json = Column(Text, nullable=True)
    source = Column(String(100), default="Yahoo Finance")
    last_updated = Column(DateTime, default=datetime.utcnow)

class CorporateActionModel(Base):
    __tablename__ = "corporate_actions"

    id = Column(String(60), primary_key=True)
    symbol = Column(String(30), index=True)
    company_name = Column(String(200))
    action_type = Column(String(50), index=True) # Dividend, Split, Bonus, Buyback, Earnings, Board Meeting
    details = Column(Text)
    ex_date = Column(String(20), nullable=True)
    record_date = Column(String(20), nullable=True)
    signal = Column(String(20), default="Neutral") # Positive, Neutral, Negative
    signal_reason = Column(Text, nullable=True)
    market_cap_category = Column(String(20), default="Large Cap")
    sector = Column(String(100), nullable=True)
    source = Column(String(100), default="NSE")
    last_updated = Column(DateTime, default=datetime.utcnow)

class DailyPickModel(Base):
    """One row per IST trading date holding the two-pick research shortlist as JSON."""
    __tablename__ = "daily_picks"

    date_key = Column(String(10), primary_key=True)  # YYYY-MM-DD (IST)
    generated_at = Column(DateTime, default=datetime.utcnow)
    eligible_count = Column(Integer, default=0)
    payload = Column(Text, nullable=False)
