from fastapi import APIRouter, Request, Depends, HTTPException
from ..dependencies import templates, get_db
from ..auth import get_current_user, require_admin
from ..models.user import User
from ..models.loan import LoanCreate, LoanGuarantorCreate, LoanPaymentCreate
from ..services import loan_service, account_service

router = APIRouter()


@router.get("/loans")
async def loans_list(
    request: Request,
    user: User = Depends(get_current_user),
    status: str = None,
):
    db = get_db()
    account_id = None
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        account_id = account.id if account else None

    loans = await loan_service.get_loans(db, account_id=account_id, status=status)

    return templates.TemplateResponse("loans/list.html", {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin",
        "loans": loans,
        "filter_status": status,
    })


@router.get("/loans/request")
async def loan_request_form(
    request: Request, user: User = Depends(get_current_user)
):
    db = get_db()
    account = await account_service.get_account_by_user(db, user.id)
    accounts = []
    if user.role == "admin":
        accounts = await account_service.get_all_accounts(db)

    return templates.TemplateResponse("loans/request.html", {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin",
        "account": account,
        "accounts": accounts,
    })


@router.get("/loans/{loan_id}")
async def loan_detail(
    request: Request, loan_id: str, user: User = Depends(get_current_user)
):
    db = get_db()
    loan = await loan_service.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    # Non-admin can only view their own loans
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        if not account or loan.account_id != account.id:
            raise HTTPException(status_code=403, detail="Access denied")

    # Get amortization schedule
    schedule = []
    if loan.amount_approved:
        schedule = loan_service.calculate_amortization_schedule(
            loan.amount_approved, loan.interest_rate, loan.term_months
        )

    # Get payments
    payments_result = db.table("loan_payments").select("*").eq(
        "loan_id", loan_id
    ).order("payment_number").execute()

    # Get guarantors with user names
    guarantors = db.table("loan_guarantors").select(
        "*, accounts(account_number, users(full_name))"
    ).eq("loan_id", loan_id).execute()

    return templates.TemplateResponse("loans/detail.html", {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin",
        "loan": loan,
        "schedule": schedule,
        "payments": payments_result.data,
        "guarantors": guarantors.data,
    })


@router.post("/api/loans")
async def create_loan(data: LoanCreate, user: User = Depends(get_current_user)):
    db = get_db()

    # If not admin, can only request for own account
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        if not account or data.account_id != account.id:
            raise HTTPException(status_code=403, detail="Can only request loans for your own account")

    valid, msg = await loan_service.validate_loan_request(db, data)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    loan = await loan_service.create_loan(db, data)
    return loan.model_dump()


@router.post("/api/loans/{loan_id}/approve")
async def approve_loan(
    loan_id: str, request: Request, admin: User = Depends(require_admin)
):
    db = get_db()
    loan = await loan_service.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    # Validate group backing if applicable
    if loan.backing_type == "group":
        valid, msg = await loan_service.validate_group_backing(db, loan_id)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)

    body = await request.json()
    amount = body.get("amount")
    approved = await loan_service.approve_loan(db, loan_id, admin.id, amount)
    return approved.model_dump()


@router.post("/api/loans/{loan_id}/reject")
async def reject_loan(
    loan_id: str, request: Request, admin: User = Depends(require_admin)
):
    db = get_db()
    body = await request.json()
    reason = body.get("reason", "")
    loan = await loan_service.reject_loan(db, loan_id, reason)
    return loan.model_dump()


@router.post("/api/loans/{loan_id}/disburse")
async def disburse_loan(loan_id: str, admin: User = Depends(require_admin)):
    db = get_db()
    await loan_service.disburse_loan(db, loan_id)
    return {"ok": True}


@router.post("/api/loans/{loan_id}/payments")
async def record_payment(
    loan_id: str, data: LoanPaymentCreate, admin: User = Depends(require_admin)
):
    db = get_db()
    if data.loan_id != loan_id:
        raise HTTPException(status_code=400, detail="Loan ID mismatch")
    payment = await loan_service.record_payment(db, data)
    return payment.model_dump()


@router.get("/api/loans/{loan_id}/schedule")
async def get_schedule(loan_id: str, user: User = Depends(get_current_user)):
    db = get_db()
    loan = await loan_service.get_loan(db, loan_id)
    if not loan or not loan.amount_approved:
        raise HTTPException(status_code=404, detail="Loan not found or not approved")
    schedule = loan_service.calculate_amortization_schedule(
        loan.amount_approved, loan.interest_rate, loan.term_months
    )
    return schedule


@router.post("/api/loans/{loan_id}/guarantors")
async def add_guarantor(
    loan_id: str, data: LoanGuarantorCreate, user: User = Depends(get_current_user)
):
    db = get_db()
    if data.loan_id != loan_id:
        raise HTTPException(status_code=400, detail="Loan ID mismatch")
    guarantor = await loan_service.add_guarantor(db, data)
    return guarantor.model_dump()


@router.patch("/api/loans/{loan_id}/guarantors/{guarantor_id}")
async def respond_to_guarantor_request(
    loan_id: str,
    guarantor_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    db = get_db()
    body = await request.json()
    accept = body.get("accept", False)
    guarantor = await loan_service.respond_guarantor(db, guarantor_id, accept)
    return guarantor.model_dump()
