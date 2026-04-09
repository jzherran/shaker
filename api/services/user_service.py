from supabase import Client
from ..models.user import User, MergeRequest, MergeRequestDetail
from typing import Optional


async def enroll_national_id(
    db: Client, user_id: str, national_id: str
) -> tuple[str, Optional[MergeRequest]]:
    """
    Enroll a user's national ID. If another active user has the same ID,
    create a merge request instead of saving directly.
    Returns ("enrolled", None) or ("merge_requested", MergeRequest).
    """
    # Check if another active user already has this national_id
    existing = (
        db.table("users")
        .select("*")
        .eq("national_id", national_id)
        .eq("is_active", True)
        .neq("id", user_id)
        .execute()
    )

    if existing.data:
        target_user = existing.data[0]

        # Check for existing pending merge request
        pending = (
            db.table("identity_merge_requests")
            .select("*")
            .eq("requesting_user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        if pending.data:
            return ("already_pending", MergeRequest(**pending.data[0]))

        # Create merge request
        result = (
            db.table("identity_merge_requests")
            .insert({
                "requesting_user_id": user_id,
                "target_user_id": target_user["id"],
                "national_id": national_id,
            })
            .execute()
        )
        # Save national_id on the requesting user too
        db.table("users").update(
            {"national_id": national_id}
        ).eq("id", user_id).execute()

        return ("merge_requested", MergeRequest(**result.data[0]))

    # No match — save national_id directly
    db.table("users").update(
        {"national_id": national_id}
    ).eq("id", user_id).execute()
    return ("enrolled", None)


async def get_pending_merge_requests(db: Client) -> list[MergeRequestDetail]:
    """Get all pending merge requests with user details."""
    result = (
        db.table("identity_merge_requests")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    )

    details = []
    for row in result.data:
        req_user = db.table("users").select("full_name, email").eq(
            "id", row["requesting_user_id"]
        ).execute()
        tgt_user = db.table("users").select("full_name, email").eq(
            "id", row["target_user_id"]
        ).execute()

        details.append(MergeRequestDetail(
            **row,
            requesting_user_name=req_user.data[0]["full_name"] if req_user.data else "",
            requesting_user_email=req_user.data[0]["email"] if req_user.data else "",
            target_user_name=tgt_user.data[0]["full_name"] if tgt_user.data else "",
            target_user_email=tgt_user.data[0]["email"] if tgt_user.data else "",
        ))

    return details


async def approve_merge(db: Client, merge_request_id: str, admin_user_id: str) -> None:
    """Approve a merge request using the atomic DB function."""
    db.rpc("approve_identity_merge", {
        "p_merge_request_id": merge_request_id,
        "p_reviewed_by": admin_user_id,
    }).execute()


async def reject_merge(db: Client, merge_request_id: str, admin_user_id: str) -> None:
    """Reject a merge request."""
    db.table("identity_merge_requests").update({
        "status": "rejected",
        "reviewed_by": admin_user_id,
        "reviewed_at": "now()",
    }).eq("id", merge_request_id).execute()


async def update_user_profile(db: Client, user_id: str, data: dict) -> User:
    """Update user profile fields."""
    update_data = {k: v for k, v in data.items() if v is not None}
    if not update_data:
        # Nothing to update, return current user
        result = db.table("users").select("*").eq("id", user_id).execute()
        return User(**result.data[0])

    db.table("users").update(update_data).eq("id", user_id).execute()
    result = db.table("users").select("*").eq("id", user_id).execute()
    return User(**result.data[0])


async def get_user_merge_status(db: Client, user_id: str) -> Optional[str]:
    """Check if user has a pending merge request. Returns status or None."""
    result = (
        db.table("identity_merge_requests")
        .select("status")
        .eq("requesting_user_id", user_id)
        .eq("status", "pending")
        .limit(1)
        .execute()
    )
    return result.data[0]["status"] if result.data else None


async def get_active_users_with_accounts(db: Client) -> list[dict]:
    """Get all active users with their account info and default amounts."""
    result = (
        db.table("accounts")
        .select("id, account_number, balance, user_id, users(id, full_name, email, default_contribution_amount)")
        .eq("status", "active")
        .order("account_number")
        .execute()
    )

    users_accounts = []
    for row in result.data:
        user_data = row.get("users") or {}
        users_accounts.append({
            "account_id": row["id"],
            "account_number": row["account_number"],
            "balance": row["balance"],
            "user_id": row["user_id"],
            "full_name": user_data.get("full_name", ""),
            "email": user_data.get("email", ""),
            "default_amount": user_data.get("default_contribution_amount"),
        })

    return users_accounts
