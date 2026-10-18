
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.data_access.database import SessionLocal
from app.modules.notification.services.upcoming_match_reminder_service import (
    generate_upcoming_match_reminders,
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def run_upcoming_match_reminders() -> None:
    """Run the reminder service using a dedicated database session."""
    db = SessionLocal()

    try:
        created_count = generate_upcoming_match_reminders(
            db,
            reminder_minutes=settings.MATCH_REMINDER_MINUTES,
        )

        if created_count:
            logger.info(
                "Created %s upcoming match reminder(s)",
                created_count,
            )

    except Exception:
        logger.exception("Failed to generate upcoming match reminders")

    finally:
        db.close()


def start_reminder_scheduler() -> None:
    """Start the periodic reminder job if it is not already running."""
    if scheduler.running:
        return

    scheduler.add_job(
        run_upcoming_match_reminders,
        trigger="interval",
        minutes=1,
        id="upcoming_match_reminders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info("Upcoming match reminder scheduler started")


def stop_reminder_scheduler() -> None:
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Upcoming match reminder scheduler stopped")
