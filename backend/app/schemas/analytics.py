"""Analytics request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WeakSkillOut(BaseModel):
    micro_skill_id: int
    name_ru: str
    name_kk: str
    code: str
    accuracy: float
    count: int
    last_practiced_at: datetime | None = None


class GraphNodeOut(BaseModel):
    id: int
    name_ru: str
    name_kk: str
    accuracy: float
    weight: int


class GraphEdgeOut(BaseModel):
    from_id: int
    to_id: int
    value: float


class ReadinessOut(BaseModel):
    psi: float
    p_grant: float
    band: str
    theta: dict[str, float]
    t_speed: float
    weak_skills: list[WeakSkillOut]
    graph: dict[str, Any]
    history: dict[str, Any]


class ErrorLogQuestionOut(BaseModel):
    template_id: int
    params: dict[str, Any]
    question_text: str
    choices: list[str] | None = None
    correct_answer: Any
    answer_type: str
    difficulty_b: float
    discrimination_a: float
    micro_skill: dict[str, Any] | None = None


class DueErrorLogItemOut(BaseModel):
    item_id: int
    review_number: int
    ef: float
    interval_days: int
    next_review_at: datetime
    wrong_count: int
    question: ErrorLogQuestionOut


class DueErrorLogOut(BaseModel):
    items: list[DueErrorLogItemOut]
