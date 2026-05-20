import uuid
from sqlalchemy import Column, String, Integer, Date, DateTime, Enum, Text, ForeignKey, CHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

CASE_STATUS = ("new", "reviewing", "approved", "rejected",
               "foia_filed", "records_received", "archived")
SENTENCE_TYPE = ("years", "life", "life_no_parole", "death")


class Case(Base):
    __tablename__ = "cases"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    defendant_name = Column(String, nullable=False)
    defendant_name_normalized = Column(String, nullable=False, index=True)
    defendant_age = Column(Integer, nullable=True)
    defendant_hometown = Column(String, nullable=True)
    victims = Column(JSONB, nullable=False, default=list)
    charges = Column(JSONB, nullable=False, default=list)
    sentence_text = Column(String, nullable=True)
    sentence_years = Column(Integer, nullable=True)
    sentence_type = Column(Enum(*SENTENCE_TYPE, name="sentence_type"), nullable=True)
    sentencing_date = Column(Date, nullable=False, index=True)
    court_name = Column(String, nullable=True)
    county = Column(String, nullable=True)
    state = Column(CHAR(2), nullable=False, index=True)
    docket_number = Column(String, nullable=True)
    judge_name = Column(String, nullable=True)
    prosecuting_office = Column(String, nullable=True)
    investigating_agency = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    content_score = Column(Integer, nullable=False, default=1)
    status = Column(Enum(*CASE_STATUS, name="case_status"), nullable=False, default="new", index=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
