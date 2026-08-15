"""Content (question template) admin schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AnswerType = Literal["integer", "float", "choice", "text"]


class TemplateCreateIn(BaseModel):
    subject_code: str = Field(min_length=2, max_length=16)
    micro_skill_id: int
    title: str = Field(min_length=2, max_length=255)
    question_text: str = Field(min_length=5, max_length=2000)
    param_schema: dict[str, Any] = Field(default_factory=dict)
    answer_type: AnswerType = "integer"
    answer_expr: str = Field(min_length=1, max_length=255)
    choices: list[str] | None = None
    difficulty_b: float = Field(ge=-3.0, le=3.0, default=0.0)
    discrimination_a: float = Field(ge=0.1, le=3.0, default=1.0)
    is_demo: bool = False

    @field_validator("choices")
    @classmethod
    def _check_choices(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) < 2:
            raise ValueError("choices must contain at least 2 options")
        return v


class TemplateUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    question_text: str | None = Field(default=None, min_length=5, max_length=2000)
    param_schema: dict[str, Any] | None = None
    answer_type: AnswerType | None = None
    answer_expr: str | None = Field(default=None, min_length=1, max_length=255)
    choices: list[str] | None = None
    difficulty_b: float | None = Field(default=None, ge=-3.0, le=3.0)
    discrimination_a: float | None = Field(default=None, ge=0.1, le=3.0)
    is_demo: bool | None = None
    micro_skill_id: int | None = None


class TemplateOut(BaseModel):
    id: int
    subject_id: int
    subject_code: str
    micro_skill_id: int
    title: str
    question_text: str
    param_schema: dict[str, Any]
    answer_type: str
    answer_expr: str
    choices: list[str] | None = None
    difficulty_b: float
    discrimination_a: float
    is_demo: bool
    created_at: datetime
