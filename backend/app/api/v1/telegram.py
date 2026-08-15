"""Telegram webhook endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings

router = APIRouter(prefix="/telegram", tags=["telegram"])

settings = get_settings()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    secret: str | None = None,
    x_webhook_secret: str | None = Header(default=None),
) -> dict:
    if settings.webhook_secret:
        provided = secret or x_webhook_secret
        if provided != settings.webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    bot_application = getattr(request.app.state, "bot_application", None)
    if bot_application is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    from telegram import Update

    update = Update.de_json(body, bot_application.bot)
    await bot_application.process_update(update)
    return {"ok": True}
