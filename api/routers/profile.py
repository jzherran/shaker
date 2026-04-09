import re

from fastapi import APIRouter, Request, Depends
from ..dependencies import templates, get_db
from ..auth import get_current_user
from ..models.user import User
from ..services import user_service

router = APIRouter()


def _parse_default_amount(raw: str) -> float | None:
    """Parse default contribution: plain float string or COP-style (e.g. $ 200.000,50)."""
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    # Strip currency / spaces / COP
    t = re.sub(r"[^\d.,-]", "", s.replace("\u00a0", " "))
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    else:
        parts = t.split(".")
        if len(parts) > 2:
            t = "".join(parts[:-1]) + "." + parts[-1]
        elif len(parts) == 2 and len(parts[1]) <= 2:
            t = parts[0] + "." + parts[1]
        else:
            t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


@router.get("/profile")
async def profile_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "profile.html", {
        "user": user,
        "is_admin": user.role == "admin",
    })


@router.post("/api/profile/htmx")
async def update_profile_htmx(request: Request, user: User = Depends(get_current_user)):
    form = await request.form()
    db = get_db()

    update_data = {}
    full_name = form.get("full_name", "").strip()
    if full_name:
        update_data["full_name"] = full_name

    phone = form.get("phone", "").strip()
    update_data["phone"] = phone if phone else None

    default_amount_raw = form.get("default_contribution_amount", "")
    raw_str = default_amount_raw.strip() if isinstance(default_amount_raw, str) else ""
    if not raw_str:
        update_data["default_contribution_amount"] = None
    else:
        parsed = _parse_default_amount(raw_str)
        if parsed is not None and parsed > 0:
            update_data["default_contribution_amount"] = parsed
        # invalid or non-positive: omit so existing DB value is preserved (same as failed float() before)

    updated_user = await user_service.update_user_profile(db, user.id, update_data)

    # Fragment only — full profile.html extends base.html and would duplicate nav/layout in the DOM
    return templates.TemplateResponse(
        request,
        "partials/profile_page_inner.html",
        {
            "user": updated_user,
            "is_admin": updated_user.role == "admin",
            "success": True,
        },
    )
