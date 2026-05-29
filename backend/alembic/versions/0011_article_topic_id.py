"""Add articles.topic_id so each article remembers which search fetched it.

Until now only Cases were tagged with the active topic; raw articles
(including those Gemini rejected) had no link back to the search that
pulled them. The Raw Articles tab needs that link so each row can show
which keyword/topic surfaced the article.

Existing articles get backfilled to the default "Homicide Sentencings"
topic so the column is never NULL for rows that pre-date this change.

Revision ID: 0011_article_topic_id
Revises: 0010_topics
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_article_topic_id"
down_revision: Union[str, None] = "0010_topics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_TOPIC_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column(
            "topic_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # Backfill: for articles already linked to a case, copy the case's
    # topic_id. For the rest, attribute them to the default topic so the
    # "Raw Articles" view shows a chip even for pre-existing rows.
    op.execute(sa.text(
        "UPDATE articles a "
        "SET topic_id = c.topic_id "
        "FROM cases c "
        "WHERE a.case_id = c.id AND a.topic_id IS NULL"
    ))
    op.execute(sa.text(
        f"UPDATE articles SET topic_id = '{DEFAULT_TOPIC_ID}'::uuid "
        f"WHERE topic_id IS NULL"
    ))
    op.create_index("ix_articles_topic_id", "articles", ["topic_id"])


def downgrade() -> None:
    op.drop_index("ix_articles_topic_id", table_name="articles")
    op.drop_column("articles", "topic_id")
