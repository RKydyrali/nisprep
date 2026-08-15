"""Outbound Telegram notifications: OTP, error alerts, weekly digests.

Every send is wrapped in try/except and returns bool so callers can degrade
gracefully when the bot is not configured or unavailable.
"""

from __future__ import annotations

import logging

from telegram import Bot

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_bot: Bot | None = None
_bot_initialized = False


async def _ensure_bot() -> Bot | None:
    global _bot, _bot_initialized
    if not settings.telegram_bot_token:
        return None
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    if not _bot_initialized:
        await _bot.initialize()
        _bot_initialized = True
    return _bot


def get_bot() -> Bot | None:
    """Lazily build the bot instance without initialising the HTTP client."""
    if not settings.telegram_bot_token:
        return None
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


async def send_otp(chat_id: int, otp: str, lang: str = "ru") -> bool:
    try:
        bot = await _ensure_bot()
        if bot is None:
            return False
        text = (
            f"Ваш код входа: {otp}. Введите его на сайте danyshpan.xyz."
            if lang == "ru"
            else f"Кіру кодыңыз: {otp}. Оны danyshpan.xyz сайтында енгізіңіз."
        )
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as exc:  # noqa: BLE001 - notification must never crash the app
        logger.warning("send_otp failed: %s", exc)
        return False


async def send_error_alert(child, count: int) -> bool:
    if child.telegram_chat_id is None:
        return False
    try:
        bot = await _ensure_bot()
        if bot is None:
            return False
        text = (
            "Серия ошибок: не сдавайся! 💪 Разбери 3 задачи из журнала ошибок."
            if child.language == "ru"
            else "Қателер сериясы: берілме! 💪 Қателер журналынан 3 тапсырма шығарып көр."
        )
        await bot.send_message(chat_id=child.telegram_chat_id, text=text)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("send_error_alert failed: %s", exc)
        return False


async def send_weekly_digest(parent, children_stats: list[dict]) -> bool:
    if parent.telegram_chat_id is None:
        return False
    try:
        bot = await _ensure_bot()
        if bot is None:
            return False
        lines = ["📊 Еженедельный дайджест «Данышпан»:"]
        for stat in children_stats:
            lines.append(
                f"• {stat['full_name']}: готовность ψ={stat['psi']:.2f}, "
                f"θ: мат {stat['theta']['math']:.2f}, "
                f"кол {stat['theta']['quant']:.2f}, "
                f"ест {stat['theta']['nat_sci']:.2f}, "
                f"яз {stat['theta']['lang']:.2f}, "
                f"серия {stat['streak_days']} дн."
            )
        if len(children_stats) == 1:
            s = children_stats[0]
            lines.append(
                "Рекомендация: продолжайте ежедневные спринты по 10 задач и "
                "повторяйте журнал ошибок."
                if s["psi"] < 1.0
                else "Отличный темп! Рекомендуем перейти к CAT-режиму."
            )
        await bot.send_message(chat_id=parent.telegram_chat_id, text="\n".join(lines))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("send_weekly_digest failed: %s", exc)
        return False
