"""Extend article_source_type enum with web_search, rss, court_records.

The new sources added in 0006 + 0007 emit IngestedArticle.source_type
values that didn't exist in the original article_source_type Postgres
enum, so inserts would fail with an InvalidTextRepresentation error
the moment those sources actually ran.

Revision ID: 0009_extend_article_source_type
Revises: 0008_remove_bing_news
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0009_extend_article_source_type"
down_revision: Union[str, None] = "0008_remove_bing_news"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block, so
    # we use Alembic's autocommit_block to commit the surrounding tx first.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE article_source_type ADD VALUE IF NOT EXISTS 'web_search'"
        )
        op.execute(
            "ALTER TYPE article_source_type ADD VALUE IF NOT EXISTS 'rss'"
        )
        op.execute(
            "ALTER TYPE article_source_type ADD VALUE IF NOT EXISTS 'court_records'"
        )


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; downgrade is a no-op.
    # The added values are harmless if unused.
    pass
