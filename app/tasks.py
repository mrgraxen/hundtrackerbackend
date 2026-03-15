"""Background tasks - position retention cleanup."""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Position

logger = logging.getLogger(__name__)


async def cleanup_old_positions() -> None:
    """Delete positions older than retention period. Run periodically (e.g. hourly)."""
    settings = get_settings()
    cutoff = datetime.utcnow() - timedelta(hours=settings.position_retention_hours)
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(delete(Position).where(Position.received_at < cutoff))
            deleted = result.rowcount
            await session.commit()
            if deleted:
                logger.info("Position cleanup: deleted %s old rows", deleted)
        except Exception as e:
            await session.rollback()
            logger.exception("Position cleanup failed: %s", e)


async def run_cleanup_loop() -> None:
    """Run cleanup every hour."""
    while True:
        try:
            await cleanup_old_positions()
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Cleanup loop error: %s", e)
