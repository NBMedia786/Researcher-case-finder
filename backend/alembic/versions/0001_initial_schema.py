"""Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid() (useful for Postgres defaults)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Enum types are auto-created by SQLAlchemy when the first table that
    # references each one is created (create_type=True on each Enum column).
    # We don't pre-create them explicitly — that caused duplicate-type errors
    # because the Column-level Enum's _on_table_create event tries to create
    # the type a second time regardless of create_type=False.

    # --- users table (no FK dependencies) ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column(
            "role",
            sa.Enum("admin", "researcher", name="user_role", create_type=True),
            nullable=False,
            server_default="researcher",
        ),
        sa.Column("google_sub", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("google_sub", name="uq_users_google_sub"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- cases table (FK to users) ---
    op.create_table(
        "cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("defendant_name", sa.String(), nullable=False),
        sa.Column("defendant_name_normalized", sa.String(), nullable=False),
        sa.Column("defendant_age", sa.Integer(), nullable=True),
        sa.Column("defendant_hometown", sa.String(), nullable=True),
        sa.Column("victims", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("charges", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sentence_text", sa.String(), nullable=True),
        sa.Column("sentence_years", sa.Integer(), nullable=True),
        sa.Column(
            "sentence_type",
            sa.Enum("years", "life", "life_no_parole", "death", name="sentence_type", create_type=True),
            nullable=True,
        ),
        sa.Column("sentencing_date", sa.Date(), nullable=False),
        sa.Column("court_name", sa.String(), nullable=True),
        sa.Column("county", sa.String(), nullable=True),
        sa.Column("state", sa.CHAR(2), nullable=False),
        sa.Column("docket_number", sa.String(), nullable=True),
        sa.Column("judge_name", sa.String(), nullable=True),
        sa.Column("prosecuting_office", sa.String(), nullable=True),
        sa.Column("investigating_agency", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_score", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "status",
            sa.Enum(
                "new", "reviewing", "approved", "rejected",
                "foia_filed", "records_received", "archived",
                name="case_status",
                create_type=True,
            ),
            nullable=False,
            server_default="new",
        ),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.create_index("ix_cases_defendant_name_normalized", "cases", ["defendant_name_normalized"])
    op.create_index("ix_cases_sentencing_date", "cases", ["sentencing_date"])
    op.create_index("ix_cases_state", "cases", ["state"])
    op.create_index("ix_cases_status", "cases", ["status"])

    # --- sources table (no FK dependencies) ---
    op.create_table(
        "sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("news_api", "rss", "scraper", "api", "webhook", name="source_type", create_type=True),
            nullable=False,
        ),
        sa.Column("config", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_fetched_24h", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_extracted_24h", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.UniqueConstraint("name", name="uq_sources_name"),
    )

    # --- articles table (FK to cases and sources) ---
    op.create_table(
        "articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "news_api", "gdelt", "doj", "da_office", "courtlistener", "google_alert",
                name="article_source_type",
                create_type=True,
            ),
            nullable=False,
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extracted_json", JSONB(), nullable=True),
        sa.Column(
            "extraction_status",
            sa.Enum("pending", "extracted", "failed", "no_match", name="extraction_status", create_type=True),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("extraction_model", sa.String(), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.UniqueConstraint("url", name="uq_articles_url"),
    )
    op.create_index("ix_articles_case_id", "articles", ["case_id"])
    op.create_index("ix_articles_url", "articles", ["url"], unique=True)
    op.create_index("ix_articles_extraction_status", "articles", ["extraction_status"])

    # --- audit_log table (FK to users) ---
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # --- Composite indexes on cases ---
    op.create_index(
        "ix_cases_status_sentencing_date",
        "cases", ["status", "sentencing_date"], unique=False,
    )
    op.create_index(
        "ix_cases_dedup",
        "cases", ["defendant_name_normalized", "sentencing_date", "state"], unique=False,
    )
    op.create_index(
        "ix_cases_state_county",
        "cases", ["state", "county"], unique=False,
    )


def downgrade() -> None:
    # Drop composite indexes
    op.drop_index("ix_cases_state_county", table_name="cases")
    op.drop_index("ix_cases_dedup", table_name="cases")
    op.drop_index("ix_cases_status_sentencing_date", table_name="cases")

    # Drop audit_log
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_table("audit_log")

    # Drop articles
    op.drop_index("ix_articles_extraction_status", table_name="articles")
    op.drop_index("ix_articles_url", table_name="articles")
    op.drop_index("ix_articles_case_id", table_name="articles")
    op.drop_table("articles")

    # Drop sources
    op.drop_table("sources")

    # Drop cases
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_state", table_name="cases")
    op.drop_index("ix_cases_sentencing_date", table_name="cases")
    op.drop_index("ix_cases_defendant_name_normalized", table_name="cases")
    op.drop_table("cases")

    # Drop users
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    # Drop enum types (in reverse creation order)
    op.execute("DROP TYPE IF EXISTS extraction_status;")
    op.execute("DROP TYPE IF EXISTS article_source_type;")
    op.execute("DROP TYPE IF EXISTS source_type;")
    op.execute("DROP TYPE IF EXISTS case_status;")
    op.execute("DROP TYPE IF EXISTS sentence_type;")
    op.execute("DROP TYPE IF EXISTS user_role;")
