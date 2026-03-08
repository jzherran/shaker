from supabase import Client
from ..models.account import Account, AccountCreate, AccountSummary
from typing import Optional


async def create_account(db: Client, data: AccountCreate) -> Account:
    result = db.table("accounts").insert({
        "user_id": data.user_id,
        "account_number": data.account_number,
    }).execute()
    return Account(**result.data[0])


async def get_account(db: Client, account_id: str) -> Optional[Account]:
    result = db.table("accounts").select("*").eq("id", account_id).execute()
    if not result.data:
        return None
    return Account(**result.data[0])


async def get_account_by_user(db: Client, user_id: str) -> Optional[Account]:
    result = db.table("accounts").select("*").eq("user_id", user_id).execute()
    if not result.data:
        return None
    return Account(**result.data[0])


async def get_all_accounts(db: Client) -> list[Account]:
    result = db.table("accounts").select("*").order("created_at").execute()
    return [Account(**row) for row in result.data]


async def get_account_summary(db: Client, account_id: str) -> Optional[AccountSummary]:
    # Join account with user data
    result = db.table("accounts").select(
        "*, users(full_name, email)"
    ).eq("id", account_id).execute()

    if not result.data:
        return None

    row = result.data[0]
    user_data = row.pop("users", {})

    # Get contribution totals
    contrib_result = db.table("contributions").select(
        "amount"
    ).eq("account_id", account_id).eq("status", "completed").execute()
    total_contributions = sum(c["amount"] for c in contrib_result.data)

    # Get last contribution date
    last_contrib = db.table("contributions").select(
        "created_at"
    ).eq("account_id", account_id).eq(
        "status", "completed"
    ).order("created_at", desc=True).limit(1).execute()
    last_contribution_at = last_contrib.data[0]["created_at"] if last_contrib.data else None

    # Get active loans count and total disbursements
    loans_result = db.table("loans").select(
        "amount_approved, status"
    ).eq("account_id", account_id).in_(
        "status", ["approved", "active"]
    ).execute()
    active_loans_count = len(loans_result.data)
    total_disbursements = sum(
        l["amount_approved"] or 0 for l in loans_result.data
    )

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


async def update_account_status(db: Client, account_id: str, status: str) -> Optional[Account]:
    result = db.table("accounts").update(
        {"status": status, "updated_at": "now()"}
    ).eq("id", account_id).execute()
    if not result.data:
        return None
    return Account(**result.data[0])


async def generate_account_number(db: Client) -> str:
    """Generate the next sequential account number like FON-0001."""
    result = db.table("accounts").select(
        "account_number"
    ).order("account_number", desc=True).limit(1).execute()

    if not result.data:
        return "FON-0001"

    last = result.data[0]["account_number"]
    num = int(last.split("-")[1]) + 1
    return f"FON-{num:04d}"
