import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False, default="running")
    started_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    current_source = Column(String, nullable=True)
    total_fetched = Column(Integer, nullable=False, default=0)
    total_extracted = Column(Integer, nullable=False, default=0)
    total_new_cases = Column(Integer, nullable=False, default=0)
    per_source = Column(JSONB, nullable=False, default=list)
    errors = Column(JSONB, nullable=False, default=list)
