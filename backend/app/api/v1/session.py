"""Session endpoints: start / submit / state for adaptive testing."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_redis, get_session
from app.models import ChildAccount
from app.schemas.session import QuestionOut, SessionStartIn, SessionStateOut, SubmitIn, SubmitOut
from app.services import adaptive_test_service as ats
from app.services.auth_service import get_current_child

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/start", response_model=QuestionOut)
async def start_session(
    payload: SessionStartIn,
    child: ChildAccount = Depends(get_current_child),
    db: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    try:
        return await ats.start_session(db, redis, child, payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/submit", response_model=SubmitOut)
async def submit_answer(
    payload: SubmitIn,
    child: ChildAccount = Depends(get_current_child),
    db: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    try:
        return await ats.submit_answer(
            db,
            redis,
            payload.session_id or None,
            child,
            payload.template_id,
            payload.params,
            payload.answer,
            payload.time_taken_sec,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/state/{session_id}", response_model=SessionStateOut)
async def session_state(
    session_id: str,
    child: ChildAccount = Depends(get_current_child),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    state = await ats.get_session_state(redis, session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена или истекла")
    if int(state.get("child_id", -1)) != child.id:
        raise HTTPException(status_code=403, detail="Сессия принадлежит другому ученику")
    return state
