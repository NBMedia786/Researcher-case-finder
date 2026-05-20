from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

VALID_ROLES = {"admin", "researcher"}


class UserItem(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: Optional[datetime]
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserList(BaseModel):
    items: list[UserItem]
    total: int


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
