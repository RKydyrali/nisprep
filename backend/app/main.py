"""FastAPI application entry point: uvicorn app.main:app."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.db.base import create_redis_client, init_db

logger = logging.getLogger(__name__)
settings: Settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    redis = create_redis_client()
    try:
        await redis.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis is unreachable at startup: %s", exc)
    finally:
        await redis.aclose()

    bot_application = None
    if settings.telegram_bot_token:
        try:
            from app.bot.handlers import build_application

            bot_application = build_application()
            await asyncio.wait_for(bot_application.initialize(), timeout=15)
            await asyncio.wait_for(bot_application.start(), timeout=15)
            app.state.bot_application = bot_application
        except Exception as exc:  # noqa: BLE001 - API must start even if Telegram is down
            logger.warning("Telegram bot init skipped in API process: %s", exc)
            app.state.bot_application = None
    else:
        app.state.bot_application = None

    yield

    if bot_application is not None:
        await bot_application.stop()
        await bot_application.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": jsonable_encoder(exc.errors()),
                "message": "Ошибка валидации данных",
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        if settings.env == "prod":
            # M6: наружу — фиксированное сообщение, детали только в логах.
            return JSONResponse(
                status_code=500,
                content={"detail": "Внутренняя ошибка сервера"},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера", "message": str(exc)},
        )

    return app


app = create_app()
