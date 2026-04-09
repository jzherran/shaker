from datetime import datetime

from pydantic import BaseModel, Field


class ContributionCreate(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0)
    contribution_type: str = "regular"
    period_year: int
    period_month: int = Field(..., ge=1, le=12)
    description: str | None = None
    receipt_reference: str | None = None


class Contribution(BaseModel):
    id: str
    account_id: str
    amount: float
    contribution_type: str
    period_year: int
    period_month: int
    description: str | None = None
    receipt_reference: str | None = None
    status: str
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class BatchContributionItem(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0)


class BatchContributionCreate(BaseModel):
    items: list[BatchContributionItem]
    contribution_type: str = "regular"
    period_year: int
    period_month: int = Field(..., ge=1, le=12)
    description: str | None = None
