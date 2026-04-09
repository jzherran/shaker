from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..auth import require_admin
from ..dependencies import get_db
from ..i18n import translate_html
from ..models.user import User
from ..services import user_service

router = APIRouter()


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
        raise HTTPException(status_code=400, detail=str(e)) from e
    msg = translate_html(request, "admin.user_approved")
    return HTMLResponse(f'<span class="text-sm font-medium text-emerald-700">{msg}</span>')


@router.post("/api/users/{user_id}/reject")
async def reject_user(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
):
    db = get_db()
    await user_service.reject_user(db, user_id)
    msg = translate_html(request, "admin.user_rejected")
    return HTMLResponse(f'<span class="text-sm font-medium text-red-700">{msg}</span>')


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
        raise HTTPException(status_code=400, detail=str(e)) from e
    msg = translate_html(request, "admin.merge_approved")
    return HTMLResponse(f'<span class="text-sm font-medium text-emerald-700">{msg}</span>')


@router.post("/api/merge-requests/{request_id}/reject")
async def reject_merge_request(
    request: Request,
    request_id: str,
    admin: User = Depends(require_admin),
):
    db = get_db()
    await user_service.reject_merge(db, request_id, admin.id)
    msg = translate_html(request, "admin.merge_rejected")
    return HTMLResponse(f'<span class="text-sm font-medium text-red-700">{msg}</span>')
