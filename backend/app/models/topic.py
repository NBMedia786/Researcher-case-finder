"""Topic model — saved search profile used by the pipeline.

A Topic is a named configuration that controls what the pipeline looks
for: keyword queries, the LLM match criteria, and the recency window.
Exactly one topic is active at any time (enforced by a partial unique
index — see migration 0010). The active topic drives the next pipeline
run; switching the active topic switches what kinds of cases the system
collects.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db import Base


# Deterministic UUID for the "Homicide Sentencings" topic seeded by
# migration 0010. Used as the server default for cases.topic_id so new
# cases auto-tag even before pipeline code is topic-aware.
DEFAULT_TOPIC_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False, unique=True)
    # List of plain keyword phrases (e.g. ["sentenced murder", "kidnapping"]).
    # Each source class adapts these into its native query syntax at fetch time.
    queries = Column(JSONB, nullable=False, default=list)
    # Plain-English description injected into the Gemini system prompt to
    # tell the LLM what counts as a match for this topic.
    extraction_criteria = Column(Text, nullable=False, default="")
    # How old (in days) can the underlying event be before we drop the
    # extracted case as "no_match". Overrides settings.sentencing_lookback_days
    # for the active topic.
    recency_days = Column(Integer, nullable=False, default=7)
    # Exactly one topic has is_active=true at any moment (partial unique
    # index enforces this at the DB level — see migration 0010).
    is_active = Column(Boolean, nullable=False, default=False)
    # Marks the "Homicide Sentencings" topic seeded by migration. Cannot
    # be deleted by the UI; ensures cases.topic_id default stays valid.
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
