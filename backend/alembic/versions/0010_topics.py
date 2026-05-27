"""Add topics table + cases.topic_id, seed default "Homicide Sentencings".

Topics let researchers define search profiles (queries + LLM match
criteria + recency window) from the UI without touching backend code.
Exactly one topic is active at any time; the active topic drives the
next pipeline run.

The "Homicide Sentencings" topic is seeded with a deterministic UUID
so cases.topic_id can have a server-default that points to it — that
way the running pipeline keeps creating cases under the default topic
even before the pipeline code is updated to handle topics explicitly.

Revision ID: 0010_topics
Revises: 0009_extend_article_source_type
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_topics"
down_revision: Union[str, None] = "0009_extend_article_source_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_TOPIC_ID = "00000000-0000-0000-0000-000000000001"

# Mirror the simple keyword-pair queries currently in all source files.
# Anyone editing this list later via the Topics UI updates the topics row,
# not source code.
DEFAULT_QUERIES = [
    "sentenced murder",
    "sentenced homicide",
    "sentence murder",
    "sentence homicide",
    "sentencing murder",
    "sentencing homicide",
]

DEFAULT_CRITERIA = (
    "An article reporting that a defendant has been sentenced in court for "
    "a homicide-related offense — murder, manslaughter, or related charges. "
    "Set is_match=true only when (a) a sentencing has occurred (not merely "
    "an arrest, indictment, trial, or appeal), AND (b) the underlying "
    "offense is a homicide (someone died as a direct result of the "
    "defendant's actions)."
)


def upgrade() -> None:
    op.create_table(
        "topics",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("queries", sa.dialects.postgresql.JSONB,
                  nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("extraction_criteria", sa.Text, nullable=False,
                  server_default=""),
        sa.Column("recency_days", sa.Integer, nullable=False,
                  server_default=sa.text("7")),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.false()),
        sa.Column("is_default", sa.Boolean, nullable=False,
                  server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    # Seed the default "Homicide Sentencings" topic with a fixed UUID so
    # the cases.topic_id column-default can point to it. Build SQL via
    # parameterized values to avoid escaping the criteria text manually.
    queries_json = '["sentenced murder","sentenced homicide","sentence murder","sentence homicide","sentencing murder","sentencing homicide"]'
    op.execute(
        sa.text(
            "INSERT INTO topics (id, name, queries, extraction_criteria, "
            "                    recency_days, is_active, is_default) "
            "VALUES (CAST(:tid AS uuid), :nm, CAST(:qs AS jsonb), :cr, 7, true, true)"
        ).bindparams(
            sa.bindparam("tid", DEFAULT_TOPIC_ID),
            sa.bindparam("nm", "Homicide Sentencings"),
            sa.bindparam("qs", queries_json),
            sa.bindparam("cr", DEFAULT_CRITERIA),
        )
    )

    # Add topic_id to cases with a server default pointing at the seeded
    # default topic. New inserts auto-tag without needing pipeline changes.
    op.add_column(
        "cases",
        sa.Column(
            "topic_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="SET NULL"),
            nullable=True,
            server_default=sa.text(f"'{DEFAULT_TOPIC_ID}'::uuid"),
        ),
    )

    # Backfill existing cases.
    op.execute(sa.text(
        f"UPDATE cases SET topic_id = '{DEFAULT_TOPIC_ID}'::uuid "
        f"WHERE topic_id IS NULL"
    ))

    op.create_index("ix_cases_topic_id", "cases", ["topic_id"])

    # Enforce that exactly one row has is_active=true at any time, via a
    # partial unique index on (is_active) WHERE is_active.
    op.create_index(
        "ix_topics_one_active",
        "topics",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("ix_topics_one_active", table_name="topics")
    op.drop_index("ix_cases_topic_id", table_name="cases")
    op.drop_column("cases", "topic_id")
    op.drop_table("topics")
