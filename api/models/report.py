from datetime import date, datetime

from pydantic import BaseModel


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


class GenerateSnapshotsRequest(BaseModel):
    """Body for POST /api/admin/snapshots/generate.

    - `account_ids` omitted/None ⇒ snapshot every active account (legacy behavior).
    - `snapshot_date` omitted/None ⇒ today.
    - `snapshot_type` ∈ {"daily", "monthly", "yearly"}; defaults to "daily".
      Monthly/yearly normalize the date to the end of the period server-side.
    """

    account_ids: list[str] | None = None
    snapshot_date: date | None = None
    snapshot_type: str = "daily"
