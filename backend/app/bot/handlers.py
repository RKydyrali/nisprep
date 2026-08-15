"""Telegram bot handlers: /start, /verify <code>, /login, fallback.

Messages are localised via the child's stored language (ru/kk).
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.base import create_redis_client, get_session_factory
from app.models import ChildAccount
from app.services.auth_service import issue_otp

logger = logging.getLogger(__name__)
settings: Settings = get_settings()

TEXT = {
    "ru": {
        "start": (
            "Привет! Я бот платформы «Данышпан» 🇰🇿\n\n"
            "Ваш родитель создал для вас код активации.\n"
            "Отправьте: /verify <код> — чтобы привязать аккаунт ученика."
        ),
        "start_verified": (
            "Привет! Аккаунт уже привязан.\n"
            "Отправьте /login — я пришлю код для входа на сайт."
        ),
        "verify_missing": "Использование: /verify <код>. Пример: /verify Ab3dEf9K",
        "verify_ok": (
            "Аккаунт привязан! ✅\n"
            "Теперь отправьте /login, чтобы получить код входа на сайт."
        ),
        "verify_bad": "Код активации не найден или уже использован. Уточните код у родителя.",
        "login_ok": "Ваш код входа: {code}. Введите его на сайте danyshpan.xyz.",
        "login_not_verified": (
            "Аккаунт не привязан. Отправьте /verify <код> (код выдаёт родитель)."
        ),
        "fallback": "Не понял команду. Доступно: /verify <код>, /login",
    },
    "kk": {
        "start": (
            "Сәлем! Мен «Данышпан» платформасының ботымын 🇰🇿\n\n"
            "Ата-анаңыз сізге белсендіру кодын жасады.\n"
            "Оқушы аккаунтын байлау үшін: /verify <код> жіберіңіз."
        ),
        "start_verified": (
            "Сәлем! Аккаунт байланған.\n"
            "Сайтқа кіру кодын алу үшін /login жіберіңіз."
        ),
        "verify_missing": "Қолданылуы: /verify <код>. Мысалы: /verify Ab3dEf9K",
        "verify_ok": (
            "Аккаунт байланды! ✅\n"
            "Енді сайтқа кіру кодын алу үшін /login жіберіңіз."
        ),
        "verify_bad": "Белсендіру коды табылмады. Ата-анаңыздан кодын сұраңыз.",
        "login_ok": "Кіру кодыңыз: {code}. Оны danyshpan.xyz сайтында енгізіңіз.",
        "login_not_verified": (
            "Аккаунт байланбаған. /verify <код> жіберіңіз (кодты ата-ана береді)."
        ),
        "fallback": "Пәрменді түсінбедім. Қолжетімді: /verify <код>, /login",
    },
}


def _t(lang: str, key: str) -> str:
    return TEXT.get(lang, TEXT["ru"]).get(key, TEXT["ru"][key])


async def _find_child_by_chat(chat_id: int) -> ChildAccount | None:
    async with get_session_factory()() as db:
        return await db.scalar(
            select(ChildAccount).where(ChildAccount.telegram_chat_id == chat_id)
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    child = await _find_child_by_chat(chat_id)
    lang = child.language if child else "ru"
    if child is None:
        await update.effective_chat.send_message(_t(lang, "start"))
    else:
        await update.effective_chat.send_message(_t(lang, "start_verified"))


async def cmd_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.message is None:
        return
    chat_id = update.effective_chat.id
    args = update.message.text.split()
    code = args[1] if len(args) > 1 else ""
    async with get_session_factory()() as db:
        if not code:
            child = await _find_child_by_chat(chat_id)
            await update.effective_chat.send_message(
                _t(child.language if child else "ru", "verify_missing")
            )
            return
        child = await db.scalar(select(ChildAccount).where(ChildAccount.activation_code == code))
        if child is None:
            existing = await _find_child_by_chat(chat_id)
            await update.effective_chat.send_message(
                _t(existing.language if existing else "ru", "verify_bad")
            )
            return
        child.is_verified = True
        child.telegram_chat_id = chat_id
        if update.effective_user is not None and update.effective_user.username:
            child.telegram_username = update.effective_user.username
        await db.commit()
        await update.effective_chat.send_message(_t(child.language, "verify_ok"))


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    async with get_session_factory()() as db:
        child = await db.scalar(
            select(ChildAccount).where(ChildAccount.telegram_chat_id == chat_id)
        )
        if child is None:
            await update.effective_chat.send_message(_t("ru", "login_not_verified"))
            return
        if not child.is_verified:
            await update.effective_chat.send_message(_t(child.language, "login_not_verified"))
            return
        redis = create_redis_client()
        try:
            otp = await issue_otp(redis, child.id)
        finally:
            await redis.aclose()
        await update.effective_chat.send_message(
            _t(child.language, "login_ok").format(code=otp)
        )


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    child = await _find_child_by_chat(chat_id)
    lang = child.language if child else "ru"
    await update.effective_chat.send_message(_t(lang, "fallback"))


def build_application() -> Application:
    """Build the PTB Application (raises RuntimeError when token is unset)."""
    if not settings.telegram_bot_token:
        raise RuntimeError("telegram_bot_token is not configured")
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("verify", cmd_verify))
    application.add_handler(CommandHandler("login", cmd_login))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))
    return application
