"""
Snapshot Generation Script

Run daily via cron to generate balance snapshots.
Usage: python -m scripts.generate_snapshots

On month-end, also generates monthly snapshots.
On year-end, also generates yearly snapshots.
"""
import asyncio
import sys
import os
from datetime import date

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from api.database import get_db
from api.services.report_service import generate_daily_snapshot, update_fund_summary


async def main():
    db = get_db()
    today = date.today()

    print(f"Generating daily snapshots for {today}...")
    count = await generate_daily_snapshot(db, today)
    print(f"Generated {count} daily snapshots.")

    print("Updating fund summary...")
    fund = await update_fund_summary(db)
    print(f"Fund: balance=${fund.total_balance}, members={fund.total_members}, "
          f"active_loans=${fund.total_active_loans}, available=${fund.available_for_lending}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
