"""activation_code nullable (one-time use, cleared after /verify)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("child_accounts", "activation_code", existing_type=sa.String(length=16), nullable=True)


def downgrade() -> None:
    op.alter_column("child_accounts", "activation_code", existing_type=sa.String(length=16), nullable=False)
