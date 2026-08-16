"""Auth endpoints: parent registration/login, children management, child OTP login."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot.notifier import send_otp
from app.db.base import get_redis, get_session, redis_set_json
from app.models import ChildAccount, User
from app.schemas.auth import (
    ChildCreateIn,
    ChildLoginIn,
    ChildOut,
    ChildUpdateIn,
    ChildrenListOut,
    LoginIn,
    OTPRequestIn,
    OTPRequestOut,
    ParentRegisterIn,
    ParentOut,
    TokenOut,
)
from app.services import auth_service
from app.services.rate_limit import client_ip, enforce_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_out(user: User, child: ChildAccount | None = None) -> TokenOut:
    token = auth_service.create_access_token(
        user.id, user.role, child_id=child.id if child else None
    )
    if child is not None:
        return TokenOut(
            access_token=token,
            user=ParentOut(id=user.id, full_name=user.full_name, email=user.email),
            child=ChildOut.model_validate(child, from_attributes=True),
        )
    return TokenOut(
        access_token=token,
        user=ParentOut(id=user.id, full_name=user.full_name, email=user.email),
    )


@router.post("/parent/register", response_model=TokenOut, status_code=200)
async def parent_register(
    payload: ParentRegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> TokenOut:
    await enforce_rate_limit(redis, f"register:ip:{client_ip(request)}", 10, 3600)
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже зарегистрирован"
        )
    user = User(
        role="PARENT",
        email=payload.email,
        hashed_password=auth_service.hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _token_out(user)


@router.post("/parent/login", response_model=TokenOut)
async def parent_login(
    payload: LoginIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> TokenOut:
    await enforce_rate_limit(
        redis, f"login:ip:{client_ip(request)}", 20, 300, "Слишком много попыток входа. Подождите 5 минут."
    )
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None or not auth_service.verify_password(payload.password, user.hashed_password):
        if user is not None:
            await enforce_rate_limit(
                redis, f"login:email:{user.email}", 10, 300,
                "Слишком много попыток входа. Подождите 5 минут.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт отключён")
    return _token_out(user)


@router.get("/children", response_model=ChildrenListOut)
async def list_children(
    parent: User = Depends(auth_service.get_current_parent),
    db: AsyncSession = Depends(get_session),
) -> ChildrenListOut:
    children = (
        await db.scalars(
            select(ChildAccount)
            .options(selectinload(ChildAccount.user))
            .where(ChildAccount.parent_id == parent.id)
            .order_by(ChildAccount.id)
        )
    ).all()
    return ChildrenListOut(
        children=[ChildOut.model_validate(c, from_attributes=True) for c in children]
    )


@router.post("/children", response_model=ChildOut, status_code=201)
async def create_child(
    payload: ChildCreateIn,
    parent: User = Depends(auth_service.get_current_parent),
    db: AsyncSession = Depends(get_session),
) -> ChildOut:
    existing = await db.scalar(
        select(ChildAccount).where(
            ChildAccount.telegram_username
            == auth_service.normalize_username(payload.telegram_username)
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот Telegram-username уже привязан к другому ученику",
        )
    child_user = User(
        role="CHILD",
        email=None,
        hashed_password=None,
        full_name=payload.full_name,
    )
    db.add(child_user)
    await db.flush()
    child = ChildAccount(
        parent_id=parent.id,
        user_id=child_user.id,
        telegram_username=auth_service.normalize_username(payload.telegram_username),
        activation_code=auth_service.generate_activation_code(),
        is_verified=False,
        language=payload.language,
        password_hash=auth_service.hash_password(payload.password),
    )
    db.add(child)
    await db.commit()
    await db.refresh(child, attribute_names=["user"])
    return ChildOut.model_validate(child, from_attributes=True)


@router.patch("/children/{child_id}", response_model=ChildOut)
async def update_child(
    child_id: int,
    payload: ChildUpdateIn,
    parent: User = Depends(auth_service.get_current_parent),
    db: AsyncSession = Depends(get_session),
) -> ChildOut:
    child = await db.scalar(
        select(ChildAccount)
        .options(selectinload(ChildAccount.user))
        .where(ChildAccount.id == child_id)
    )
    if child is None or child.parent_id != parent.id:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates:
        child.password_hash = auth_service.hash_password(updates.pop("password"))
    if "full_name" in updates:
        if child.user is not None:
            child.user.full_name = updates.pop("full_name")
    if "telegram_username" in updates:
        normalized = auth_service.normalize_username(updates["telegram_username"])
        updates["telegram_username"] = normalized
        dup = await db.scalar(
            select(ChildAccount).where(
                ChildAccount.telegram_username == normalized,
                ChildAccount.id != child.id,
            )
        )
        if dup is not None:
            raise HTTPException(status_code=409, detail="Этот Telegram-username уже занят")
    for key, value in updates.items():
        setattr(child, key, value)
    await db.commit()
    await db.refresh(child)
    return ChildOut.model_validate(child, from_attributes=True)


@router.delete("/children/{child_id}", status_code=200)
async def delete_child(
    child_id: int,
    parent: User = Depends(auth_service.get_current_parent),
    db: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    child = await db.get(ChildAccount, child_id)
    if child is None or child.parent_id != parent.id:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    from app.models import ErrorLogItem, UserResponseLog

    for model in (UserResponseLog, ErrorLogItem):
        await db.execute(model.__table__.delete().where(model.child_id == child.id))
    user_id = child.user_id
    await db.delete(child)
    await db.flush()
    if user_id is not None:
        user = await db.get(User, user_id)
        if user is not None:
            await db.delete(user)
    await db.commit()
    return {"ok": True}


@router.post("/child/request-otp", response_model=OTPRequestOut)
async def child_request_otp(
    payload: OTPRequestIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> OTPRequestOut:
    await enforce_rate_limit(
        redis, f"req_otp:ip:{client_ip(request)}", 10, 60,
        "Слишком много запросов кода. Подождите минуту.",
    )
    child = await db.scalar(
        select(ChildAccount).where(
            ChildAccount.telegram_username
            == auth_service.normalize_username(payload.telegram_username)
        )
    )
    # M3: единый ответ в любом случае — без раскрытия существования username
    # и статуса верификации анонимам. Инструкция по активации всегда на странице.
    if child is None or not child.is_verified or child.telegram_chat_id is None:
        return OTPRequestOut(
            sent=False,
            need_activation=False,
            message="Код отправляется только на активированный аккаунт. "
            "Если аккаунт создан — подтвердите его через бота: /verify <код>.",
        )
    await enforce_rate_limit(
        redis, f"req_otp:child:{child.id}", 5, 300,
        "Слишком много запросов кода. Подождите 5 минут.",
    )
    otp = await auth_service.issue_otp(redis, child.id)
    sent = await send_otp(child.telegram_chat_id, otp, child.language)
    if not sent:
        return OTPRequestOut(
            sent=False, message="Код не доставлен, попробуйте позже"
        )
    return OTPRequestOut(sent=True, message="Код отправлен в Telegram")


@router.post("/child/login-otp", response_model=TokenOut)
async def child_login_otp(
    payload: ChildLoginIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> TokenOut:
    await enforce_rate_limit(
        redis, f"login_otp:ip:{client_ip(request)}", 30, 300,
        "Слишком много попыток входа. Подождите 5 минут.",
    )
    child = await db.scalar(
        select(ChildAccount).where(
            ChildAccount.telegram_username
            == auth_service.normalize_username(payload.telegram_username)
        )
    )
    if child is None or not auth_service.verify_password(payload.password, child.password_hash):
        if child is not None:
            await enforce_rate_limit(
                redis, f"login_otp:child:{child.id}", 10, 300,
                "Слишком много попыток входа. Подождите 5 минут.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный Telegram-username или пароль",
        )
    await enforce_rate_limit(
        redis, f"login_otp:child:{child.id}", 10, 300,
        "Слишком много попыток входа. Подождите 5 минут.",
    )
    if not child.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подтвердите аккаунт через Telegram-бота: /start → /verify <код>",
        )
    if not payload.otp:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Введите OTP из Telegram-бота",
        )
    ok = await auth_service.verify_otp(redis, child.id, payload.otp)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный или истёкший OTP"
        )
    if child.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Учётная запись не привязана"
        )
    user = await db.get(User, child.user_id)
    if user is None:
        raise HTTPException(status_code=403, detail="Учётная запись не найдена")
    await db.refresh(child, attribute_names=["user"])
    return _token_out(user, child)


PARENT_BIND_TTL_SECONDS = 600


@router.post("/parent/bind-code", response_model=dict)
async def parent_bind_code(
    parent: User = Depends(auth_service.get_current_parent),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Выдаёт одноразовый код привязки Telegram-чата родителя (живёт 10 мин).

    Родитель отправляет боту /verify <код> — и получает еженедельные
    дайджесты и алерты в личные сообщения.
    """
    await enforce_rate_limit(redis, f"bind_code:user:{parent.id}", 5, 600)
    code = auth_service.generate_activation_code()
    await redis_set_json(
        redis, f"parent_bind:{code}", {"user_id": parent.id}, PARENT_BIND_TTL_SECONDS
    )
    return {"code": code, "ttl_seconds": PARENT_BIND_TTL_SECONDS}
