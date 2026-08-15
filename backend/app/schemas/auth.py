"""Auth-related request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

LANGUAGE_CODES = ("ru", "kk")


class ParentRegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ParentOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: ParentOut | ChildOut | None = None
    child: ChildOut | None = None


class ChildCreateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    telegram_username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)
    language: str = "ru"

    @field_validator("language")
    @classmethod
    def _check_language(cls, v: str) -> str:
        if v not in LANGUAGE_CODES:
            raise ValueError("language must be 'ru' or 'kk'")
        return v


class ChildUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    telegram_username: str | None = Field(
        default=None, min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_]+$"
    )
    password: str | None = Field(default=None, min_length=6, max_length=128)
    language: str | None = None

    @field_validator("language")
    @classmethod
    def _check_language(cls, v: str | None) -> str | None:
        if v is not None and v not in LANGUAGE_CODES:
            raise ValueError("language must be 'ru' or 'kk'")
        return v


class ChildOut(BaseModel):
    id: int
    full_name: str
    telegram_username: str
    telegram_chat_id: int | None = None
    is_verified: bool = False
    language: str = "ru"
    activation_code: str | None = None
    current_elo: float = 1000.0
    theta_math: float = 0.0
    theta_quant: float = 0.0
    theta_nat_sci: float = 0.0
    theta_lang: float = 0.0
    streak_days: int = 0
    total_solved: int = 0
    total_correct: int = 0


class ChildrenListOut(BaseModel):
    children: list[ChildOut]


class ChildLoginIn(BaseModel):
    telegram_username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    otp: str | None = None


class OTPRequestIn(BaseModel):
    telegram_username: str = Field(min_length=2, max_length=64)


class OTPRequestOut(BaseModel):
    sent: bool
    need_activation: bool = False
    message: str | None = None
