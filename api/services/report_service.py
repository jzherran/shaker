from collections import defaultdict
from datetime import date, timedelta

from supabase import Client

from ..models.report import BalanceSnapshot, FundSummary

SNAPSHOT_TYPES = ("daily", "monthly", "yearly")


def normalize_snapshot_date(snapshot_date: date, snapshot_type: str) -> date:
    """Snap the date to the conventional end-of-period for the given type.

    - daily: returned unchanged.
    - monthly: last day of `snapshot_date`'s month.
    - yearly: December 31 of `snapshot_date`'s year.
    """
    if snapshot_type == "monthly":
        if snapshot_date.month == 12:
            return date(snapshot_date.year, 12, 31)
        return date(snapshot_date.year, snapshot_date.month + 1, 1) - timedelta(days=1)
    if snapshot_type == "yearly":
        return date(snapshot_date.year, 12, 31)
    return snapshot_date


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


async def get_balance_snapshots_for_accounts(
    db: Client,
    account_ids: list[str],
    snapshot_type: str = "monthly",
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[BalanceSnapshot]:
    """Fetch snapshots for one or more accounts in a single query."""
    if not account_ids:
        return []
    query = (
        db.table("balance_snapshots")
        .select("*")
        .in_("account_id", account_ids)
        .eq("snapshot_type", snapshot_type)
    )
    if date_from:
        query = query.gte("snapshot_date", date_from.isoformat())
    if date_to:
        query = query.lte("snapshot_date", date_to.isoformat())
    query = query.order("snapshot_date", desc=True)
    result = query.execute()
    return [BalanceSnapshot(**row) for row in result.data]


async def get_accounts_meta(db: Client, account_ids: list[str]) -> dict[str, dict]:
    """Return ``{account_id: {name, account_number}}`` for the given ids."""
    if not account_ids:
        return {}
    res = (
        db.table("accounts")
        .select("id, account_number, users(full_name)")
        .in_("id", account_ids)
        .execute()
    )
    out: dict[str, dict] = {}
    for row in res.data or []:
        owner = (row.get("users") or {}).get("full_name") or row["account_number"]
        out[row["id"]] = {"name": owner, "account_number": row["account_number"]}
    return out


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


def _upsert_account_snapshot(
    db: Client, account: dict, snapshot_date: date, snapshot_type: str
) -> None:
    """Compute totals for a single account and upsert one snapshot row.

    The same totals query is used for every `snapshot_type`; the only
    difference is the row tag so the existing reporting queries can pick
    the right grain (daily / monthly / yearly).
    """
    account_id = account["id"]

    contribs = (
        db.table("contributions")
        .select("amount")
        .eq("account_id", account_id)
        .eq("status", "completed")
        .lte("created_at", f"{snapshot_date}T23:59:59")
        .execute()
    )
    total_contributions = sum(float(c["amount"]) for c in contribs.data)

    loans = (
        db.table("loans")
        .select("amount_approved")
        .eq("account_id", account_id)
        .in_("status", ["active", "paid"])
        .lte("disbursed_at", f"{snapshot_date}T23:59:59")
        .execute()
    )
    total_disbursements = sum(float(loan["amount_approved"] or 0) for loan in loans.data)

    account_loans = db.table("loans").select("id").eq("account_id", account_id).execute()
    account_loan_ids = {row["id"] for row in account_loans.data}
    if account_loan_ids:
        payments = (
            db.table("loan_payments")
            .select("amount, loan_id")
            .eq("status", "completed")
            .in_("loan_id", list(account_loan_ids))
            .lte("created_at", f"{snapshot_date}T23:59:59")
            .execute()
        )
        total_payments = sum(float(p["amount"]) for p in payments.data)
    else:
        total_payments = 0.0

    db.table("balance_snapshots").upsert(
        {
            "account_id": account_id,
            "snapshot_type": snapshot_type,
            "snapshot_date": snapshot_date.isoformat(),
            "balance": float(account["balance"]),
            "total_contributions": total_contributions,
            "total_loan_disbursements": total_disbursements,
            "total_loan_payments": total_payments,
        },
        on_conflict="account_id,snapshot_type,snapshot_date",
    ).execute()


async def generate_snapshots(
    db: Client,
    snapshot_date: date,
    snapshot_type: str = "daily",
    account_ids: list[str] | None = None,
) -> dict:
    """Generate balance snapshots of the requested type.

    - When `account_ids` is None/empty, snapshots are generated for every
      active account (the legacy behavior).
    - When provided, only active accounts whose id is in the list are
      processed; missing or inactive ids are reported back as `skipped`.

    The `snapshot_date` is normalized via `normalize_snapshot_date`, so a
    `monthly` request from any day of the month writes a row dated to the
    last day of that month, and a `yearly` request writes one dated Dec 31.

    Returns: ``{"generated": int, "skipped": list[str], "snapshot_type":
    str, "snapshot_date": "YYYY-MM-DD"}``.
    """
    if snapshot_type not in SNAPSHOT_TYPES:
        raise ValueError(f"Unsupported snapshot_type: {snapshot_type}")

    effective_date = normalize_snapshot_date(snapshot_date, snapshot_type)

    query = db.table("accounts").select("id, balance, status")
    if account_ids:
        query = query.in_("id", account_ids)
    else:
        query = query.eq("status", "active")
    rows = query.execute().data or []

    eligible = [a for a in rows if a.get("status") == "active"]
    for account in eligible:
        _upsert_account_snapshot(db, account, effective_date, snapshot_type)

    skipped: list[str] = []
    if account_ids:
        eligible_ids = {a["id"] for a in eligible}
        skipped = [aid for aid in account_ids if aid not in eligible_ids]

    return {
        "generated": len(eligible),
        "skipped": skipped,
        "snapshot_type": snapshot_type,
        "snapshot_date": effective_date.isoformat(),
    }


async def generate_daily_snapshot(
    db: Client,
    snapshot_date: date,
    account_ids: list[str] | None = None,
) -> dict:
    """Backwards-compatible wrapper that always writes daily snapshots."""
    return await generate_snapshots(db, snapshot_date, "daily", account_ids)
