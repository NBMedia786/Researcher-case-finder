from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class SourceItem(BaseModel):
    id: UUID
    name: str
    type: str
    is_active: bool
    last_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    items_fetched_24h: int
    items_extracted_24h: int
    consecutive_failures: int
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class SourceList(BaseModel):
    items: list[SourceItem]
    total: int


class SourceToggle(BaseModel):
    is_active: bool
