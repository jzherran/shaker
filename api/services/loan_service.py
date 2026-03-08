from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from supabase import Client
from ..models.loan import (
    Loan, LoanCreate, LoanGuarantor, LoanGuarantorCreate,
    LoanPayment, LoanPaymentCreate,
)
from typing import Optional


async def validate_loan_request(
    db: Client, data: LoanCreate
) -> tuple[bool, str]:
    """Validate a loan request based on backing type."""
    # Check account is active
    account = db.table("accounts").select("*").eq("id", data.account_id).execute()
    if not account.data:
        return False, "Account not found"
    account = account.data[0]
    if account["status"] != "active":
        return False, "Account is not active"

    # Check for defaulted loans
    defaulted = db.table("loans").select("id").eq(
        "account_id", data.account_id
    ).eq("status", "defaulted").execute()
    if defaulted.data:
        return False, "Account has defaulted loans"

    if data.backing_type == "individual":
        if account["balance"] < data.amount_requested:
            return False, (
                f"Insufficient balance. Available: {account['balance']:.2f}"
            )

    elif data.backing_type == "collective":
        fund = db.table("fund_summary").select("*").eq("id", 1).execute()
        if not fund.data:
            return False, "Fund summary not found"
        fund = fund.data[0]
        available = float(fund["available_for_lending"])
        max_collective = available * 0.20

        if data.amount_requested > available:
            return False, "Insufficient collective fund balance"
        if data.amount_requested > max_collective:
            return False, (
                f"Exceeds 20% cap. Max: {max_collective:.2f}"
            )

    elif data.backing_type == "group":
        pass  # Group validation happens after guarantors are added

    else:
        return False, f"Invalid backing type: {data.backing_type}"

    return True, "Loan request is valid"


async def get_available_balance(db: Client, account_id: str) -> float:
    """Get balance minus amounts committed as guarantor on active loans."""
    account = db.table("accounts").select("balance").eq("id", account_id).execute()
    if not account.data:
        return 0.0

    balance = float(account.data[0]["balance"])

    # Sum committed guarantor amounts on active/approved loans
    guarantees = db.table("loan_guarantors").select(
        "guaranteed_amount, loan_id"
    ).eq("guarantor_account_id", account_id).eq("status", "accepted").execute()

    committed = 0.0
    for g in guarantees.data:
        loan = db.table("loans").select("status").eq("id", g["loan_id"]).execute()
        if loan.data and loan.data[0]["status"] in ("approved", "active"):
            committed += float(g["guaranteed_amount"])

    return balance - committed


async def validate_group_backing(
    db: Client, loan_id: str
) -> tuple[bool, str]:
    """Validate that group guarantors fully cover the loan."""
    loan = db.table("loans").select("*").eq("id", loan_id).execute()
    if not loan.data:
        return False, "Loan not found"
    loan = loan.data[0]

    guarantors = db.table("loan_guarantors").select("*").eq(
        "loan_id", loan_id
    ).execute()

    if not guarantors.data:
        return False, "No guarantors assigned"

    # Check all accepted
    pending = [g for g in guarantors.data if g["status"] == "pending"]
    rejected = [g for g in guarantors.data if g["status"] == "rejected"]
    if rejected:
        return False, "One or more guarantors rejected"
    if pending:
        return False, "Waiting for guarantor responses"

    # Check total coverage
    total = sum(float(g["guaranteed_amount"]) for g in guarantors.data)
    if total < float(loan["amount_requested"]):
        return False, (
            f"Guarantor coverage insufficient. "
            f"Need: {loan['amount_requested']}, Have: {total:.2f}"
        )

    # Check each guarantor's available balance
    for g in guarantors.data:
        available = await get_available_balance(db, g["guarantor_account_id"])
        if available < float(g["guaranteed_amount"]):
            return False, (
                f"Guarantor {g['guarantor_account_id']} has insufficient "
                f"available balance ({available:.2f})"
            )

    return True, "Group backing is valid"


