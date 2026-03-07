#!/usr/bin/env python3
"""
Seed initial users for Contract AI System.
Run inside Docker container or locally with DATABASE_URL set.

Creates 4 users:
  - Admin (enterprise)
  - Lawyer (pro) — обычный пользователь
  - VIP Client (enterprise)
  - Demo User (demo)
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal, engine, Base
from src.models.auth_models import User
from src.services.auth_service import AuthService


# ============================================================
# USER DEFINITIONS
# ============================================================
USERS = [
    {
        "email": "admin@contractai.ru",
        "name": "Администратор",
        "password": "***REMOVED***",
        "role": "admin",
        "tier": "enterprise",
    },
    {
        "email": "lawyer@contractai.ru",
        "name": "Юрист Иванов",
        "password": "***REMOVED***",
        "role": "lawyer",
        "tier": "pro",
    },
    {
        "email": "vip@contractai.ru",
        "name": "VIP Клиент",
        "password": "***REMOVED***",
        "role": "senior_lawyer",
        "tier": "enterprise",
    },
    {
        "email": "demo@contractai.ru",
        "name": "Демо Пользователь",
        "password": "***REMOVED***",
        "role": "junior_lawyer",
        "tier": "demo",
    },
]


def seed():
    db = SessionLocal()
    try:
        created = []
        skipped = []

        for u in USERS:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                skipped.append(u["email"])
                continue

            user = User(
                email=u["email"],
                name=u["name"],
                password_hash=AuthService.hash_password(u["password"]),
                role=u["role"],
                subscription_tier=u["tier"],
                email_verified=True,   # skip verification for seed users
                active=True,
                is_demo=(u["tier"] == "demo"),
            )
            db.add(user)
            created.append(u["email"])

        db.commit()

        # Print results
        print()
        print("=" * 60)
        print("  CONTRACT AI SYSTEM — SEED USERS")
        print("=" * 60)

        if created:
            print(f"\n  Created {len(created)} users:\n")
            print(f"  {'Email':<30} {'Password':<16} {'Role':<16} {'Tier'}")
            print(f"  {'-'*30} {'-'*16} {'-'*16} {'-'*12}")
            for u in USERS:
                if u["email"] in created:
                    print(f"  {u['email']:<30} {u['password']:<16} {u['role']:<16} {u['tier']}")
        else:
            print("\n  No new users created.")

        if skipped:
            print(f"\n  Skipped (already exist): {', '.join(skipped)}")

        print()
        print("=" * 60)
        print()

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
