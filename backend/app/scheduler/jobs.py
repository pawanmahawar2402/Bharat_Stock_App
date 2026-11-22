import logging
from app.db.session import SessionLocal
from app.services.macro_service import MacroService
from app.services.daily_picks_service import DailyPicksEngine
from app.config import settings

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    HAS_APSCHEDULER = True
except ImportError:
    scheduler = None
    HAS_APSCHEDULER = False

def nightly_price_and_macro_refresh():
    """
    Nightly background job to refresh macro indicators and sector data.
    """
    logger.info("🌙 Running nightly BharatStock Analyzer data refresh job...")
    try:
        db = SessionLocal()
        # Refresh macro indicators
        MacroService.get_market_indicators()
        MacroService.get_sector_rotation_heatmap()
        db.close()
        logger.info("✅ Nightly refresh job completed successfully.")
    except Exception as e:
        logger.error(f"❌ Error during nightly refresh job: {e}")

def start_scheduler():
    if HAS_APSCHEDULER and scheduler and not scheduler.running:
        # Run every 6 hours
        scheduler.add_job(nightly_price_and_macro_refresh, "interval", hours=6, id="nightly_refresh", replace_existing=True)
        # Daily Two Picks: after market close, Mon-Fri IST
        from app.services.corporate_actions import refresh as refresh_actions
        from app.db.models import StockMaster
        def _refresh_actions():
            db = SessionLocal()
            try:
                members = [(r.symbol, r.name) for r in db.query(StockMaster).filter(StockMaster.is_nifty500 == True).all()]
            finally:
                db.close()
            refresh_actions(members)
        scheduler.add_job(_refresh_actions, "cron", hour=6, minute=0, timezone="Asia/Kolkata",
                          id="corporate_actions", replace_existing=True)
        scheduler.add_job(
            DailyPicksEngine.run_safe, "cron",
            day_of_week="mon-fri", hour=settings.DAILY_PICKS_HOUR_IST, minute=settings.DAILY_PICKS_MINUTE_IST,
            timezone="Asia/Kolkata", id="daily_two_picks", replace_existing=True,
        )
        scheduler.start()
        logger.info("⏰ APScheduler background scheduler started.")

def shutdown_scheduler():
    if HAS_APSCHEDULER and scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 APScheduler background scheduler stopped.")
