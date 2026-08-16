"""SQLAlchemy ORM models for the Danyshpan platform.

Enums are stored as plain strings (native_enum=False style) so migrations stay
portable across PostgreSQL and SQLite; validation happens in the Pydantic layer.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="PARENT")  # ADMIN|PARENT|CHILD
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    children: Mapped[list["ChildAccount"]] = relationship(
        "ChildAccount",
        foreign_keys="ChildAccount.parent_id",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    child_account: Mapped["ChildAccount | None"] = relationship(
        "ChildAccount",
        foreign_keys="ChildAccount.user_id",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class ChildAccount(Base):
    __tablename__ = "child_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    telegram_username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    activation_code: Mapped[str | None] = mapped_column(String(16), unique=True, index=True, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    language: Mapped[str] = mapped_column(String(4), nullable=False, default="ru")  # ru|kk
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_elo: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)
    theta_math: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    theta_quant: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    theta_nat_sci: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    theta_lang: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    t_avg_math: Mapped[float] = mapped_column(Float, nullable=False, default=90.0)
    t_avg_quant: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    t_avg_nat_sci: Mapped[float] = mapped_column(Float, nullable=False, default=90.0)
    t_avg_lang: Mapped[float] = mapped_column(Float, nullable=False, default=120.0)
    streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_solved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    parent: Mapped[User] = relationship(
        "User", foreign_keys=[parent_id], back_populates="children", passive_deletes=True
    )
    user: Mapped[User | None] = relationship(
        "User", foreign_keys=[user_id], back_populates="child_account", passive_deletes=True
    )

    @property
    def full_name(self) -> str:
        return self.user.full_name if self.user is not None else self.telegram_username


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)  # math|quant|nat_sci|lang
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    name_kk: Mapped[str] = mapped_column(String(255), nullable=False)
    questions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    time_limit_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    per_question_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=90)

    topics: Mapped[list["Topic"]] = relationship(
        "Topic", back_populates="subject", cascade="all, delete-orphan", passive_deletes=True
    )


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    name_kk: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)

    subject: Mapped[Subject] = relationship("Subject", back_populates="topics")
    micro_skills: Mapped[list["MicroSkill"]] = relationship(
        "MicroSkill", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )


class MicroSkill(Base):
    __tablename__ = "micro_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    name_kk: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    difficulty_b: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discrimination_a: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    topic: Mapped[Topic] = relationship("Topic", back_populates="micro_skills")


class QuestionTemplate(Base):
    __tablename__ = "question_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    micro_skill_id: Mapped[int] = mapped_column(
        ForeignKey("micro_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    question_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    param_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    answer_type: Mapped[str] = mapped_column(String(16), nullable=False, default="integer")  # integer|float|choice|text
    answer_expr: Mapped[str] = mapped_column(String(255), nullable=False)
    choices: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    difficulty_b: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discrimination_a: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    subject: Mapped[Subject] = relationship("Subject", foreign_keys=[subject_id])
    micro_skill: Mapped[MicroSkill] = relationship(
        "MicroSkill", foreign_keys=[micro_skill_id], lazy="joined"
    )

    __table_args__ = (Index("ix_question_templates_is_demo", "is_demo"),)


class UserResponseLog(Base):
    __tablename__ = "user_response_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child_accounts.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[int] = mapped_column(
        ForeignKey("question_templates.id", ondelete="CASCADE"), nullable=False
    )
    micro_skill_id: Mapped[int] = mapped_column(
        ForeignKey("micro_skills.id", ondelete="CASCADE"), nullable=False
    )
    subject_code: Mapped[str] = mapped_column(String(16), nullable=False)
    params_used: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_taken_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    difficulty_b: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discrimination_a: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    theta_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    elo_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    elo_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # sprint|cat|day1|day2|free|revision
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_user_response_logs_child_id", "child_id"),
        Index("ix_user_response_logs_child_subject", "child_id", "subject_code"),
        Index("ix_user_response_logs_child_created", "child_id", "created_at"),
        Index("ix_user_response_logs_session_id", "session_id"),
    )


class ErrorLogItem(Base):
    __tablename__ = "error_log_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child_accounts.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[int] = mapped_column(
        ForeignKey("question_templates.id", ondelete="CASCADE"), nullable=False
    )
    micro_skill_id: Mapped[int] = mapped_column(
        ForeignKey("micro_skills.id", ondelete="CASCADE"), nullable=False
    )
    params_used: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    review_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quality: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ef: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_error_log_items_child_id", "child_id"),
        Index("ix_error_log_items_template_id", "template_id"),
        Index("ix_error_log_items_child_next", "child_id", "next_review_at"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default="free")  # free|premium
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payment_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="subscriptions")
