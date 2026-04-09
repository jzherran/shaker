from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    auth_id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    national_id: Optional[str] = None
    default_contribution_amount: Optional[float] = None
    role: str = "member"


class User(BaseModel):
    id: str
    auth_id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    national_id: Optional[str] = None
    default_contribution_amount: Optional[float] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserEnrollment(BaseModel):
    national_id: str = Field(..., min_length=5, max_length=30)


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    default_contribution_amount: Optional[float] = Field(None, gt=0)


class MergeRequest(BaseModel):
    id: str
    requesting_user_id: str
    target_user_id: str
    national_id: str
    status: str
    reviewed_by: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class MergeRequestDetail(MergeRequest):
    requesting_user_name: str = ""
    requesting_user_email: str = ""
    target_user_name: str = ""
    target_user_email: str = ""
