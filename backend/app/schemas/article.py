from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel


class ArticleListItem(BaseModel):
    id: UUID
    url: str
    title: Optional[str]
    source_name: str
    source_type: str
    published_at: Optional[datetime]
    created_at: datetime
    extraction_status: str
    extraction_error: Optional[str]
    case_id: Optional[UUID]
    topic_id: Optional[UUID] = None
    # Search keyword/topic that fetched this article — shown as a chip on
    # each row so researchers can see which search surfaced it.
    topic_name: Optional[str] = None
    # Short reason derived by the API for UI display, e.g.
    # "Defendant not yet sentenced (trial ongoing)" — comes from the LLM's
    # rejection note in extracted_json when no_match, else from
    # extraction_error.
    rejection_reason: Optional[str] = None
    # Best-effort fields lifted from extracted_json so the UI can preview a
    # rejected article's likely defendant/state without opening the article.
    extracted_defendant_name: Optional[str] = None
    extracted_state: Optional[str] = None
    extracted_sentencing_date: Optional[str] = None

    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    items: list[ArticleListItem]
    total: int
    page: int
    page_size: int


class ArticleStatusCounts(BaseModel):
    all: int
    extracted: int
    no_match: int
    failed: int
    pending: int


class PromoteRequest(BaseModel):
    # Allow the researcher to override / fill in fields the LLM didn't
    # extract. Required fields fall back to extracted_json values when not
    # provided here.
    defendant_name: Optional[str] = None
    sentencing_date: Optional[str] = None  # YYYY-MM-DD
    state: Optional[str] = None
    notes: Optional[str] = None


class PromoteResponse(BaseModel):
    case_id: UUID
    created: bool
    reused_existing: bool
