from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AccountCreate(BaseModel):
    user_id: str
    account_number: str = Field(..., pattern=r"^FON-\d{4}$")


class Account(BaseModel):
    id: str
    user_id: str
    account_number: str
    balance: float
    status: str
    created_at: datetime
    updated_at: datetime


class AccountSummary(BaseModel):
    id: str
    user_id: str
    account_number: str
    balance: float
    status: str
    owner_name: str
    email: str
    total_contributions: float = 0
    total_loan_disbursements: float = 0
    active_loans_count: int = 0
    created_at: datetime
    last_contribution_at: Optional[datetime] = None
