"""Session/adaptive-test request and response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SessionMode = Literal["sprint", "day1", "day2", "cat", "free"]


class SessionStartIn(BaseModel):
    mode: SessionMode = "sprint"


class MicroSkillOut(BaseModel):
    id: int
    code: str
    name_ru: str
    name_kk: str


class QuestionOut(BaseModel):
    session_id: str
    question_id: int
    template_id: int
    micro_skill: MicroSkillOut
    question_text: str
    choices: list[str] | None = None
    answer_type: str
    params: dict[str, Any]
    time_limit_sec: int
    mode: str
    total_questions: int
    progress: float


class SubmitIn(BaseModel):
    session_id: str = Field(min_length=1)
    template_id: int
    params: dict[str, Any]
    answer: int | float | str
    time_taken_sec: float = Field(ge=0.0, le=7200.0)


class SubmitOut(BaseModel):
    session_id: str
    is_correct: bool
    correct_answer: Any
    theta_after: float | None = None
    elo_after: float | None = None
    elo_delta: float | None = None
    streak_days: int
    streak_bonus: float | None = None
    next_question: QuestionOut | None = None
    session_finished: bool


class SessionStateOut(BaseModel):
    session_id: str
    mode: str
    subject_code: str
    asked: list[int]
    question_idx: int
    max_questions: int
    answers: list[dict[str, Any]]
    ttl_remaining_sec: int
