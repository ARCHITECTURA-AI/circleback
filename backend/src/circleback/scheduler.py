"""Optional periodic scheduler for digest generation.

Uses APScheduler to run digest compilation on a configurable cron schedule.
Disabled by default — enable via ENABLE_DIGEST_SCHEDULER=true in env.

Design decisions:
- Off by default so tests and dev don't spawn background threads
- Uses AsyncIOScheduler to share the FastAPI event loop
- Each active user gets a separate digest run
- Failures are logged but never crash the scheduler
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def _run_digest_for_all_users() -> None:
    """Run digest generation for every active user."""
    from sqlalchemy import select

    from circleback.db import async_session_factory
    from circleback.db.models import User
    from circleback.pipeline.digest import generate_digest

    async with async_session_factory() as db:
        try:
            result = await db.execute(select(User))
            users = result.scalars().all()

            for user in users:
                try:
                    digest = await generate_digest(db, user_id=user.id)
                    total = len(digest.get("made_by_user", [])) + len(digest.get("owed_to_user", []))
                    logger.info(
                        "Digest generated for user %s (%s): %d active commitments",
                        user.id, user.email, total,
                    )
                except Exception:
                    logger.exception("Failed to generate digest for user %s", user.id)

            await db.commit()
        except Exception:
            logger.exception("Scheduled digest run failed")
            await db.rollback()


def start_scheduler() -> None:
    """Start the APScheduler digest cron job.

    Call this during application startup (inside lifespan).
    Requires the `apscheduler` package.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
        from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "apscheduler is not installed — digest scheduler disabled. "
            "Install with: pip install apscheduler"
        )
        return

    from circleback.config import get_settings
    settings = get_settings()

    if not settings.enable_digest_scheduler:
        logger.info("Digest scheduler is disabled (ENABLE_DIGEST_SCHEDULER=false)")
        return

    trigger = CronTrigger.from_crontab(settings.digest_schedule_cron)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_digest_for_all_users,
        trigger=trigger,
        id="digest_cron",
        name="Periodic digest generation",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Digest scheduler started with cron: %s",
        settings.digest_schedule_cron,
    )
