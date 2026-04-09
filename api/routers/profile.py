from fastapi import APIRouter, Request, Depends
from ..dependencies import templates, get_db
from ..auth import get_current_user
from ..models.user import User
from ..services import user_service

router = APIRouter()


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

    default_amount = form.get("default_contribution_amount", "").strip()
    if default_amount:
        try:
            update_data["default_contribution_amount"] = float(default_amount)
        except ValueError:
            pass
    else:
        update_data["default_contribution_amount"] = None

    updated_user = await user_service.update_user_profile(db, user.id, update_data)

    return templates.TemplateResponse(request, "profile.html", {
        "user": updated_user,
        "is_admin": updated_user.role == "admin",
        "success": True,
    })
