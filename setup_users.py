#!/usr/bin/env python3
"""
Create test users for Contract AI System via API.
Passwords are read from environment variables.
"""
import os
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

TEST_USERS = [
    {
        "email": "demo@example.com",
        "name": "Demo User",
        "password_env": "SEED_DEMO_PASSWORD",
        "role": "demo",
        "subscription_tier": "demo"
    },
    {
        "email": "user@example.com",
        "name": "Regular User",
        "password_env": "SEED_DEMO_PASSWORD",
        "role": "junior_lawyer",
        "subscription_tier": "basic"
    },
    {
        "email": "lawyer@example.com",
        "name": "Lawyer Pro",
        "password_env": "SEED_LAWYER_PASSWORD",
        "role": "lawyer",
        "subscription_tier": "pro"
    },
    {
        "email": "senior@example.com",
        "name": "Senior Lawyer",
        "password_env": "SEED_VIP_PASSWORD",
        "role": "senior_lawyer",
        "subscription_tier": "pro"
    },
    {
        "email": "admin@example.com",
        "name": "System Admin",
        "password_env": "SEED_ADMIN_PASSWORD",
        "role": "admin",
        "subscription_tier": "enterprise"
    }
]


def create_user(user_data):
    password = os.environ.get(user_data["password_env"], "")
    if not password:
        print(f"⚠️  {user_data['password_env']} not set, skipping {user_data['email']}")
        return False

    payload = {
        "email": user_data["email"],
        "name": user_data["name"],
        "password": password,
        "role": user_data["role"],
        "subscription_tier": user_data["subscription_tier"],
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=payload, timeout=5)
        if response.status_code == 201:
            print(f"✅ Created: {user_data['email']} ({user_data['role']})")
            return True
        elif response.status_code == 400 and "already exists" in response.text.lower():
            print(f"ℹ️  Already exists: {user_data['email']}")
            return False
        else:
            print(f"❌ Failed: {user_data['email']} - {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Backend is not running.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print("=" * 60)
    print("  Creating Test Users for Contract AI System")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code != 200:
            print("❌ Backend is not healthy.")
            return
    except Exception:
        print("❌ Backend is not running!")
        return

    created = sum(1 for u in TEST_USERS if create_user(u))
    print(f"\n✅ Created {created} new users")


if __name__ == "__main__":
    main()
