from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import require_admin
from ..auth import require_approved_user as get_current_user
from ..dependencies import get_db, templates
from ..models.loan import LoanCreate, LoanGuarantorCreate, LoanPaymentCreate
from ..models.user import User
from ..services import account_service, loan_service

router = APIRouter()


@router.get("/api/members/search")
async def search_members(
    q: str = Query("", min_length=0),
    exclude_account: str = Query(None),
    user: User = Depends(get_current_user),
):
    """Search active members for guarantor picker. Returns account_id, name, available balance."""
    db = get_db()
    query = (
        db.table("accounts")
        .select("id, account_number, balance, user_id, users(full_name, is_active)")
        .eq("status", "active")
        .order("account_number")
    )
    result = query.execute()

    members = []
    q_lower = q.lower()
    for row in result.data:
        if exclude_account and row["id"] == exclude_account:
            continue
        user_data = row.get("users") or {}
        if not user_data.get("is_active", True):
            continue
        name = user_data.get("full_name", "")
        if q_lower and q_lower not in name.lower() and q_lower not in row["account_number"].lower():
            continue
        available = await loan_service.get_available_balance(db, row["id"])
        members.append(
            {
                "account_id": row["id"],
                "account_number": row["account_number"],
                "full_name": name,
                "balance": row["balance"],
                "available_balance": round(available, 2),
            }
        )
    return members


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

    return templates.TemplateResponse(
        request,
        "loans/list.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
            "loans": loans,
            "filter_status": status,
        },
    )


@router.get("/loans/request")
async def loan_request_form(request: Request, user: User = Depends(get_current_user)):
    db = get_db()
    account = await account_service.get_account_by_user(db, user.id)
    accounts = []
    available_balance = 0.0
    if user.role == "admin":
        accounts = await account_service.get_all_accounts(db, status="active", active_owner=True)
    if account:
        available_balance = await loan_service.get_available_balance(db, account.id)

    return templates.TemplateResponse(
        request,
        "loans/request.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
            "account": account,
            "accounts": accounts,
            "available_balance": round(available_balance, 2),
        },
    )


@router.get("/loans/{loan_id}")
async def loan_detail(request: Request, loan_id: str, user: User = Depends(get_current_user)):
    db = get_db()
    loan = await loan_service.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    is_owner = False
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        if not account or loan.account_id != account.id:
            raise HTTPException(status_code=403, detail="Access denied")
        is_owner = True
    else:
        owner_account = db.table("accounts").select("user_id").eq("id", loan.account_id).execute()
        if owner_account.data and owner_account.data[0]["user_id"] == user.id:
            is_owner = True

    schedule = []
    if loan.amount_approved:
        schedule = loan_service.calculate_amortization_schedule(
            loan.amount_approved, loan.interest_rate, loan.term_months
        )

    payments_result = (
        db.table("loan_payments")
        .select("*")
        .eq("loan_id", loan_id)
        .order("payment_number")
        .execute()
    )

    guarantors = (
        db.table("loan_guarantors")
        .select("*, accounts(account_number, users(full_name))")
        .eq("loan_id", loan_id)
        .execute()
    )

    # Suggest next installment number based on existing non-cancelled payments
    used_numbers = {
        int(p["payment_number"]) for p in payments_result.data if p.get("status") != "cancelled"
    }
    next_payment_number = 1
    while next_payment_number in used_numbers:
        next_payment_number += 1

    return templates.TemplateResponse(
        request,
        "loans/detail.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
            "is_owner": is_owner,
            "loan": loan,
            "schedule": schedule,
            "payments": payments_result.data,
            "guarantors": guarantors.data,
            "next_payment_number": next_payment_number,
        },
    )


@router.post("/api/loans")
async def create_loan(data: LoanCreate, user: User = Depends(get_current_user)):
    db = get_db()

    # If not admin, can only request for own account
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        if not account or data.account_id != account.id:
            raise HTTPException(
                status_code=403,
                detail="Can only request loans for your own account",
            )

    try:
        await account_service.require_active_account(db, data.account_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    valid, msg = await loan_service.validate_loan_request(db, data)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    loan = await loan_service.create_loan(db, data)
    return loan.model_dump()


@router.post("/api/loans/{loan_id}/approve")
async def approve_loan(loan_id: str, request: Request, admin: User = Depends(require_admin)):
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
async def reject_loan(loan_id: str, request: Request, admin: User = Depends(require_admin)):
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
    loan_id: str, data: LoanPaymentCreate, user: User = Depends(get_current_user)
):
    """Submit a loan payment. Anyone (admin or borrower) can submit; admins approve later."""
    db = get_db()
    if data.loan_id != loan_id:
        raise HTTPException(status_code=400, detail="Loan ID mismatch")

    loan = await loan_service.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        if not account or loan.account_id != account.id:
            raise HTTPException(
                status_code=403, detail="Can only submit payments for your own loans"
            )

    if loan.status not in ("active", "approved"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit payment for loan in status '{loan.status}'",
        )

    payment = await loan_service.record_payment(db, data, submitted_by=user.id)
    return payment.model_dump()


@router.get("/admin/payments")
async def admin_pending_payments(request: Request, admin: User = Depends(require_admin)):
    """Admin view listing all pending loan payments awaiting approval."""
    db = get_db()
    pending = await loan_service.get_pending_payments(db)
    return templates.TemplateResponse(
        request,
        "admin/payments.html",
        {
            "user": admin,
            "is_admin": True,
            "pending_payments": pending,
        },
    )


@router.post("/api/loans/payments/{payment_id}/approve")
async def approve_payment(payment_id: str, admin: User = Depends(require_admin)):
    db = get_db()
    try:
        payment = await loan_service.approve_payment(db, payment_id, admin.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return payment.model_dump()


@router.post("/api/loans/payments/{payment_id}/reject")
async def reject_payment(payment_id: str, admin: User = Depends(require_admin)):
    db = get_db()
    try:
        payment = await loan_service.reject_payment(db, payment_id, admin.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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
