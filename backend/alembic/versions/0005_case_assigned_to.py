"""Add assigned_to column on cases

Revision ID: 0005_case_assigned_to
Revises: 0004_pipeline_runs
Create Date: 2026-05-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005_case_assigned_to"
down_revision: Union[str, None] = "0004_pipeline_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("assigned_to", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_cases_assigned_to", "cases", ["assigned_to"])


def downgrade() -> None:
    op.drop_index("ix_cases_assigned_to", table_name="cases")
    op.drop_column("cases", "assigned_to")
