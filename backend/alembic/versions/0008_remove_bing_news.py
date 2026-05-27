"""Remove bing_news source row (Bing Search v7 retired by Microsoft).

Revision ID: 0008_remove_bing_news
Revises: 0007_more_sources
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_remove_bing_news"
down_revision: Union[str, None] = "0007_more_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM sources WHERE name = 'bing_news'"))


def downgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO sources (id, name, type, config, is_active,
                             items_fetched_24h, items_extracted_24h,
                             consecutive_failures)
        VALUES (gen_random_uuid(), 'bing_news', 'web_search', '{}'::jsonb,
                false, 0, 0, 0)
    """))
