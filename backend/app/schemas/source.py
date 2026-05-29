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
    # API-key admin fields — populated by the sources router so the UI
    # can render an "API Key" column with edit. Sources that don't need
    # a key (RSS feeds, free APIs) have key_field=null.
    key_field: Optional[str] = None
    key_preview: Optional[str] = None
    key_source: Optional[str] = None   # "config" | "env" | None

    class Config:
        from_attributes = True


class SourceList(BaseModel):
    items: list[SourceItem]
    total: int


class SourceToggle(BaseModel):
    is_active: bool


class SourceConfigUpdate(BaseModel):
    """Update credential fields on a Source's config blob. Only fields
    listed in SOURCE_KEY_FIELDS for this source are honored. Sending an
    empty string clears the key (falls back to env var at runtime)."""
    api_key: Optional[str] = None
    api_token: Optional[str] = None
