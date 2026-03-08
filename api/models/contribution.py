from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ContributionCreate(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0)
    contribution_type: str = "regular"
    period_year: int
    period_month: int = Field(..., ge=1, le=12)
    description: Optional[str] = None
    receipt_reference: Optional[str] = None


class Contribution(BaseModel):
    id: str
    account_id: str
    amount: float
    contribution_type: str
    period_year: int
    period_month: int
    description: Optional[str] = None
    receipt_reference: Optional[str] = None
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