async def create_loan(db: Client, data: LoanCreate) -> Loan:
    result = db.table("loans").insert({
        "account_id": data.account_id,
        "amount_requested": data.amount_requested,
        "interest_rate": data.interest_rate,
        "term_months": data.term_months,
        "backing_type": data.backing_type,
        "purpose": data.purpose,
    }).execute()
    return Loan(**result.data[0])


async def approve_loan(
    db: Client, loan_id: str, approved_by: str, amount: Optional[float] = None
) -> Loan:
    loan = db.table("loans").select("*").eq("id", loan_id).execute()
    if not loan.data or loan.data[0]["status"] != "requested":
        raise ValueError("Loan not found or not in requested status")

    loan_data = loan.data[0]
    approved_amount = amount or float(loan_data["amount_requested"])
    due = date.today() + relativedelta(months=int(loan_data["term_months"]))

    result = db.table("loans").update({
        "status": "approved",
        "amount_approved": approved_amount,
        "approved_by": approved_by,
        "approved_at": "now()",
        "due_date": due.isoformat(),
        "updated_at": "now()",
    }).eq("id", loan_id).execute()
    return Loan(**result.data[0])


async def reject_loan(db: Client, loan_id: str, reason: str) -> Loan:
    result = db.table("loans").update({
        "status": "rejected",
        "rejection_reason": reason,
        "updated_at": "now()",
    }).eq("id", loan_id).execute()
    return Loan(**result.data[0])


async def disburse_loan(db: Client, loan_id: str) -> None:
    db.rpc("disburse_loan", {
        "p_loan_id": loan_id,
        "p_amount": 0,  # amount tracked in loan record
    }).execute()


async def record_payment(db: Client, data: LoanPaymentCreate) -> LoanPayment:
    result_data = db.rpc("record_loan_payment", {
        "p_loan_id": data.loan_id,
        "p_amount": data.amount,
        "p_principal": data.principal_amount,
        "p_interest": data.interest_amount,
        "p_payment_number": data.payment_number,
        "p_receipt_reference": data.receipt_reference or "",
    }).execute()

    payment_id = result_data.data
    row = db.table("loan_payments").select("*").eq("id", payment_id).execute()
    return LoanPayment(**row.data[0])


async def get_loan(db: Client, loan_id: str) -> Optional[Loan]:
    result = db.table("loans").select("*").eq("id", loan_id).execute()
    if not result.data:
        return None
    return Loan(**result.data[0])


async def get_loans(
    db: Client,
    account_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Loan]:
    query = db.table("loans").select("*")
    if account_id:
        query = query.eq("account_id", account_id)
    if status:
        query = query.eq("status", status)
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return [Loan(**row) for row in result.data]


async def add_guarantor(db: Client, data: LoanGuarantorCreate) -> LoanGuarantor:
    result = db.table("loan_guarantors").insert({
        "loan_id": data.loan_id,
        "guarantor_account_id": data.guarantor_account_id,
        "guaranteed_amount": data.guaranteed_amount,
    }).execute()
    return LoanGuarantor(**result.data[0])


async def respond_guarantor(
    db: Client, guarantor_id: str, accept: bool
) -> LoanGuarantor:
    status = "accepted" if accept else "rejected"
    result = db.table("loan_guarantors").update({
        "status": status,
        "responded_at": "now()",
    }).eq("id", guarantor_id).execute()
    return LoanGuarantor(**result.data[0])


def calculate_amortization_schedule(
    principal: float, annual_rate: float, term_months: int
) -> list[dict]:
    """Calculate French amortization schedule."""
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        payment = principal / term_months
    else:
        payment = principal * (
            monthly_rate * (1 + monthly_rate) ** term_months
        ) / ((1 + monthly_rate) ** term_months - 1)

    schedule = []
    remaining = principal
    for i in range(1, term_months + 1):
        interest = remaining * monthly_rate
        principal_part = payment - interest
        remaining -= principal_part
        schedule.append({
            "payment_number": i,
            "payment": round(payment, 2),
            "principal": round(principal_part, 2),
            "interest": round(interest, 2),
            "remaining": round(max(remaining, 0), 2),
        })
    return schedule
