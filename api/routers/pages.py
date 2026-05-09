from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from ..auth import (
    create_session_token,
    get_current_user,
    get_current_user_or_none,
)
from ..config import get_settings
from ..dependencies import admin_view_as_user, get_db, templates
from ..i18n import locale_from_request, translate, translate_html
from ..models.user import User
from ..services import account_service, loan_service, report_service, user_service

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
    lang = locale_from_request(request)
    login_js = {
        "err_url": translate(lang, "login.js.err_url"),
        "err_key": translate(lang, "login.js.err_key"),
        "err_client": translate(lang, "login.js.err_client"),
        "err_init": translate(lang, "login.js.err_init"),
        "err_oauth": translate(lang, "login.js.err_oauth"),
        "err_unexpected": translate(lang, "login.js.err_unexpected"),
    }

    mock_users: list[dict] = []
    if settings.app_env == "development":
        db = get_db()
        result = (
            db.table("users")
            .select("email, full_name, role")
            .like("email", "%@fonafahe.dev")
            .eq("is_active", True)
            .order("role")
            .order("full_name")
            .execute()
        )
        mock_users = result.data or []

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "supabase_url": settings.supabase_url,
            "supabase_key": settings.supabase_key,
            "app_env": settings.app_env,
            "login_js": login_js,
            "mock_users": mock_users,
        },
    )


@router.get("/set-language")
async def set_language(
    request: Request,
    lang: str = Query("en"),
    next_path: str | None = Query(None, alias="next"),
):
    if lang not in ("en", "es"):
        lang = "en"
    dest = "/"
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        dest = next_path
    response = RedirectResponse(url=dest, status_code=302)
    response.set_cookie(
        "lang",
        lang,
        max_age=365 * 24 * 3600,
        path="/",
        samesite="lax",
        httponly=False,
    )
    return response


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle Supabase OAuth callback. The frontend JS sends us the session."""
    return templates.TemplateResponse(request, "auth_callback.html")


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
        # Check if this auth_id is a merged alias
        alias_check = (
            db.table("user_auth_aliases").select("user_id").eq("auth_id", auth_id).execute()
        )
        if not alias_check.data:
            # Truly new user — create with pending approval, no account yet
            db.table("users").insert(
                {
                    "auth_id": auth_id,
                    "email": email,
                    "full_name": full_name,
                    "approval_status": "pending",
                }
            ).execute()

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


@router.post("/auth/mock-login")
async def mock_login(request: Request):
    """Development-only login: issue a session cookie for a mock user by email.

    Strictly disabled outside of the development environment.
    """
    settings = get_settings()
    if settings.app_env != "development":
        raise HTTPException(status_code=403, detail="Mock login is disabled")

    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    db = get_db()
    result = (
        db.table("users")
        .select("auth_id, email, is_active")
        .eq("email", email)
        .eq("is_active", True)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Mock user not found")

    auth_id = result.data[0]["auth_id"]
    user_email = result.data[0]["email"]

    token = create_session_token(auth_id, user_email)
    response = Response(content='{"ok": true}', media_type="application/json")
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@router.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


@router.get("/enrollment")
async def enrollment_page(request: Request, user: User = Depends(get_current_user)):
    if user.national_id and user.approval_status == "approved":
        return RedirectResponse(url="/dashboard", status_code=302)
    if user.national_id and user.approval_status != "approved":
        return RedirectResponse(url="/pending-approval", status_code=302)

    db = get_db()
    merge_status = await user_service.get_user_merge_status(db, user.id)

    return templates.TemplateResponse(
        request,
        "enrollment.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
            "merge_pending": merge_status == "pending",
        },
    )


@router.post("/enrollment")
async def enrollment_submit(request: Request, user: User = Depends(get_current_user)):
    form = await request.form()
    national_id = form.get("national_id", "").strip()

    if not national_id or len(national_id) < 5:
        return templates.TemplateResponse(
            request,
            "enrollment.html",
            {
                "user": user,
                "is_admin": user.role == "admin",
                "error": translate_html(request, "enrollment.error_short"),
            },
        )

    db = get_db()
    enroll_status, merge_request = await user_service.enroll_national_id(db, user.id, national_id)

    if enroll_status == "enrolled":
        if user.approval_status != "approved":
            return RedirectResponse(url="/pending-approval", status_code=302)
        return RedirectResponse(url="/dashboard", status_code=302)

    # merge_requested or already_pending
    return templates.TemplateResponse(
        request,
        "enrollment.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
            "merge_pending": True,
        },
    )


@router.get("/pending-approval")
async def pending_approval_page(request: Request, user: User = Depends(get_current_user)):
    if user.approval_status == "approved":
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(
        request,
        "pending_approval.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
        },
    )


@router.get("/dashboard")
async def dashboard(request: Request, user: User = Depends(get_current_user)):
    if not user.national_id:
        return RedirectResponse(url="/enrollment", status_code=302)
    if user.approval_status != "approved":
        return RedirectResponse(url="/pending-approval", status_code=302)

    db = get_db()
    # Check if user has a pending merge (show info on dashboard)
    merge_pending = await user_service.get_user_merge_status(db, user.id) == "pending"
    account = await account_service.get_account_by_user(db, user.id)

    admin_member_ui = user.role == "admin" and admin_view_as_user(request)
    fund = await report_service.get_fund_summary(db)

    # Get recent contributions for this account
    recent_contributions = []
    balance_history: list[dict] = []
    if account:
        from ..services import contribution_service

        recent_contributions = await contribution_service.get_contributions(
            db, account_id=account.id, limit=5
        )
        balance_history = await report_service.get_account_balance_history(
            db, account.id, months=12
        )

    fund_history: list[dict] = []
    fund_per_account: dict = {"labels": [], "series": []}
    if user.role == "admin" and not admin_member_ui:
        fund_history = await report_service.get_fund_historical_balances(db, months=12)
        fund_per_account = await report_service.get_fund_per_account_history(db, months=12)

    loan_repayment_summary: dict | None = None
    if account and (user.role != "admin" or admin_member_ui):
        loan_repayment_summary = await loan_service.summarize_active_loan_repayments(
            db, account.id
        )

    dashboard_show_fund_metrics = bool(
        user.role == "admin" and fund and not admin_member_ui
    )
    dashboard_metric_count = (
        (1 if account else 0)
        + (2 if dashboard_show_fund_metrics else 0)
        + (1 if loan_repayment_summary is not None else 0)
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "is_admin": user.role == "admin",
            "account": account,
            "fund": fund,
            "recent_contributions": recent_contributions,
            "merge_pending": merge_pending,
            "balance_history": balance_history,
            "fund_history": fund_history,
            "fund_per_account": fund_per_account,
            "loan_repayment_summary": loan_repayment_summary,
            "dashboard_show_fund_metrics": dashboard_show_fund_metrics,
            "dashboard_metric_count": dashboard_metric_count,
        },
    )
