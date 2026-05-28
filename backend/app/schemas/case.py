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
    assigned_to: Optional[str] = None
    summary: Optional[str]
    created_at: datetime
    topic_id: Optional[UUID] = None
    topic_name: Optional[str] = None

    class Config:
        from_attributes = True


class CaseListResponse(BaseModel):
    items: list[CaseListItem]
    total: int
    page: int
    page_size: int


class CaseArticle(BaseModel):
    id: UUID
    url: str
    title: Optional[str]
    source_name: str
    source_type: str
    published_at: Optional[datetime]

    class Config:
        from_attributes = True


class CaseDetail(CaseListItem):
    victims: list
    charges: list
    docket_number: Optional[str]
    judge_name: Optional[str]
    court_name: Optional[str]
    prosecuting_office: Optional[str]
    investigating_agency: Optional[str]
    sentence_years: Optional[int]
    notes: Optional[str]
    articles: list[CaseArticle]


class CaseUpdate(BaseModel):
    defendant_name: Optional[str] = None
    defendant_age: Optional[int] = None
    defendant_hometown: Optional[str] = None
    court_name: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    docket_number: Optional[str] = None
    judge_name: Optional[str] = None
    prosecuting_office: Optional[str] = None
    investigating_agency: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
