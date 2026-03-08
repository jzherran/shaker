from supabase import Client
from ..models.report import BalanceSnapshot, FundSummary
from typing import Optional
from datetime import date


async def get_balance_snapshots(
    db: Client,
    account_id: str,
    snapshot_type: str = "monthly",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[BalanceSnapshot]:
    query = db.table("balance_snapshots").select("*").eq(
        "account_id", account_id
    ).eq("snapshot_type", snapshot_type)

    if date_from:
        query = query.gte("snapshot_date", date_from.isoformat())
    if date_to:
        query = query.lte("snapshot_date", date_to.isoformat())

    query = query.order("snapshot_date", desc=True)
    result = query.execute()
    return [BalanceSnapshot(**row) for row in result.data]


async def get_fund_summary(db: Client) -> Optional[FundSummary]:
    result = db.table("fund_summary").select("*").eq("id", 1).execute()
    if not result.data:
        return None
    return FundSummary(**result.data[0])


async def update_fund_summary(db: Client) -> FundSummary:
    """Recalculate and update the fund summary."""
    # Total balance across all active accounts
    accounts = db.table("accounts").select("balance").eq("status", "active").execute()
    total_balance = sum(float(a["balance"]) for a in accounts.data)
    total_members = len(accounts.data)

    # Total active loans
    loans = db.table("loans").select("amount_approved").in_(
        "status", ["approved", "active"]
    ).execute()
    total_active_loans = sum(float(l["amount_approved"] or 0) for l in loans.data)

    available = total_balance - total_active_loans

    result = db.table("fund_summary").update({
        "total_balance": total_balance,
        "total_members": total_members,
        "total_active_loans": total_active_loans,
        "available_for_lending": max(available, 0),
        "last_updated": "now()",
    }).eq("id", 1).execute()

    return FundSummary(**result.data[0])


async def generate_daily_snapshot(db: Client, snapshot_date: date) -> int:
    """Generate daily balance snapshots for all active accounts. Returns count."""
    accounts = db.table("accounts").select("id, balance").eq("status", "active").execute()
    count = 0

    for account in accounts.data:
        account_id = account["id"]

        # Get contribution total up to snapshot_date
        contribs = db.table("contributions").select("amount").eq(
            "account_id", account_id
        ).eq("status", "completed").lte(
            "created_at", f"{snapshot_date}T23:59:59"
        ).execute()
        total_contributions = sum(float(c["amount"]) for c in contribs.data)

        # Get loan disbursement total
        loans = db.table("loans").select("amount_approved").eq(
            "account_id", account_id
        ).in_("status", ["active", "paid"]).lte(
            "disbursed_at", f"{snapshot_date}T23:59:59"
        ).execute()
        total_disbursements = sum(float(l["amount_approved"] or 0) for l in loans.data)

        # Get loan payments total
        payments = db.table("loan_payments").select(
            "amount, loan_id"
        ).eq("status", "completed").lte(
            "created_at", f"{snapshot_date}T23:59:59"
        ).execute()
        # Filter to this account's loans
        account_loans = db.table("loans").select("id").eq(
            "account_id", account_id
        ).execute()
        account_loan_ids = {l["id"] for l in account_loans.data}
        total_payments = sum(
            float(p["amount"]) for p in payments.data
            if p["loan_id"] in account_loan_ids
        )

        # Upsert snapshot
        db.table("balance_snapshots").upsert({
            "account_id": account_id,
            "snapshot_type": "daily",
            "snapshot_date": snapshot_date.isoformat(),
            "balance": float(account["balance"]),
            "total_contributions": total_contributions,
            "total_loan_disbursements": total_disbursements,
            "total_loan_payments": total_payments,
        }, on_conflict="account_id,snapshot_type,snapshot_date").execute()
        count += 1

    return count
