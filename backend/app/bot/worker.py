"""Telegram bot worker: polling entry point + weekly digest cron job.

Run with: python -m app.bot.worker
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from telegram import Update
from telegram.ext import Application, ContextTypes
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.handlers import build_application
from app.bot.notifier import send_weekly_digest
from app.db.base import get_session_factory
from app.models import ChildAccount, User
from app.services.analytics_service import _compute_psi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLLING_RESTART_DELAY_SECONDS = 5.0


async def weekly_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Monday 09:00 UTC: per-parent digest with children readiness stats."""
    try:
        async with get_session_factory()() as db:
            parents = (
                await db.scalars(select(User).where(User.role == "PARENT"))
            ).all()
            for parent in parents:
                children = (
                    await db.scalars(
                        select(ChildAccount)
                        .options(selectinload(ChildAccount.user))
                        .where(ChildAccount.parent_id == parent.id)
                    )
                ).all()
                if not children:
                    continue
                stats: list[dict] = []
                for child in children:
                    psi, _t_speed, theta = _compute_psi(child)
                    stats.append(
                        {
                            "full_name": child.user.full_name if child.user else "",
                            "psi": psi,
                            "theta": theta,
                            "streak_days": child.streak_days,
                        }
                    )
                await send_weekly_digest(parent, stats)
        logger.info("weekly digest job finished")
    except Exception as exc:  # noqa: BLE001 - a failed job must never kill the bot
        logger.exception("weekly digest job failed: %s", exc)


def run_polling_forever(application: Application) -> None:
    """Resilient polling loop: restart polling on any unexpected failure.

    Application.run_polling() manages its own event loop via asyncio.run(),
    so this must stay a plain sync function — never await it.
    """
    while True:
        try:
            application.run_polling(
                allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY],
                drop_pending_updates=True,
            )
            logger.warning("polling stopped cleanly; restarting…")
        except Exception as exc:  # noqa: BLE001 - keep the bot alive at all costs
            logger.exception("polling crashed (%s); restarting in %.0fs…",
                             exc, POLLING_RESTART_DELAY_SECONDS)
        time.sleep(POLLING_RESTART_DELAY_SECONDS)


def main() -> None:
    application = build_application()
    application.job_queue.run_daily(
        weekly_digest_job, time=dt.time(hour=9, minute=0, tzinfo=dt.timezone.utc), days=(0,)
    )
    logger.info("starting Danyshpan bot polling…")
    run_polling_forever(application)


if __name__ == "__main__":
    main()
