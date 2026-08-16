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
from app.models import ChildAccount, User
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
        "verify_taken": "Этот аккаунт уже привязан к другому Telegram-чату. Если это ваш аккаунт — обратитесь к родителю.",
        "parent_verify_ok": "Родительский чат привязан! ✅ Теперь вы будете получать еженедельные дайджесты в этом чате.",
        "login_ok": "Ваш код входа: {code}. Введите его на сайте danyshpan.xyz.",
        "login_rate_limited": "Слишком много запросов кода. Подождите 5 минут.",
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
        "verify_taken": "Бұл аккаунт басқа Telegram-чатқа байланған. Бұл сіздің аккаунтыңыз болса — ата-анаңызға хабарласыңыз.",
        "parent_verify_ok": "Ата-ана чаты байланды! ✅ Енді апталық дайджесттерді осы чатқа аласыз.",
        "login_ok": "Кіру кодыңыз: {code}. Оны danyshpan.xyz сайтында енгізіңіз.",
        "login_rate_limited": "Код сұрау тым көп. 5 минут күтіңіз.",
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
            # Возможно, это код привязки родителя (Redis).
            redis = create_redis_client()
            try:
                bind = await redis.get(f"parent_bind:{code}")
            finally:
                await redis.aclose()
            if bind:
                try:
                    import json

                    user_id = int(json.loads(bind).get("user_id", 0))
                except (json.JSONDecodeError, TypeError, ValueError):
                    user_id = 0
                if user_id:
                    async with get_session_factory()() as db2:
                        parent = await db2.get(User, user_id)
                        if parent is not None and parent.role == "PARENT":
                            parent.telegram_chat_id = chat_id
                            await db2.commit()
                            await update.effective_chat.send_message(
                                _t("ru", "parent_verify_ok")
                            )
                            return
            existing = await _find_child_by_chat(chat_id)
            await update.effective_chat.send_message(
                _t(existing.language if existing else "ru", "verify_bad")
            )
            return
        if child.is_verified and child.telegram_chat_id != chat_id:
            # Аккаунт уже привязан к другому Telegram-чату — защита от захвата.
            await update.effective_chat.send_message(_t("ru", "verify_taken"))
            return
        # M9: чат не должен быть привязан к другому ребёнку.
        other = await db.scalar(
            select(ChildAccount)
            .where(
                ChildAccount.telegram_chat_id == chat_id,
                ChildAccount.id != child.id,
            )
            .limit(1)
        )
        if other is not None:
            await update.effective_chat.send_message(_t("ru", "verify_taken"))
            return
        child.is_verified = True
        child.telegram_chat_id = chat_id
        if update.effective_user is not None and update.effective_user.username:
            from app.services.auth_service import normalize_username

            new_username = normalize_username(update.effective_user.username)
            username_taken = await db.scalar(
                select(ChildAccount.id)
                .where(
                    ChildAccount.telegram_username == new_username,
                    ChildAccount.id != child.id,
                )
                .limit(1)
            )
            if username_taken is None:
                child.telegram_username = new_username
        child.activation_code = None  # одноразовый: повторное использование невозможно
        await db.commit()
        await update.effective_chat.send_message(_t(child.language, "verify_ok"))


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    # Rate limit: 3 OTP-запроса в 5 минут на чат — спам /login не должен
    # перезаписывать OTP и долбить Telegram API.
    redis = create_redis_client()
    try:
        try:
            import time

            window = int(time.time()) // 300
            count = await redis.incr(f"rl:bot_login:{chat_id}:{window}")
            await redis.expire(f"rl:bot_login:{chat_id}:{window}", 301)
        except Exception:  # noqa: BLE001 - Redis недоступен — пропускаем лимит
            count = 0
        if count > 3:
            await update.effective_chat.send_message(_t("ru", "login_rate_limited"))
            return
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
            otp = await issue_otp(redis, child.id)
            await update.effective_chat.send_message(
                _t(child.language, "login_ok").format(code=otp)
            )
    finally:
        await redis.aclose()


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    child = await _find_child_by_chat(chat_id)
    lang = child.language if child else "ru"
    await update.effective_chat.send_message(_t(lang, "fallback"))


async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует сбои обработки апдейтов (PTB сам ретраит сетевые ошибки)."""
    logger.warning(
        "update %s failed: %s",
        getattr(update, "update_id", "?"),
        context.error,
    )


def build_application() -> Application:
    """Build the PTB Application (raises RuntimeError when token is unset)."""
    if not settings.telegram_bot_token:
        raise RuntimeError("telegram_bot_token is not configured")
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("verify", cmd_verify))
    application.add_handler(CommandHandler("login", cmd_login))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))
    application.add_error_handler(handle_error)
    return application
