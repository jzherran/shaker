from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from ..auth import require_admin
from ..auth import require_approved_user as get_current_user
from ..dependencies import admin_view_as_user, get_db, templates
from ..models.report import GenerateSnapshotsRequest
from ..models.user import User
from ..services import account_service, report_service

router = APIRouter()


@router.get("/reports/balance")
async def balance_report_page(
    request: Request,
    account_id: str | None = Query(None),
    user: User = Depends(get_current_user),
):
    db = get_db()
    accounts = []
    balance_account_locked = False
    full_balance = user.role == "admin" and request.query_params.get("full") == "1"
    admin_member_ui = user.role == "admin" and admin_view_as_user(request) and not full_balance

    if account_id:
        account = await account_service.get_account(db, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if user.role != "admin" and account.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        accounts = [account]
        balance_account_locked = True
    elif admin_member_ui:
        account = await account_service.get_account_by_user(db, user.id)
        if account:
            accounts = [account]
    elif user.role == "admin":
        accounts = await account_service.get_all_accounts(db, status="active", active_owner=True)
    else:
        account = await account_service.get_account_by_user(db, user.id)
        if account:
            accounts = [account]

    effective_member_like = user.role != "admin" or admin_member_ui
    balance_scope_fixed = balance_account_locked or (effective_member_like and len(accounts) == 1)

    return templates.TemplateResponse(
        request,
        "reports/balance.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
            "accounts": accounts,
            "balance_account_locked": balance_account_locked,
            "balance_scope_fixed": balance_scope_fixed,
            "balance_full_report": full_balance,
            "balance_admin_member_ui": admin_member_ui,
        },
    )


@router.get("/reports/fund")
async def fund_report_page(request: Request, user: User = Depends(get_current_user)):
    db = get_db()
    fund = await report_service.get_fund_summary(db)
    accounts = []
    admin_member_ui = user.role == "admin" and admin_view_as_user(request)
    if user.role == "admin" and not admin_member_ui:
        accounts = await account_service.get_all_accounts(db, status="active", active_owner=True)
    return templates.TemplateResponse(
        request,
        "reports/fund.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
            "fund": fund,
            "accounts": accounts,
            "today_iso": date.today().isoformat(),
        },
    )


@router.get("/api/reports/balance")
async def get_balance_data(
    request: Request,
    account_id: str | None = None,
    account_ids: list[str] = Query(default=[]),
    snapshot_type: str = "monthly",
    date_from: str = None,
    date_to: str = None,
    user: User = Depends(get_current_user),
):
    """Return balance snapshots for one or more accounts.

    Either pass a single `account_id` (legacy) or a repeatable `account_ids`
    query param. The response includes a flat snapshot list and a per-account
    metadata map so the UI can label chart series and table rows.
    """
    db = get_db()

    requested = list(account_ids) if account_ids else ([account_id] if account_id else [])
    requested = [aid for aid in requested if aid]
    if not requested:
        raise HTTPException(status_code=400, detail="At least one account_id is required")

    full_balance = user.role == "admin" and request.query_params.get("full") == "1"
    admin_member_ui = user.role == "admin" and admin_view_as_user(request) and not full_balance
    if user.role != "admin" or admin_member_ui:
        account = await account_service.get_account_by_user(db, user.id)
        if not account or any(aid != account.id for aid in requested):
            raise HTTPException(status_code=403, detail="Access denied")

    from_date = date.fromisoformat(date_from) if date_from else None
    to_date = date.fromisoformat(date_to) if date_to else None

    snapshots = await report_service.get_balance_snapshots_for_accounts(
        db, requested, snapshot_type, from_date, to_date
    )
    accounts_meta = await report_service.get_accounts_meta(db, requested)

    return {
        "snapshots": [s.model_dump(mode="json") for s in snapshots],
        "accounts": accounts_meta,
        "snapshot_type": snapshot_type,
    }


@router.get("/api/reports/fund-summary")
async def get_fund_summary(user: User = Depends(get_current_user)):
    db = get_db()
    fund = await report_service.get_fund_summary(db)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund summary not found")
    return fund.model_dump()


@router.post("/api/admin/snapshots/generate")
async def trigger_snapshot(
    payload: GenerateSnapshotsRequest = Body(default_factory=GenerateSnapshotsRequest),
    admin: User = Depends(require_admin),
):
    """Generate snapshots for all active accounts or a selected subset.

    Body is optional; an empty `{}` keeps the legacy "all active accounts,
    daily" behavior. Pass `snapshot_type` to write `monthly` or `yearly`
    rows (the date is normalized to the end of the requested period).
    """
    db = get_db()
    snapshot_date = payload.snapshot_date or date.today()
    try:
        result = await report_service.generate_snapshots(
            db, snapshot_date, payload.snapshot_type, payload.account_ids
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await report_service.update_fund_summary(db)
    return {
        "generated": result["generated"],
        "skipped": result["skipped"],
        "requested": len(payload.account_ids) if payload.account_ids else None,
        "snapshot_type": result["snapshot_type"],
        "date": result["snapshot_date"],
    }
