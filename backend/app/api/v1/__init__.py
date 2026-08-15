"""API v1 router: wires all endpoint modules together."""

from fastapi import APIRouter

from app.api.v1 import analytics, auth, content, health, session, telegram

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(session.router)
api_router.include_router(analytics.router)
api_router.include_router(content.router)
api_router.include_router(telegram.router)
api_router.include_router(health.router)
