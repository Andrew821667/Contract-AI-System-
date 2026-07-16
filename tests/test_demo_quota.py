# -*- coding: utf-8 -*-
"""Personal demo quotas are lifetime limits from the invitation."""

from src.models.auth_models import User
from src.models.database import Contract
from src.services.auth_service import AuthService
from src.services.quota_service import get_contract_quota, get_llm_quota


def _demo_user(db, max_contracts=2, max_llm=4):
    auth = AuthService(db)
    admin, error = auth.register_user(
        email="quota-admin@example.com",
        name="Quota Admin",
        password="AdminPass123!",
        role="admin",
        subscription_tier="enterprise",
        send_verification=False,
    )
    assert admin is not None, error
    token = auth.generate_demo_token(
        created_by_user_id=admin.id,
        max_contracts=max_contracts,
        max_llm_requests=max_llm,
        recipient_email="quota-demo@example.com",
    )
    result, error = auth.activate_demo_token(
        token=token.token,
        email="quota-demo@example.com",
        name="Quota Demo",
    )
    assert result is not None, error
    return db.query(User).filter(User.email == "quota-demo@example.com").one()


def test_contract_limit_comes_from_invitation_and_does_not_reset_monthly(test_db):
    user = _demo_user(test_db, max_contracts=2)
    test_db.add_all([
        Contract(file_name="one.pdf", file_path="/tmp/one.pdf", document_type="contract", status="completed", assigned_to=user.id),
        Contract(file_name="two.pdf", file_path="/tmp/two.pdf", document_type="contract", status="uploaded", assigned_to=user.id),
    ])
    test_db.commit()

    quota = get_contract_quota(test_db, user)
    assert quota == {"used": 2, "limit": 2, "period": "demo"}


def test_llm_limit_uses_total_demo_requests(test_db):
    user = _demo_user(test_db, max_llm=4)
    user.llm_requests_today = 1
    user.llm_requests_total = 3
    test_db.commit()

    quota = get_llm_quota(test_db, user)
    assert quota == {"used": 3, "limit": 4, "period": "demo"}
