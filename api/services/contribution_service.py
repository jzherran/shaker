from supabase import Client
from ..models.contribution import Contribution, ContributionCreate
from typing import Optional


async def record_contribution(
    db: Client, data: ContributionCreate, created_by: str
) -> Contribution:
    """Record a contribution using the atomic DB function."""
    result = db.rpc("record_contribution", {
        "p_account_id": data.account_id,
        "p_amount": data.amount,
        "p_contribution_type": data.contribution_type,
        "p_period_year": data.period_year,
        "p_period_month": data.period_month,
        "p_description": data.description or "",
        "p_receipt_reference": data.receipt_reference or "",
        "p_created_by": created_by,
    }).execute()

    contribution_id = result.data
    # Fetch the created contribution
    row = db.table("contributions").select("*").eq("id", contribution_id).execute()
    return Contribution(**row.data[0])


async def cancel_contribution(db: Client, contribution_id: str) -> None:
    """Cancel a contribution and reverse the balance."""
    db.rpc("cancel_contribution", {
        "p_contribution_id": contribution_id,
    }).execute()


async def get_contributions(
    db: Client,
    account_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Contribution]:
    query = db.table("contributions").select("*")

    if account_id:
        query = query.eq("account_id", account_id)
    if year:
        query = query.eq("period_year", year)
    if month:
        query = query.eq("period_month", month)

    query = query.neq("status", "cancelled")
    query = query.order("created_at", desc=True)
    query = query.range(offset, offset + limit - 1)

    result = query.execute()
    return [Contribution(**row) for row in result.data]


async def get_contribution(db: Client, contribution_id: str) -> Optional[Contribution]:
    result = db.table("contributions").select("*").eq("id", contribution_id).execute()
    if not result.data:
        return None
    return Contribution(**result.data[0])
