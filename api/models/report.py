from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional


class BalanceSnapshot(BaseModel):
    id: str
    account_id: str
    snapshot_type: str
    snapshot_date: date
    balance: float
    total_contributions: float
    total_loan_disbursements: float
    total_loan_payments: float
    created_at: datetime


class FundSummary(BaseModel):
    total_balance: float
    total_members: int
    total_active_loans: float
    available_for_lending: float
    last_updated: datetime
