"""Pipeline runs table

Revision ID: 0004_pipeline_runs
Revises: 0003_add_mediastack_gdelt
Create Date: 2026-05-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0004_pipeline_runs"
down_revision: Union[str, None] = "0003_add_mediastack_gdelt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("started_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_source", sa.String(), nullable=True),
        sa.Column("total_fetched", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_extracted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_new_cases", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("per_source", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("errors", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
