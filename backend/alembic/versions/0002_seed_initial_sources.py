"""seed initial sources

Revision ID: 0002_seed_initial_sources
Revises: 0001_initial_schema
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_seed_initial_sources"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgcrypto is available for gen_random_uuid()
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    op.execute(sa.text("""
        INSERT INTO sources (id, name, type, config, is_active,
                             items_fetched_24h, items_extracted_24h,
                             consecutive_failures)
        VALUES
        (gen_random_uuid(), 'newsapi', 'news_api', '{}'::jsonb, true, 0, 0, 0),
        (gen_random_uuid(), 'doj', 'rss', '{}'::jsonb, true, 0, 0, 0)
    """))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM sources WHERE name IN ('newsapi', 'doj')"))
