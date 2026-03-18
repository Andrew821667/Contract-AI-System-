"""Seed initial users for Docker deployment."""
import os
import sys
import secrets
import string
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.database import SessionLocal, Base, engine
from src.models.auth_models import User
from src.services.auth_service import AuthService


def _generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Ensure at least one of each category
        if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd)
                and any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*" for c in pwd)):
            return pwd


def seed():
    db = SessionLocal()
    try:
        force = os.getenv("FORCE_RESEED", "").lower() in ("true", "1", "yes")
        existing = db.query(User).first()

        if existing and not force:
            print("Users already exist, skipping seed.")
            return

        if existing and force:
            count = db.query(User).delete()
            db.commit()
            print(f"FORCE_RESEED: deleted {count} existing users.")

        auth = AuthService(db)

        # Passwords MUST be set via environment variables.
        # If not set, a random password is generated and printed ONCE.
        seed_users = [
            ("admin@contractai.ru", "Администратор", "SEED_ADMIN_PASSWORD", "admin", "enterprise"),
            ("lawyer@contractai.ru", "Юрист", "SEED_LAWYER_PASSWORD", "lawyer", "pro"),
            ("vip@contractai.ru", "VIP Юрист", "SEED_VIP_PASSWORD", "senior_lawyer", "enterprise"),
            ("demo@contractai.ru", "Демо пользователь", "SEED_DEMO_PASSWORD", "demo", "demo"),
        ]

        print("=" * 60)
        for email, name, env_var, role, tier in seed_users:
            pwd = os.getenv(env_var)
            if not pwd:
                pwd = _generate_secure_password()
                print(f"⚠️  {env_var} not set! Generated password for {email}: {pwd}")
                print(f"   Set {env_var}={pwd} in your environment to persist it.")

            user = User(
                email=email, name=name,
                password_hash=auth.hash_password(pwd),
                role=role, subscription_tier=tier,
                email_verified=True, active=True,
                is_demo=(role == "demo"),
            )
            db.add(user)
        print("=" * 60)

        db.commit()
        print(f"Seeded {len(seed_users)} users successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
