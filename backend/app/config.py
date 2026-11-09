import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "BharatStock Analyzer"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/bharatstock.db"
    
    # LLM Settings (Optional narrative generation)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    ENABLE_LLM_NARRATIVE: bool = True
    
    # Caching TTL in seconds
    CACHE_TTL_PRICES: int = 300       # 5 minutes
    CACHE_TTL_MACRO: int = 3600       # 1 hour
    CACHE_TTL_FINANCIALS: int = 86400 # 24 hours
    
    # Market-data sources, in priority order (see app/sources/registry.py)
    DATA_SOURCES: str = "yahoo,stock_list,statement_derived"

    # Daily Two Picks engine
    DAILY_UNIVERSE_SIZE: int = 120    # Nifty 500 names screened per run
    DAILY_PICKS_HOUR_IST: int = 16    # run after market close (15:30 IST)
    DAILY_PICKS_MINUTE_IST: int = 30

    # Risk-free rate for India DCF & Graham (India 10Y G-Sec benchmark default)
    INDIA_10Y_GSEC_DEFAULT: float = 6.80
    EQUITY_RISK_PREMIUM_DEFAULT: float = 6.50
    
    class Config:
        env_file = os.path.join(BASE_DIR.parent, ".env")
        extra = "ignore"

settings = Settings()
