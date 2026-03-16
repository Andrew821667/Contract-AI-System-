"""
Policy Engine — MultiLevelPolicyResolver.

Каскадная проверка политик: platform → tenant → org → branch → document → user.
Реализует IPolicyResolver.
"""

from __future__ import annotations

import fnmatch
from typing import Any

from sqlalchemy.orm import Session

from src.core.base import PolicyDecision, PolicyLevel
from .models import ActionPermission, ApprovalRule, Policy


# Порядок каскада (от общего к частному)
_LEVEL_ORDER: list[str] = [level.value for level in PolicyLevel]


class MultiLevelPolicyResolver:
    """
    Каскадный резолвер политик.

    Алгоритм:
    1. Собираем все активные политики для всех уровней (от platform до user).
    2. Сортируем по каскаду (platform первый, user последний).
    3. Внутри уровня — по priority (больший выигрывает).
    4. Каждый более специфичный уровень может переопределить решение.
    5. Проверяем approval rules — нужно ли human approval.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    async def resolve(
        self,
        action: str,
        user_id: str,
        organization_id: str | None = None,
        document_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Проверить, разрешено ли действие."""
        context = context or {}

        # Собираем все применимые политики
        policies = self._collect_applicable_policies(
            user_id=user_id,
            organization_id=organization_id,
            document_id=document_id,
        )

        if not policies:
            # Нет политик — разрешаем по умолчанию (platform default)
            return PolicyDecision(
                allowed=True,
                reason="Нет применимых политик — разрешено по умолчанию",
            )

        # Каскадная проверка
        decision = self._cascade_resolve(policies, action, context)

        # Проверяем approval rules
        approval = self._check_approval_rules(policies, action)
        if approval:
            decision.requires_approval = True
            decision.approval_rule_id = approval.id

        return decision

    def _collect_applicable_policies(
        self,
        user_id: str,
        organization_id: str | None,
        document_id: str | None,
    ) -> list[Policy]:
        """Собрать все применимые политики по всем уровням каскада."""
        scope_filters = [
            # Platform-level (scope_id IS NULL)
            (Policy.level == "platform", Policy.scope_id.is_(None)),
        ]

        if organization_id:
            # Tenant и Organization уровень
            scope_filters.append(
                (Policy.level == "tenant", Policy.scope_id == organization_id)
            )
            scope_filters.append(
                (Policy.level == "organization", Policy.scope_id == organization_id)
            )

        if document_id:
            scope_filters.append(
                (Policy.level == "document", Policy.scope_id == document_id)
            )

        # User-level
        scope_filters.append(
            (Policy.level == "user", Policy.scope_id == user_id)
        )

        from sqlalchemy import or_, and_

        conditions = [and_(level_cond, scope_cond) for level_cond, scope_cond in scope_filters]

        policies = (
            self.db.query(Policy)
            .filter(Policy.active.is_(True), or_(*conditions))
            .all()
        )

        # Сортируем: по каскаду, затем по priority
        def sort_key(p: Policy) -> tuple[int, int]:
            level_idx = _LEVEL_ORDER.index(p.level) if p.level in _LEVEL_ORDER else 99
            return (level_idx, p.priority)

        policies.sort(key=sort_key)
        return policies

    def _cascade_resolve(
        self,
        policies: list[Policy],
        action: str,
        context: dict[str, Any],
    ) -> PolicyDecision:
        """Применить каскад политик и вернуть финальное решение."""
        # Начинаем с «разрешено»
        current_decision = PolicyDecision(
            allowed=True,
            reason="Разрешено по умолчанию",
        )

        for policy in policies:
            decision = self._evaluate_policy(policy, action, context)
            if decision is not None:
                current_decision = decision

        return current_decision

    def _evaluate_policy(
        self,
        policy: Policy,
        action: str,
        context: dict[str, Any],
    ) -> PolicyDecision | None:
        """
        Проверить одну политику. Возвращает решение или None (если не применима).
        """
        rules: dict[str, Any] = policy.rules or {}

        # --- tool_access ---
        if policy.policy_type == "tool_access":
            tool_id = action.replace("tool.", "").replace(".execute", "")
            denied = rules.get("denied_tools", [])
            allowed = rules.get("allowed_tools")

            if tool_id in denied:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Инструмент '{tool_id}' запрещён политикой '{policy.name}'",
                    policy_id=policy.id,
                    level=PolicyLevel(policy.level),
                )
            if allowed is not None and tool_id not in allowed:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Инструмент '{tool_id}' не в списке разрешённых (политика '{policy.name}')",
                    policy_id=policy.id,
                    level=PolicyLevel(policy.level),
                )

        # --- ai_autonomy ---
        elif policy.policy_type == "ai_autonomy":
            max_level = rules.get("max_autonomy_level", "autonomous")
            _levels = ["advisor", "copilot", "processor", "autonomous"]
            requested = context.get("autonomy_level", "advisor")
            if requested in _levels and max_level in _levels:
                if _levels.index(requested) > _levels.index(max_level):
                    return PolicyDecision(
                        allowed=False,
                        reason=f"Уровень автономности '{requested}' превышает максимальный '{max_level}' (политика '{policy.name}')",
                        policy_id=policy.id,
                        level=PolicyLevel(policy.level),
                    )

        # --- action_approval ---
        elif policy.policy_type == "action_approval":
            blocked_actions = rules.get("blocked_actions", [])
            if action in blocked_actions:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Действие '{action}' заблокировано политикой '{policy.name}'",
                    policy_id=policy.id,
                    level=PolicyLevel(policy.level),
                )

        # --- data_sensitivity ---
        elif policy.policy_type == "data_sensitivity":
            max_sensitivity = rules.get("max_sensitivity", "restricted")
            _sens = ["normal", "confidential", "restricted"]
            requested = context.get("sensitivity", "normal")
            if requested in _sens and max_sensitivity in _sens:
                if _sens.index(requested) > _sens.index(max_sensitivity):
                    return PolicyDecision(
                        allowed=False,
                        reason=f"Чувствительность '{requested}' превышает допустимую '{max_sensitivity}'",
                        policy_id=policy.id,
                        level=PolicyLevel(policy.level),
                    )

        # --- action_permissions ---
        for perm in policy.action_permissions:
            if not perm.active:
                continue
            if perm.action_type == action or fnmatch.fnmatch(action, perm.action_type):
                user_role = context.get("user_role")
                if user_role and user_role not in (perm.allowed_roles or []):
                    return PolicyDecision(
                        allowed=False,
                        reason=f"Роль '{user_role}' не имеет прав на '{action}' (политика '{policy.name}')",
                        policy_id=policy.id,
                        level=PolicyLevel(policy.level),
                    )

        return None  # Политика не повлияла на решение

    def _check_approval_rules(
        self,
        policies: list[Policy],
        action: str,
    ) -> ApprovalRule | None:
        """Проверить, есть ли approval rule для данного действия."""
        for policy in reversed(policies):  # Более специфичные (user) проверяются первыми
            for rule in policy.approval_rules:
                if not rule.active:
                    continue
                if fnmatch.fnmatch(action, rule.action_pattern):
                    return rule
        return None
