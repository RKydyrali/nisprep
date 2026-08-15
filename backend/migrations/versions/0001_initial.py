"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-15

Manual migration: mirrors app/models/entities.py exactly.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "child_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("telegram_username", sa.String(length=64), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("activation_code", sa.String(length=16), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(length=4), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("current_elo", sa.Float(), nullable=False),
        sa.Column("theta_math", sa.Float(), nullable=False),
        sa.Column("theta_quant", sa.Float(), nullable=False),
        sa.Column("theta_nat_sci", sa.Float(), nullable=False),
        sa.Column("theta_lang", sa.Float(), nullable=False),
        sa.Column("t_avg_math", sa.Float(), nullable=False),
        sa.Column("t_avg_quant", sa.Float(), nullable=False),
        sa.Column("t_avg_nat_sci", sa.Float(), nullable=False),
        sa.Column("t_avg_lang", sa.Float(), nullable=False),
        sa.Column("streak_days", sa.Integer(), nullable=False),
        sa.Column("total_solved", sa.Integer(), nullable=False),
        sa.Column("total_correct", sa.Integer(), nullable=False),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_child_accounts_user_id"),
    )
    op.create_index("ix_child_accounts_parent_id", "child_accounts", ["parent_id"], unique=False)
    op.create_index("ix_child_accounts_telegram_username", "child_accounts", ["telegram_username"], unique=True)
    op.create_index("ix_child_accounts_telegram_chat_id", "child_accounts", ["telegram_chat_id"], unique=False)
    op.create_index("ix_child_accounts_activation_code", "child_accounts", ["activation_code"], unique=True)

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_kk", sa.String(length=255), nullable=False),
        sa.Column("questions_count", sa.Integer(), nullable=False),
        sa.Column("time_limit_sec", sa.Integer(), nullable=False),
        sa.Column("per_question_sec", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subjects_code", "subjects", ["code"], unique=True)

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_kk", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_topics_subject_id", "topics", ["subject_id"], unique=False)

    op.create_table(
        "micro_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_kk", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("difficulty_b", sa.Float(), nullable=False),
        sa.Column("discrimination_a", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_micro_skills_topic_id", "micro_skills", ["topic_id"], unique=False)

    op.create_table(
        "question_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("micro_skill_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("question_text", sa.String(length=2000), nullable=False),
        sa.Column("param_schema", sa.JSON(), nullable=False),
        sa.Column("answer_type", sa.String(length=16), nullable=False),
        sa.Column("answer_expr", sa.String(length=255), nullable=False),
        sa.Column("choices", sa.JSON(), nullable=True),
        sa.Column("difficulty_b", sa.Float(), nullable=False),
        sa.Column("discrimination_a", sa.Float(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["micro_skill_id"], ["micro_skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_templates_subject_id", "question_templates", ["subject_id"], unique=False)
    op.create_index("ix_question_templates_micro_skill_id", "question_templates", ["micro_skill_id"], unique=False)
    op.create_index("ix_question_templates_is_demo", "question_templates", ["is_demo"], unique=False)

    op.create_table(
        "user_response_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("micro_skill_id", sa.Integer(), nullable=False),
        sa.Column("subject_code", sa.String(length=16), nullable=False),
        sa.Column("params_used", sa.JSON(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("time_taken_sec", sa.Float(), nullable=False),
        sa.Column("difficulty_b", sa.Float(), nullable=False),
        sa.Column("discrimination_a", sa.Float(), nullable=False),
        sa.Column("theta_after", sa.Float(), nullable=True),
        sa.Column("elo_after", sa.Float(), nullable=True),
        sa.Column("elo_delta", sa.Float(), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["question_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["micro_skill_id"], ["micro_skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_response_logs_child_id", "user_response_logs", ["child_id"], unique=False)
    op.create_index("ix_user_response_logs_child_subject", "user_response_logs", ["child_id", "subject_code"], unique=False)
    op.create_index("ix_user_response_logs_child_created", "user_response_logs", ["child_id", "created_at"], unique=False)
    op.create_index("ix_user_response_logs_session_id", "user_response_logs", ["session_id"], unique=False)

    op.create_table(
        "error_log_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("micro_skill_id", sa.Integer(), nullable=False),
        sa.Column("params_used", sa.JSON(), nullable=False),
        sa.Column("review_number", sa.Integer(), nullable=False),
        sa.Column("quality", sa.Float(), nullable=False),
        sa.Column("ef", sa.Float(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wrong_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["question_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["micro_skill_id"], ["micro_skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_log_items_child_id", "error_log_items", ["child_id"], unique=False)
    op.create_index("ix_error_log_items_template_id", "error_log_items", ["template_id"], unique=False)
    op.create_index("ix_error_log_items_child_next", "error_log_items", ["child_id", "next_review_at"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("payment_ref", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("error_log_items")
    op.drop_table("user_response_logs")
    op.drop_table("question_templates")
    op.drop_table("micro_skills")
    op.drop_table("topics")
    op.drop_table("subjects")
    op.drop_table("child_accounts")
    op.drop_table("users")
