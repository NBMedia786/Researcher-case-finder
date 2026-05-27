from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class TopicBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    queries: list[str] = Field(default_factory=list)
    extraction_criteria: str = ""
    recency_days: int = Field(default=7, ge=1, le=3650)


class TopicCreate(TopicBase):
    pass


class TopicUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    queries: Optional[list[str]] = None
    extraction_criteria: Optional[str] = None
    recency_days: Optional[int] = Field(default=None, ge=1, le=3650)


class TopicItem(TopicBase):
    id: UUID
    is_active: bool
    is_default: bool
    case_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TopicList(BaseModel):
    items: list[TopicItem]
    total: int
