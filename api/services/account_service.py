from supabase import Client

from ..models.account import Account, AccountCreate, AccountSummary


def _account_from_row(row: dict) -> Account:
    """Build Account from a row that may include joined user data."""
    user_data = row.pop("users", None) or {}
    return Account(
        id=row["id"],
        user_id=row["user_id"],
        account_number=row["account_number"],
        balance=row["balance"],
        status=row["status"],
        owner_name=user_data.get("full_name", ""),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def create_account(db: Client, data: AccountCreate) -> Account:
    result = (
        db.table("accounts")
        .insert(
            {
                "user_id": data.user_id,
                "account_number": data.account_number,
            }
        )
        .execute()
    )
    row = result.data[0]
    # Fetch with user join
    full = db.table("accounts").select("*, users(full_name)").eq("id", row["id"]).execute()
    return _account_from_row(full.data[0])


async def get_account(db: Client, account_id: str) -> Account | None:
    result = db.table("accounts").select("*, users(full_name)").eq("id", account_id).execute()
    if not result.data:
        return None
    return _account_from_row(result.data[0])


async def get_account_by_user(db: Client, user_id: str) -> Account | None:
    result = db.table("accounts").select("*, users(full_name)").eq("user_id", user_id).execute()
    if not result.data:
        return None
    return _account_from_row(result.data[0])


async def get_all_accounts(
    db: Client, status: str = None, active_owner: bool = False
) -> list[Account]:
    """List accounts with optional status filter.

    When active_owner is True, exclude accounts whose user has is_active=false
    (e.g. identity-merge duplicates); use for member/account dropdowns.
    """
    user_cols = "full_name, is_active" if active_owner else "full_name"
    query = db.table("accounts").select(f"*, users({user_cols})")
    if status and status in ("active", "inactive", "suspended"):
        query = query.eq("status", status)
    query = query.order("created_at")
    result = query.execute()
    out: list[Account] = []
    for row in result.data:
        if active_owner:
            user_data = row.get("users") or {}
            if not user_data.get("is_active", True):
                continue
        out.append(_account_from_row(dict(row)))
    return out


async def require_active_account(db: Client, account_id: str) -> Account:
    """Ensure the account exists and is active (contributions, loans, etc.)."""
    account = await get_account(db, account_id)
    if not account:
        raise ValueError("Account not found")
    if account.status != "active":
        raise ValueError("Only active accounts can be used for this operation")
    return account


async def get_account_summary(db: Client, account_id: str) -> AccountSummary | None:
    # Join account with user data
    result = (
        db.table("accounts").select("*, users(full_name, email)").eq("id", account_id).execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    user_data = row.pop("users", {})

    # Get contribution totals
    contrib_result = (
        db.table("contributions")
        .select("amount")
        .eq("account_id", account_id)
        .eq("status", "completed")
        .execute()
    )
    total_contributions = sum(c["amount"] for c in contrib_result.data)

    # Get last contribution date
    last_contrib = (
        db.table("contributions")
        .select("created_at")
        .eq("account_id", account_id)
        .eq("status", "completed")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    last_contribution_at = last_contrib.data[0]["created_at"] if last_contrib.data else None

    # Get active loans count and total disbursements
    loans_result = (
        db.table("loans")
        .select("amount_approved, status")
        .eq("account_id", account_id)
        .in_("status", ["approved", "active"])
        .execute()
    )
    active_loans_count = len(loans_result.data)
    total_disbursements = sum(loan["amount_approved"] or 0 for loan in loans_result.data)

    return AccountSummary(
        id=row["id"],
        user_id=row["user_id"],
        account_number=row["account_number"],
        balance=row["balance"],
        status=row["status"],
        owner_name=user_data.get("full_name", ""),
        email=user_data.get("email", ""),
        total_contributions=total_contributions,
        total_loan_disbursements=total_disbursements,
        active_loans_count=active_loans_count,
        created_at=row["created_at"],
        last_contribution_at=last_contribution_at,
    )


async def update_account_status(db: Client, account_id: str, status: str) -> Account | None:
    result = (
        db.table("accounts")
        .update({"status": status, "updated_at": "now()"})
        .eq("id", account_id)
        .execute()
    )
    if not result.data:
        return None
    # Re-fetch with user join
    full = db.table("accounts").select("*, users(full_name)").eq("id", account_id).execute()
    return _account_from_row(full.data[0])


async def generate_account_number(db: Client) -> str:
    """Generate the next sequential account number like FON-0001."""
    result = (
        db.table("accounts")
        .select("account_number")
        .order("account_number", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return "FON-0001"

    last = result.data[0]["account_number"]
    num = int(last.split("-")[1]) + 1
    return f"FON-{num:04d}"
