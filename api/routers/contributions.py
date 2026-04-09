from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from ..dependencies import templates, get_db
from ..auth import get_current_user, require_admin
from ..models.user import User
from ..models.contribution import ContributionCreate, BatchContributionCreate, BatchContributionItem
from ..services import contribution_service, account_service, user_service
import json

router = APIRouter()


@router.get("/contributions")
async def contributions_list(
    request: Request,
    user: User = Depends(get_current_user),
    account_id: str = None,
    year: int = None,
    month: int = None,
):
    db = get_db()

    # Non-admin can only see their own
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        account_id = account.id if account else None

    contributions = await contribution_service.get_contributions(
        db, account_id=account_id, year=year, month=month
    )

    # Get accounts list for the filter dropdown (admin only)
    accounts = []
    if user.role == "admin":
        accounts = await account_service.get_all_accounts(db)

    return templates.TemplateResponse(request, "contributions/list.html", {
        "user": user,
        "is_admin": user.role == "admin",
        "contributions": contributions,
        "accounts": accounts,
        "filter_account_id": account_id,
        "filter_year": year,
        "filter_month": month,
    })


@router.get("/contributions/new")
async def contribution_form(
    request: Request, user: User = Depends(get_current_user)
):
    db = get_db()

    if user.role == "admin":
        accounts = await account_service.get_all_accounts(db)
        return templates.TemplateResponse(request, "contributions/form.html", {
            "user": user,
            "is_admin": True,
            "accounts": accounts,
        })
    else:
        account = await account_service.get_account_by_user(db, user.id)
        return templates.TemplateResponse(request, "contributions/form.html", {
            "user": user,
            "is_admin": False,
            "account": account,
            "default_amount": user.default_contribution_amount,
        })


@router.get("/contributions/batch")
async def batch_contribution_form(
    request: Request, admin: User = Depends(require_admin)
):
    db = get_db()
    users_accounts = await user_service.get_active_users_with_accounts(db)
    return templates.TemplateResponse(request, "contributions/batch_form.html", {
        "user": admin,
        "is_admin": True,
        "users_accounts": users_accounts,
    })


@router.post("/api/contributions")
async def create_contribution(
    data: ContributionCreate, user: User = Depends(get_current_user)
):
    db = get_db()

    # Non-admin can only create for their own account
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        if not account or account.id != data.account_id:
            raise HTTPException(status_code=403, detail="Can only contribute to your own account")

    contribution = await contribution_service.record_contribution(
        db, data, created_by=user.id
    )
    return contribution.model_dump()


@router.post("/api/contributions/htmx")
async def create_contribution_htmx(
    request: Request, user: User = Depends(get_current_user)
):
    """HTMX endpoint: returns an HTML row partial."""
    form = await request.form()
    data = ContributionCreate(
        account_id=form["account_id"],
        amount=float(form["amount"]),
        contribution_type=form.get("contribution_type", "regular"),
        period_year=int(form["period_year"]),
        period_month=int(form["period_month"]),
        description=form.get("description", ""),
        receipt_reference=form.get("receipt_reference"),
    )

    db = get_db()

    # Non-admin can only create for their own account
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        if not account or account.id != data.account_id:
            raise HTTPException(status_code=403, detail="Can only contribute to your own account")

    contribution = await contribution_service.record_contribution(
        db, data, created_by=user.id
    )
    return templates.TemplateResponse(request, "contributions/_row.html", {
        "c": contribution,
    })


@router.post("/api/contributions/batch/htmx")
async def create_batch_contributions_htmx(
    request: Request, admin: User = Depends(require_admin)
):
    """HTMX endpoint: batch create contributions for selected accounts."""
    form = await request.form()

    contribution_type = form.get("contribution_type", "regular")
    period_year = int(form["period_year"])
    period_month = int(form["period_month"])
    description = form.get("description", "")

    # Collect selected accounts and their amounts
    selected_accounts = form.getlist("selected_accounts")
    items = []
    for account_id in selected_accounts:
        amount_key = f"amount_{account_id}"
        amount = float(form.get(amount_key, 0))
        if amount > 0:
            items.append(BatchContributionItem(account_id=account_id, amount=amount))

    if not items:
        return HTMLResponse(
            '<div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">'
            'No accounts selected or all amounts are zero.</div>'
        )

    batch_data = BatchContributionCreate(
        items=items,
        contribution_type=contribution_type,
        period_year=period_year,
        period_month=period_month,
        description=description,
    )

    db = get_db()
    contributions = await contribution_service.record_contributions_batch(
        db, batch_data, created_by=admin.id
    )

    total = sum(c.amount for c in contributions)
    return templates.TemplateResponse(request, "contributions/_batch_result.html", {
        "count": len(contributions),
        "total": total,
        "contributions": contributions,
    })


@router.delete("/api/contributions/{contribution_id}")
async def cancel_contribution(
    contribution_id: str, admin: User = Depends(require_admin)
):
    db = get_db()
    existing = await contribution_service.get_contribution(db, contribution_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Contribution not found")
    await contribution_service.cancel_contribution(db, contribution_id)
    return {"ok": True}
