import uuid
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

ARTICLE_SOURCE_TYPE = (
    "news_api", "gdelt", "doj", "da_office", "courtlistener", "google_alert",
    # Added in migration 0009 for the new sources:
    "web_search",     # serpapi, tavily
    "rss",            # marshall_project, prnewswire
    "court_records",  # courtlistener (new source emits this)
)
EXTRACTION_STATUS = ("pending", "extracted", "failed", "no_match")


class Article(Base):
    __tablename__ = "articles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=True)
    source_name = Column(String, nullable=False)
    source_type = Column(Enum(*ARTICLE_SOURCE_TYPE, name="article_source_type"), nullable=False)
    url = Column(String, unique=True, nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    title = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)
    extracted_json = Column(JSONB, nullable=True)
    extraction_status = Column(Enum(*EXTRACTION_STATUS, name="extraction_status"),
                               nullable=False, default="pending", index=True)
    extraction_model = Column(String, nullable=True)
    extraction_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
