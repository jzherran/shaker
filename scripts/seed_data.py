"""
Seed test data for local development.
Creates test users, accounts, and contributions.

Usage: python -m scripts.seed_data
"""
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from api.database import get_db


def seed():
    db = get_db()

    # Create test users
    users = [
        {"auth_id": str(uuid.uuid4()), "email": "admin@fonafahe.org",
         "full_name": "Admin User", "role": "admin"},
        {"auth_id": str(uuid.uuid4()), "email": "maria@example.com",
         "full_name": "Maria Garcia", "role": "member"},
        {"auth_id": str(uuid.uuid4()), "email": "carlos@example.com",
         "full_name": "Carlos Lopez", "role": "member"},
    ]

    print("Creating users...")
    for u in users:
        db.table("users").upsert(u, on_conflict="email").execute()

    # Fetch created users
    result = db.table("users").select("id, email, full_name").execute()
    user_map = {u["email"]: u["id"] for u in result.data}

    # Create accounts
    print("Creating accounts...")
    accounts_data = [
        {"user_id": user_map["admin@fonafahe.org"], "account_number": "FON-0001"},
        {"user_id": user_map["maria@example.com"], "account_number": "FON-0002"},
        {"user_id": user_map["carlos@example.com"], "account_number": "FON-0003"},
    ]
    for a in accounts_data:
        db.table("accounts").upsert(a, on_conflict="account_number").execute()

    # Fetch accounts
    accts = db.table("accounts").select("id, account_number, user_id").execute()
    acct_map = {a["account_number"]: a["id"] for a in accts.data}

    # Create some contributions
    print("Creating contributions...")
    admin_id = user_map["admin@fonafahe.org"]
    for acct_num, acct_id in acct_map.items():
        for month in range(1, 4):
            db.rpc("record_contribution", {
                "p_account_id": acct_id,
                "p_amount": 100.00,
                "p_contribution_type": "regular",
                "p_period_year": 2026,
                "p_period_month": month,
                "p_description": f"Monthly contribution {month}/2026",
                "p_receipt_reference": "",
                "p_created_by": admin_id,
            }).execute()

    print("Seed data created successfully!")
    print(f"Users: {len(users)}")
    print(f"Accounts: {len(accounts_data)}")
    print("Contributions: 9 (3 per account, Jan-Mar 2026)")


if __name__ == "__main__":
    seed()
