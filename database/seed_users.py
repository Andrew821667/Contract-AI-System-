"""Seed initial users for Docker deployment."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.database import SessionLocal, Base, engine
from src.models.auth_models import User
from src.services.auth_service import AuthService

def seed():
    db = SessionLocal()
    try:
        existing = db.query(User).first()
        if existing:
            print("Users already exist, skipping seed.")
            return

        auth = AuthService(db)
        users = [
            ("admin@contractai.ru", "Администратор", os.getenv("SEED_ADMIN_PASSWORD", "Admin123!"), "admin", "enterprise"),
            ("lawyer@contractai.ru", "Юрист", os.getenv("SEED_LAWYER_PASSWORD", "Lawyer123!"), "lawyer", "pro"),
            ("vip@contractai.ru", "VIP Юрист", os.getenv("SEED_VIP_PASSWORD", "Vip12345!"), "senior_lawyer", "enterprise"),
            ("demo@contractai.ru", "Демо пользователь", os.getenv("SEED_DEMO_PASSWORD", "Demo1234!"), "demo", "demo"),
        ]
        for email, name, pwd, role, tier in users:
            user = User(
                email=email, name=name,
                password_hash=auth.hash_password(pwd),
                role=role, subscription_tier=tier,
                email_verified=True, active=True,
                is_demo=(role == "demo"),
            )
            db.add(user)
        db.commit()
        print(f"Seeded {len(users)} users successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
