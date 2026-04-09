from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from ..dependencies import templates, get_db
from ..auth import require_admin
from ..models.user import User
from ..services import user_service
from ..i18n import translate_html

router = APIRouter()


@router.get("/admin/pending-users")
async def pending_users_page(request: Request, admin: User = Depends(require_admin)):
    db = get_db()
    pending_users = await user_service.get_pending_users(db)
    return templates.TemplateResponse(request, "admin/pending_users.html", {
        "user": admin,
        "is_admin": True,
        "pending_users": pending_users,
    })


@router.post("/api/users/{user_id}/approve")
async def approve_user(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
):
    db = get_db()
    try:
        await user_service.approve_user(db, user_id, admin.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    msg = translate_html(request, "admin.user_approved")
    return HTMLResponse(
        f'<tr class="border-t bg-green-50"><td colspan="5" class="px-6 py-3 text-green-700 text-center">'
        f"{msg}</td></tr>"
    )


@router.post("/api/users/{user_id}/reject")
async def reject_user(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
):
    db = get_db()
    await user_service.reject_user(db, user_id)
    msg = translate_html(request, "admin.user_rejected")
    return HTMLResponse(
        f'<tr class="border-t bg-red-50"><td colspan="5" class="px-6 py-3 text-red-700 text-center">'
        f"{msg}</td></tr>"
    )


@router.get("/admin/merge-requests")
async def merge_requests_page(request: Request, admin: User = Depends(require_admin)):
    db = get_db()
    merge_requests = await user_service.get_pending_merge_requests(db)
    return templates.TemplateResponse(request, "admin/merge_requests.html", {
        "user": admin,
        "is_admin": True,
        "merge_requests": merge_requests,
    })


@router.post("/api/merge-requests/{request_id}/approve")
async def approve_merge_request(
    request: Request,
    request_id: str,
    admin: User = Depends(require_admin),
):
    db = get_db()
    try:
        await user_service.approve_merge(db, request_id, admin.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    msg = translate_html(request, "admin.merge_approved")
    return HTMLResponse(
        f'<tr class="border-t bg-green-50"><td colspan="5" class="px-6 py-3 text-green-700 text-center">'
        f"{msg}</td></tr>"
    )


@router.post("/api/merge-requests/{request_id}/reject")
async def reject_merge_request(
    request: Request,
    request_id: str,
    admin: User = Depends(require_admin),
):
    db = get_db()
    await user_service.reject_merge(db, request_id, admin.id)
    msg = translate_html(request, "admin.merge_rejected")
    return HTMLResponse(
        f'<tr class="border-t bg-red-50"><td colspan="5" class="px-6 py-3 text-red-700 text-center">'
        f"{msg}</td></tr>"
    )
