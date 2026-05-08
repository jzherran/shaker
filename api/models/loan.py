from datetime import date, datetime

from pydantic import BaseModel, Field


class GuarantorEntry(BaseModel):
    guarantor_account_id: str
    guaranteed_amount: float = Field(..., gt=0)


class LoanCreate(BaseModel):
    account_id: str
    amount_requested: float = Field(..., gt=0)
    interest_rate: float = 0.02
    term_months: int = Field(..., gt=0)
    backing_type: str  # individual, group, collective
    purpose: str | None = None
    guarantors: list[GuarantorEntry] = []


class Loan(BaseModel):
    id: str
    account_id: str
    amount_requested: float
    amount_approved: float | None = None
    interest_rate: float
    term_months: int
    backing_type: str
    status: str
    purpose: str | None = None
    rejection_reason: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    disbursed_at: datetime | None = None
    due_date: date | None = None
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
    responded_at: datetime | None = None
    created_at: datetime


class LoanPaymentCreate(BaseModel):
    loan_id: str
    amount: float = Field(..., gt=0)
    principal_amount: float = 0
    interest_amount: float = 0
    payment_number: int
    receipt_reference: str | None = None
    notes: str | None = None


class LoanPayment(BaseModel):
    id: str
    loan_id: str
    amount: float
    principal_amount: float
    interest_amount: float
    payment_number: int
    receipt_reference: str | None = None
    notes: str | None = None
    status: str
    submitted_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
