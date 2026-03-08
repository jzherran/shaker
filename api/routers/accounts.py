from fastapi import APIRouter, Request, Depends, HTTPException
from ..dependencies import templates, get_db
from ..auth import get_current_user, require_admin
from ..models.user import User
from ..services import account_service

router = APIRouter()


@router.get("/accounts")
async def accounts_list(request: Request, user: User = Depends(get_current_user)):
    db = get_db()
    if user.role == "admin":
        accounts = await account_service.get_all_accounts(db)
    else:
        account = await account_service.get_account_by_user(db, user.id)
        accounts = [account] if account else []

    return templates.TemplateResponse("accounts/list.html", {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin",
        "accounts": accounts,
    })


@router.get("/accounts/{account_id}")
async def account_detail(
    request: Request,
    account_id: str,
    user: User = Depends(get_current_user),
):
    db = get_db()
    summary = await account_service.get_account_summary(db, account_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Account not found")

    # Non-admin can only view their own account
    if user.role != "admin" and summary.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return templates.TemplateResponse("accounts/detail.html", {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin",
        "account": summary,
    })


@router.post("/api/accounts")
async def create_account(request: Request, admin: User = Depends(require_admin)):
    db = get_db()
    body = await request.json()
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    account_number = await account_service.generate_account_number(db)
    account = await account_service.create_account(
        db,
        account_service.AccountCreate(user_id=user_id, account_number=account_number),
    )
    return account.model_dump()


@router.patch("/api/accounts/{account_id}")
async def update_account(
    account_id: str, request: Request, admin: User = Depends(require_admin)
):
    db = get_db()
    body = await request.json()
    status = body.get("status")
    if status not in ("active", "inactive", "suspended"):
        raise HTTPException(status_code=400, detail="Invalid status")

    account = await account_service.update_account_status(db, account_id, status)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account.model_dump()
