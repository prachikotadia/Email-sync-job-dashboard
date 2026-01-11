from pydantic import BaseModel, EmailStr
from typing import Literal
from uuid import UUID

UserRole = Literal["viewer", "editor"]


class UserResponse(BaseModel):
    id: str  # UUID as string for compatibility
    email: EmailStr
    full_name: str | None = None  # Full name of the user
    role: UserRole
    
    class Config:
        from_attributes = True
