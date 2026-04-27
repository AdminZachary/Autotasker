"""drop legacy sessions table

Revision ID: 20260419_02
Revises: 20260419_01
Create Date: 2026-04-19 10:48:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260419_02"
down_revision: Union[str, Sequence[str], None] = "20260419_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sessions")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token VARCHAR(255) PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at DATETIME NOT NULL
        )
        """
    )
