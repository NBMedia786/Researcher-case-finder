from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class CaseListItem(BaseModel):
    id: UUID
    defendant_name: str
    defendant_age: Optional[int]
    defendant_hometown: Optional[str]
    sentencing_date: date
    state: str
    county: Optional[str]
    sentence_text: Optional[str]
    sentence_type: Optional[str]
    content_score: int
    status: str
    summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CaseListResponse(BaseModel):
    items: list[CaseListItem]
    total: int
    page: int
    page_size: int
