import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import init_db, SessionLocal
from app.services.stock_master import seed_stock_master
from app.scheduler.jobs import start_scheduler, shutdown_scheduler
from app.routers import macro, market_pulse, swing_scanner, stock_analysis, daily_picks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bharatstock")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting BharatStock Analyzer Backend...")
    # Initialize SQLite tables
    init_db()
    # Seed 500+ NSE stocks
    db = SessionLocal()
    count = seed_stock_master(db)
    db.close()
    logger.info(f"📊 Stock Master initialized with {count} Indian stocks.")
    # Start scheduler
    start_scheduler()
    yield
    logger.info("🛑 Shutting down BharatStock Analyzer Backend...")
    shutdown_scheduler()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Institutional-grade stock analytics platform for Indian Equities (NSE/BSE).",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(macro.router, prefix=settings.API_V1_STR)
app.include_router(market_pulse.router, prefix=settings.API_V1_STR)
app.include_router(swing_scanner.router, prefix=settings.API_V1_STR)
app.include_router(stock_analysis.router, prefix=settings.API_V1_STR)
app.include_router(daily_picks.router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "disclaimer": "For educational purposes only. Free data may be delayed. Not SEBI registered advice."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
