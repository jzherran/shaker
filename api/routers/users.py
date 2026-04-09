from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from ..dependencies import templates, get_db
from ..auth import require_admin
from ..models.user import User
from ..services import user_service

router = APIRouter()


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
    request_id: str, admin: User = Depends(require_admin)
):
    db = get_db()
    try:
        await user_service.approve_merge(db, request_id, admin.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return HTMLResponse(
        '<tr class="border-t bg-green-50"><td colspan="5" class="px-6 py-3 text-green-700 text-center">'
        'Merge approved successfully.</td></tr>'
    )


@router.post("/api/merge-requests/{request_id}/reject")
async def reject_merge_request(
    request_id: str, admin: User = Depends(require_admin)
):
    db = get_db()
    await user_service.reject_merge(db, request_id, admin.id)
    return HTMLResponse(
        '<tr class="border-t bg-red-50"><td colspan="5" class="px-6 py-3 text-red-700 text-center">'
        'Merge rejected.</td></tr>'
    )
