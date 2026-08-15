"""Analytics and smart error-log endpoints."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_redis, get_session
from app.models import ChildAccount, User
from app.schemas.analytics import DueErrorLogOut, ReadinessOut
from app.services import analytics_service
from app.services.auth_service import get_current_child, get_current_parent

router = APIRouter(tags=["analytics"])


async def _resolve_child(
    child_id: int | None,
    parent: User,
    db: AsyncSession,
) -> ChildAccount:
    if child_id is not None:
        child = await db.get(ChildAccount, child_id)
        if child is None or child.parent_id != parent.id:
            raise HTTPException(status_code=404, detail="Ученик не найден")
        return child
    children = (
        await db.scalars(select(ChildAccount).where(ChildAccount.parent_id == parent.id))
    ).all()
    if not children:
        raise HTTPException(status_code=404, detail="У вас нет учеников")
    return children[0]


@router.get("/analytics/readiness", response_model=ReadinessOut)
async def readiness_for_child(
    child: ChildAccount = Depends(get_current_child),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await analytics_service.get_readiness(db, child)


@router.get("/analytics/parent/readiness", response_model=ReadinessOut)
async def readiness_for_parent(
    child_id: int | None = Query(default=None),
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_session),
) -> dict:
    child = await _resolve_child(child_id, parent, db)
    return await analytics_service.get_readiness(db, child)


@router.get("/smart-error-log/due", response_model=DueErrorLogOut)
async def due_error_log(
    child: ChildAccount = Depends(get_current_child),
    db: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    return await analytics_service.get_due_error_log(db, redis, child)
