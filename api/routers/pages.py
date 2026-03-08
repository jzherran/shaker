from fastapi import APIRouter, Request, Depends, Response, HTTPException
from fastapi.responses import RedirectResponse
from ..dependencies import templates, get_db
from ..auth import (
    get_current_user, get_current_user_or_none,
    require_admin, create_session_token,
)
from ..models.user import User
from ..config import get_settings
from ..services import account_service, report_service

router = APIRouter()


@router.get("/")
async def index(request: Request):
    user = await get_current_user_or_none(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/login")
async def login_page(request: Request):
    user = await get_current_user_or_none(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    settings = get_settings()
    return templates.TemplateResponse("login.html", {
        "request": request,
        "supabase_url": settings.supabase_url,
        "supabase_key": settings.supabase_key,
    })


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle Supabase OAuth callback. The frontend JS sends us the session."""
    return templates.TemplateResponse("auth_callback.html", {
        "request": request,
    })


@router.post("/auth/session")
async def set_session(request: Request):
    """Set session cookie from Supabase auth token. Called from JS after OAuth."""
    body = await request.json()
    auth_id = body.get("user_id")
    email = body.get("email")
    full_name = body.get("full_name", email.split("@")[0] if email else "User")

    if not auth_id or not email:
        raise HTTPException(status_code=400, detail="Missing user data")

    db = get_db()

    # Find or create user
    result = db.table("users").select("*").eq("auth_id", auth_id).execute()
    if not result.data:
        db.table("users").insert({
            "auth_id": auth_id,
            "email": email,
            "full_name": full_name,
        }).execute()

        # Create account for new user
        user_result = db.table("users").select("id").eq("auth_id", auth_id).execute()
        user_id = user_result.data[0]["id"]
        account_number = await account_service.generate_account_number(db)
        await account_service.create_account(db, account_service.AccountCreate(
            user_id=user_id,
            account_number=account_number,
        ))

    token = create_session_token(auth_id, email)
    response = Response(content='{"ok": true}', media_type="application/json")
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    return response


@router.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


@router.get("/dashboard")
async def dashboard(request: Request, user: User = Depends(get_current_user)):
    db = get_db()
    account = await account_service.get_account_by_user(db, user.id)

    fund = await report_service.get_fund_summary(db)

    # Get recent contributions for this account
    recent_contributions = []
    if account:
        from ..services import contribution_service
        recent_contributions = await contribution_service.get_contributions(
            db, account_id=account.id, limit=5
        )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "is_admin": user.role == "admin",
        "account": account,
        "fund": fund,
        "recent_contributions": recent_contributions,
    })
