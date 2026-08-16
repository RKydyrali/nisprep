"""Authentication: passwords, JWT, activation codes, OTP."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import get_session, redis_get_json, redis_set_json
from app.models import ChildAccount, User

settings: Settings = get_settings()

_OTP_TTL_SECONDS = 300
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"

security = HTTPBearer(auto_error=False)


def normalize_username(username: str) -> str:
    """Telegram usernames are case-insensitive: strip '@', lowercase."""
    return username.strip().lstrip("@").lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str, child_id: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "child_id": child_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен истёк. Войдите заново",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен"
        ) from exc
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден"
        )
    return user


async def get_current_parent(user: User = Depends(get_current_user)) -> User:
    if user.role != "PARENT":
        raise HTTPException(status_code=403, detail="Доступ только для родителей")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Доступ только для администратора")
    return user


async def get_current_child(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ChildAccount:
    if user.role != "CHILD":
        raise HTTPException(status_code=403, detail="Доступ только для ученика")
    child = await db.scalar(select(ChildAccount).where(ChildAccount.user_id == user.id))
    if child is None:
        raise HTTPException(status_code=403, detail="Учётная запись ученика не найдена")
    return child


def generate_activation_code() -> str:
    """8-char code from an alphabet without lookalike characters (0O1Il)."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(8))


async def issue_otp(redis, child_id: int) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis_set_json(redis, f"otp:{child_id}", {"code": code}, _OTP_TTL_SECONDS)
    return code


async def verify_otp(redis, child_id: int, code: str | None) -> bool:
    if not code:
        return False
    # Атомарное чтение+удаление: параллельные попытки с одним кодом не пройдут.
    raw = await redis.getdel(f"otp:{child_id}")
    if raw is None:
        return False
    try:
        stored = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return False
    if secrets.compare_digest(str(stored.get("code", "")), str(code)):
        return True
    return False
