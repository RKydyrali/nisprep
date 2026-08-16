"""index tuning: composite (child_id, micro_skill_id), drop duplicate indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Дубли: лидирующая колонка уже покрыта составными индексами.
    op.drop_index("ix_user_response_logs_child_id", table_name="user_response_logs")
    op.drop_index("ix_error_log_items_child_id", table_name="error_log_items")
    # Группировка weak_skills / gap_graph (group by micro_skill_id).
    op.create_index(
        "ix_user_response_logs_child_micro",
        "user_response_logs",
        ["child_id", "micro_skill_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_response_logs_child_micro", table_name="user_response_logs")
    op.create_index("ix_user_response_logs_child_id", "user_response_logs", ["child_id"])
    op.create_index("ix_error_log_items_child_id", "error_log_items", ["child_id"])
