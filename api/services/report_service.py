from collections import defaultdict
from datetime import date

from supabase import Client

from ..models.report import BalanceSnapshot, FundSummary


async def get_balance_snapshots(
    db: Client,
    account_id: str,
    snapshot_type: str = "monthly",
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[BalanceSnapshot]:
    query = (
        db.table("balance_snapshots")
        .select("*")
        .eq("account_id", account_id)
        .eq("snapshot_type", snapshot_type)
    )

    if date_from:
        query = query.gte("snapshot_date", date_from.isoformat())
    if date_to:
        query = query.lte("snapshot_date", date_to.isoformat())

    query = query.order("snapshot_date", desc=True)
    result = query.execute()
    return [BalanceSnapshot(**row) for row in result.data]


async def get_account_balance_history(
    db: Client,
    account_id: str,
    months: int = 12,
) -> list[dict]:
    """Return monthly balance points for an account, oldest -> newest.

    Each item is {"date": "YYYY-MM-DD", "balance": float}. Backed by
    `balance_snapshots` rows of type 'monthly'.
    """
    result = (
        db.table("balance_snapshots")
        .select("snapshot_date, balance")
        .eq("account_id", account_id)
        .eq("snapshot_type", "monthly")
        .order("snapshot_date", desc=True)
        .limit(months)
        .execute()
    )
    rows = list(reversed(result.data or []))
    return [{"date": row["snapshot_date"], "balance": float(row["balance"])} for row in rows]


async def get_fund_historical_balances(db: Client, months: int = 12) -> list[dict]:
    """Aggregate monthly balance snapshots across all accounts.

    Returns oldest -> newest list of {"date": "YYYY-MM-DD", "balance": float},
    where balance is the sum across all accounts for that month.
    """
    result = (
        db.table("balance_snapshots")
        .select("snapshot_date, balance")
        .eq("snapshot_type", "monthly")
        .order("snapshot_date", desc=True)
        .execute()
    )
    rows = result.data or []

    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[row["snapshot_date"]] += float(row["balance"])

    sorted_dates = sorted(totals.keys())
    if months and len(sorted_dates) > months:
        sorted_dates = sorted_dates[-months:]

    return [{"date": d, "balance": totals[d]} for d in sorted_dates]


async def get_fund_per_account_history(db: Client, months: int = 12) -> dict:
    """Per-account monthly balance history aligned to a shared timeline.

    Returns: {
        "labels": ["YYYY-MM", ...],
        "series": [
            {"name": "Random Name", "account_number": "RAND-0001",
             "data": [float|None, ...]},
            ...
        ],
    }
    Missing months are filled with None so Chart.js can show gaps.
    """
    snaps = (
        db.table("balance_snapshots")
        .select("snapshot_date, balance, account_id")
        .eq("snapshot_type", "monthly")
        .order("snapshot_date", desc=False)
        .execute()
    )
    rows = snaps.data or []
    if not rows:
        return {"labels": [], "series": []}

    accounts = db.table("accounts").select("id, account_number, users(full_name)").execute()
    account_meta: dict[str, dict] = {}
    for a in accounts.data or []:
        owner = (a.get("users") or {}).get("full_name") or a["account_number"]
        account_meta[a["id"]] = {"name": owner, "account_number": a["account_number"]}

    by_account: dict[str, dict[str, float]] = defaultdict(dict)
    all_dates: set[str] = set()
    for row in rows:
        d = row["snapshot_date"]
        all_dates.add(d)
        by_account[row["account_id"]][d] = float(row["balance"])

    sorted_dates = sorted(all_dates)
    if months and len(sorted_dates) > months:
        sorted_dates = sorted_dates[-months:]

    series = []
    for account_id, points in by_account.items():
        meta = account_meta.get(
            account_id, {"name": account_id[:8], "account_number": account_id[:8]}
        )
        data = [points.get(d) for d in sorted_dates]
        if not any(v is not None for v in data):
            continue
        series.append(
            {
                "name": meta["name"],
                "account_number": meta["account_number"],
                "data": data,
            }
        )

    series.sort(key=lambda s: s["name"].lower())

    return {
        "labels": [d[:7] for d in sorted_dates],
        "series": series,
    }


async def get_fund_summary(db: Client) -> FundSummary | None:
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
    loans = (
        db.table("loans").select("amount_approved").in_("status", ["approved", "active"]).execute()
    )
    total_active_loans = sum(float(loan["amount_approved"] or 0) for loan in loans.data)

    available = total_balance - total_active_loans

    result = (
        db.table("fund_summary")
        .update(
            {
                "total_balance": total_balance,
                "total_members": total_members,
                "total_active_loans": total_active_loans,
                "available_for_lending": max(available, 0),
                "last_updated": "now()",
            }
        )
        .eq("id", 1)
        .execute()
    )

    return FundSummary(**result.data[0])


async def generate_daily_snapshot(db: Client, snapshot_date: date) -> int:
    """Generate daily balance snapshots for all active accounts. Returns count."""
    accounts = db.table("accounts").select("id, balance").eq("status", "active").execute()
    count = 0

    for account in accounts.data:
        account_id = account["id"]

        # Get contribution total up to snapshot_date
        contribs = (
            db.table("contributions")
            .select("amount")
            .eq("account_id", account_id)
            .eq("status", "completed")
            .lte("created_at", f"{snapshot_date}T23:59:59")
            .execute()
        )
        total_contributions = sum(float(c["amount"]) for c in contribs.data)

        # Get loan disbursement total
        loans = (
            db.table("loans")
            .select("amount_approved")
            .eq("account_id", account_id)
            .in_("status", ["active", "paid"])
            .lte("disbursed_at", f"{snapshot_date}T23:59:59")
            .execute()
        )
        total_disbursements = sum(float(loan["amount_approved"] or 0) for loan in loans.data)

        # Get loan payments total
        payments = (
            db.table("loan_payments")
            .select("amount, loan_id")
            .eq("status", "completed")
            .lte("created_at", f"{snapshot_date}T23:59:59")
            .execute()
        )
        # Filter to this account's loans
        account_loans = db.table("loans").select("id").eq("account_id", account_id).execute()
        account_loan_ids = {row["id"] for row in account_loans.data}
        total_payments = sum(
            float(p["amount"]) for p in payments.data if p["loan_id"] in account_loan_ids
        )

        # Upsert snapshot
        db.table("balance_snapshots").upsert(
            {
                "account_id": account_id,
                "snapshot_type": "daily",
                "snapshot_date": snapshot_date.isoformat(),
                "balance": float(account["balance"]),
                "total_contributions": total_contributions,
                "total_loan_disbursements": total_disbursements,
                "total_loan_payments": total_payments,
            },
            on_conflict="account_id,snapshot_type,snapshot_date",
        ).execute()
        count += 1

    return count
