"""Seed initial users for Docker deployment.

The seeding process must be idempotent for persistent Docker volumes.
Recreating the container should not delete existing users that may already
be referenced by contracts or review tasks.
"""
import os
import sys
import secrets
import string

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.database import SessionLocal
from src.models.auth_models import User
from src.services.auth_service import AuthService


def _generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Ensure at least one of each category
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*" for c in pwd)
        ):
            return pwd


def seed():
    db = SessionLocal()
    try:
        force = os.getenv("FORCE_RESEED", "").lower() in ("true", "1", "yes")
        auth = AuthService(db)

        # Passwords MUST be set via environment variables.
        # If not set for a new user, a random password is generated and printed ONCE.
        seed_users = [
            ("admin@contractai.ru", "Администратор", "SEED_ADMIN_PASSWORD", "admin", "enterprise"),
            ("lawyer@contractai.ru", "Юрист", "SEED_LAWYER_PASSWORD", "lawyer", "pro"),
            ("vip@contractai.ru", "VIP Юрист", "SEED_VIP_PASSWORD", "senior_lawyer", "enterprise"),
            ("demo@contractai.ru", "Демо пользователь", "SEED_DEMO_PASSWORD", "demo", "demo"),
        ]

        existing_users = {
            user.email: user
            for user in db.query(User).filter(
                User.email.in_([email for email, *_ in seed_users])
            ).all()
        }

        created_count = 0
        updated_count = 0
        kept_count = 0

        print("=" * 60)
        for email, name, env_var, role, tier in seed_users:
            pwd = os.getenv(env_var)
            user = existing_users.get(email)

            if user:
                if force:
                    user.name = name
                    user.role = role
                    user.subscription_tier = tier
                    user.email_verified = True
                    user.active = True
                    user.is_demo = (role == "demo")
                    if pwd:
                        user.password_hash = auth.hash_password(pwd)
                    else:
                        print(
                            f"ℹ️  {env_var} not set for existing user {email}; "
                            "keeping current password."
                        )
                    updated_count += 1
                    print(f"Updated seed user: {email}")
                else:
                    kept_count += 1
                    print(f"Keeping existing user: {email}")
                continue

            if not pwd:
                pwd = _generate_secure_password()
                print(f"⚠️  {env_var} not set! Generated password for {email}: {pwd}")
                print(f"   Set {env_var}={pwd} in your environment to persist it.")

            user = User(
                email=email,
                name=name,
                password_hash=auth.hash_password(pwd),
                role=role,
                subscription_tier=tier,
                email_verified=True,
                active=True,
                is_demo=(role == "demo"),
            )
            db.add(user)
            created_count += 1
            print(f"Created seed user: {email}")
        print("=" * 60)

        db.commit()
        print(
            "Seed complete: "
            f"created={created_count}, updated={updated_count}, kept={kept_count}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
