from pydantic import BaseModel
from uuid import UUID

class LoginRequest(BaseModel):
    id_token: str

class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: str
    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    user: UserOut
