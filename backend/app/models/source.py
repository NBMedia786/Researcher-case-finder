import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

SOURCE_TYPE = (
    "news_api", "rss", "scraper", "api", "webhook",
    # Added via migration 0006 for the new sources:
    "web_search",     # serpapi, tavily
    "court_records",  # courtlistener
)


class Source(Base):
    __tablename__ = "sources"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    type = Column(Enum(*SOURCE_TYPE, name="source_type"), nullable=False)
    config = Column(JSONB, nullable=False, default=dict)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    items_fetched_24h = Column(Integer, nullable=False, default=0)
    items_extracted_24h = Column(Integer, nullable=False, default=0)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
