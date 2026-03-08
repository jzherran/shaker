from supabase import Client


async def get_fund_available_for_lending(db: Client) -> float:
    """Calculate how much of the collective fund is available for new loans."""
    fund = db.table("fund_summary").select("*").eq("id", 1).execute()
    if not fund.data:
        return 0.0
    return float(fund.data[0]["available_for_lending"])
