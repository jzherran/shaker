from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional


class LoanCreate(BaseModel):
    account_id: str
    amount_requested: float = Field(..., gt=0)
    interest_rate: float = 0.02
    term_months: int = Field(..., gt=0)
    backing_type: str  # individual, group, collective
    purpose: Optional[str] = None


class Loan(BaseModel):
    id: str
    account_id: str
    amount_requested: float
    amount_approved: Optional[float] = None
    interest_rate: float
    term_months: int
    backing_type: str
    status: str
    purpose: Optional[str] = None
    rejection_reason: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    disbursed_at: Optional[datetime] = None
    due_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class LoanGuarantorCreate(BaseModel):
    loan_id: str
    guarantor_account_id: str
    guaranteed_amount: float = Field(..., gt=0)


class LoanGuarantor(BaseModel):
    id: str
    loan_id: str
    guarantor_account_id: str
    guaranteed_amount: float
    status: str
    responded_at: Optional[datetime] = None
    created_at: datetime


class LoanPaymentCreate(BaseModel):
    loan_id: str
    amount: float = Field(..., gt=0)
    principal_amount: float = 0
    interest_amount: float = 0
    payment_number: int
    receipt_reference: Optional[str] = None


class LoanPayment(BaseModel):
    id: str
    loan_id: str
    amount: float
    principal_amount: float
    interest_amount: float
    payment_number: int
    receipt_reference: Optional[str] = None
    status: str
    created_at: datetime
