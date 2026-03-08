from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from ..dependencies import templates, get_db
from ..auth import get_current_user, require_admin
from ..models.user import User
from ..models.contribution import ContributionCreate
from ..services import contribution_service, account_service

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

    return templates.TemplateResponse("contributions/list.html", {
        "request": request,
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
    request: Request, admin: User = Depends(require_admin)
):
    db = get_db()
    accounts = await account_service.get_all_accounts(db)
    return templates.TemplateResponse("contributions/form.html", {
        "request": request,
        "user": admin,
        "is_admin": True,
        "accounts": accounts,
    })


@router.post("/api/contributions")
async def create_contribution(
    data: ContributionCreate, admin: User = Depends(require_admin)
):
    db = get_db()
    contribution = await contribution_service.record_contribution(
        db, data, created_by=admin.id
    )
    return contribution.model_dump()


@router.post("/api/contributions/htmx")
async def create_contribution_htmx(
    request: Request, admin: User = Depends(require_admin)
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
    contribution = await contribution_service.record_contribution(
        db, data, created_by=admin.id
    )
    return templates.TemplateResponse("contributions/_row.html", {
        "request": request,
        "c": contribution,
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
