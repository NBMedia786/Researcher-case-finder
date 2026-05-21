"""add mediastack and gdelt sources, deactivate newsapi

Revision ID: 0003_add_mediastack_gdelt
Revises: 0002_seed_initial_sources
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_add_mediastack_gdelt"
down_revision: Union[str, None] = "0002_seed_initial_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO sources (id, name, type, config, is_active,
                             items_fetched_24h, items_extracted_24h,
                             consecutive_failures)
        VALUES
        (gen_random_uuid(), 'mediastack', 'news_api', '{}'::jsonb, true, 0, 0, 0),
        (gen_random_uuid(), 'gdelt', 'api', '{}'::jsonb, true, 0, 0, 0)
    """))
    op.execute(sa.text("UPDATE sources SET is_active = false WHERE name = 'newsapi'"))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM sources WHERE name IN ('mediastack', 'gdelt')"))
    op.execute(sa.text("UPDATE sources SET is_active = true WHERE name = 'newsapi'"))
