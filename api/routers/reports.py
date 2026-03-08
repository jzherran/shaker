from fastapi import APIRouter, Request, Depends, HTTPException
from datetime import date
from ..dependencies import templates, get_db
from ..auth import get_current_user, require_admin
from ..models.user import User
from ..services import report_service, account_service

router = APIRouter()


@router.get("/reports/balance")
async def balance_report_page(
    request: Request, user: User = Depends(get_current_user)
):
    db = get_db()
    accounts = []
    if user.role == "admin":
        accounts = await account_service.get_all_accounts(db)
    else:
        account = await account_service.get_account_by_user(db, user.id)
        if account:
            accounts = [account]

    return templates.TemplateResponse("reports/balance.html", {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin",
        "accounts": accounts,
    })


@router.get("/reports/fund")
async def fund_report_page(
    request: Request, user: User = Depends(get_current_user)
):
    db = get_db()
    fund = await report_service.get_fund_summary(db)
    return templates.TemplateResponse("reports/fund.html", {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin",
        "fund": fund,
    })


@router.get("/api/reports/balance")
async def get_balance_data(
    account_id: str,
    snapshot_type: str = "monthly",
    date_from: str = None,
    date_to: str = None,
    user: User = Depends(get_current_user),
):
    db = get_db()

    # Non-admin can only query their own account
    if user.role != "admin":
        account = await account_service.get_account_by_user(db, user.id)
        if not account or account.id != account_id:
            raise HTTPException(status_code=403, detail="Access denied")

    from_date = date.fromisoformat(date_from) if date_from else None
    to_date = date.fromisoformat(date_to) if date_to else None

    snapshots = await report_service.get_balance_snapshots(
        db, account_id, snapshot_type, from_date, to_date
    )
    return [s.model_dump() for s in snapshots]


@router.get("/api/reports/fund-summary")
async def get_fund_summary(user: User = Depends(get_current_user)):
    db = get_db()
    fund = await report_service.get_fund_summary(db)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund summary not found")
    return fund.model_dump()


@router.post("/api/admin/snapshots/generate")
async def trigger_snapshot(admin: User = Depends(require_admin)):
    db = get_db()
    count = await report_service.generate_daily_snapshot(db, date.today())
    await report_service.update_fund_summary(db)
    return {"generated": count, "date": date.today().isoformat()}
