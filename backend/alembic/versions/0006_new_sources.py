"""Seed serpapi, tavily, courtlistener source rows

Revision ID: 0006_new_sources
Revises: 0005_case_assigned_to
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_new_sources"
down_revision: Union[str, None] = "0005_case_assigned_to"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The new source rows use 'web_search' and 'court_records' values that
    # don't exist in the original source_type enum. Extend it FIRST in an
    # autocommit block (Postgres rule: ALTER TYPE ... ADD VALUE can't run
    # inside a transaction), then do the inserts.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'web_search'"
        )
        op.execute(
            "ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'court_records'"
        )

    # New sources are seeded as is_active=false by default — they need API
    # keys configured in .env before they can do anything useful. Flip them
    # to active via the Sources UI (or SQL) after keys are set.
    op.execute(sa.text("""
        INSERT INTO sources (id, name, type, config, is_active,
                             items_fetched_24h, items_extracted_24h,
                             consecutive_failures)
        VALUES
        (gen_random_uuid(), 'serpapi', 'web_search', '{}'::jsonb, false, 0, 0, 0),
        (gen_random_uuid(), 'tavily', 'web_search', '{}'::jsonb, false, 0, 0, 0),
        (gen_random_uuid(), 'courtlistener', 'court_records', '{}'::jsonb, true, 0, 0, 0)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM sources WHERE name IN ('serpapi', 'tavily', 'courtlistener')"
    ))
