"""Seed marshall_project, prnewswire, newsdata, gnews, bing_news source rows

Revision ID: 0007_more_sources
Revises: 0006_new_sources
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_more_sources"
down_revision: Union[str, None] = "0006_new_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Marshall Project and PR Newswire are keyless RSS feeds — active by
    # default. NewsData / GNews / Bing all need API keys, so they start
    # inactive; flip on after pasting keys into .env.
    op.execute(sa.text("""
        INSERT INTO sources (id, name, type, config, is_active,
                             items_fetched_24h, items_extracted_24h,
                             consecutive_failures)
        VALUES
        (gen_random_uuid(), 'marshall_project', 'rss',        '{}'::jsonb, true,  0, 0, 0),
        (gen_random_uuid(), 'prnewswire',       'rss',        '{}'::jsonb, true,  0, 0, 0),
        (gen_random_uuid(), 'newsdata',         'news_api',   '{}'::jsonb, false, 0, 0, 0),
        (gen_random_uuid(), 'gnews',            'news_api',   '{}'::jsonb, false, 0, 0, 0),
        (gen_random_uuid(), 'bing_news',        'web_search', '{}'::jsonb, false, 0, 0, 0)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM sources WHERE name IN ("
        "'marshall_project', 'prnewswire', 'newsdata', 'gnews', 'bing_news')"
    ))
