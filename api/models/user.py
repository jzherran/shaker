from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    auth_id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    national_id: Optional[str] = None
    role: str = "member"


class User(BaseModel):
    id: str
    auth_id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    national_id: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
