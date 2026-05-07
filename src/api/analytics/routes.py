"""
Analytics API Endpoints

Provides access to analytics dashboard data, metrics, and insights.

Endpoints:
- GET /api/v1/analytics/dashboard - Get dashboard summary
- GET /api/v1/analytics/risks/trends - Get risk trends
- GET /api/v1/analytics/costs - Get cost analysis
- GET /api/v1/analytics/productivity - Get productivity metrics
- POST /api/v1/analytics/export - Export analytics report
- POST /api/v1/analytics/track - Track custom metric

Author: AI Contract System
"""

import time
from typing import Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.services.analytics_service import get_analytics_service, MetricType
from src.models.database import get_db
from src.models.auth_models import User
from src.api.dependencies import get_current_user
from sqlalchemy.orm import Session


# ── Analytics cache (5 min TTL) ──────────────────────────────────────────
# Dashboard queries are expensive (multiple aggregations). Cache per user+period.
_ANALYTICS_CACHE_TTL = 300  # 5 minutes
_analytics_cache: dict[str, tuple[Any, float]] = {}  # key → (data, expires_at)
_ANALYTICS_CACHE_MAX = 64


def _analytics_cache_get(key: str) -> Any | None:
    entry = _analytics_cache.get(key)
    if entry and entry[1] > time.time():
        return entry[0]
    _analytics_cache.pop(key, None)
    return None


def _analytics_cache_set(key: str, data: Any) -> None:
    if len(_analytics_cache) >= _ANALYTICS_CACHE_MAX:
        # Evict expired
        now = time.time()
        expired = [k for k, v in _analytics_cache.items() if v[1] <= now]
        for k in expired:
            del _analytics_cache[k]
    _analytics_cache[key] = (data, time.time() + _ANALYTICS_CACHE_TTL)


# Router
router = APIRouter(tags=["analytics"])


# Request/Response Models
class DashboardRequest(BaseModel):
    """Dashboard request"""
    period_days: int = Field(default=30, ge=1, le=365)
    user_id: Optional[str] = None


class DashboardResponse(BaseModel):
    """Dashboard response with all analytics data"""
    period: dict
    headline_metrics: dict
    risk_trends: list
    cost_analysis: dict
    productivity: dict
    top_risks: list
    risk_distribution: list
    recommendations: list
    generated_at: str


class TrackMetricRequest(BaseModel):
    """Track custom metric request"""
    name: str = Field(..., min_length=1, max_length=100)
    value: float
    unit: str = Field(..., min_length=1, max_length=20)
    metric_type: MetricType


class ExportRequest(BaseModel):
    """Export analytics report request"""
    format: str = Field(default='json')
    period_days: int = Field(default=30, ge=1, le=365)
    user_id: Optional[str] = None


# Endpoints

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics dashboard summary

    Returns comprehensive analytics including:
    - Headline metrics (contracts, time saved, costs)
    - Risk trends over time
    - Cost analysis (LLM usage)
    - Productivity metrics
    - Top 10 risks
    - Risk distribution by category
    - Actionable recommendations

    **Access:** Requires authentication
    """
    # Check cache (5 min TTL per user+period)
    cache_key = f"dashboard:{current_user.id}:{period_days}"
    cached = _analytics_cache_get(cache_key)
    if cached:
        return cached

    analytics = get_analytics_service(db)

    dashboard_data = analytics.get_dashboard_summary(
        user_id=current_user.id,
        period_days=period_days
    )

    _analytics_cache_set(cache_key, dashboard_data)
    return dashboard_data


@router.get("/risks/trends")
async def get_risk_trends(
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get risk trends over time

    Returns daily/weekly risk statistics including count by severity level.

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    # Use internal method to get just risk trends
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    trends = analytics._calculate_risk_trends(start_date, end_date, current_user.id)

    return {
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': period_days
        },
        'trends': [asdict(t) for t in trends]
    }


@router.get("/costs")
async def get_cost_analysis(
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get cost analysis (LLM usage, ML savings)

    Returns:
    - Total LLM costs
    - Token usage
    - ML predictor savings
    - Cost per contract
    - Estimated monthly cost

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    costs = analytics._calculate_cost_analysis(start_date, end_date, current_user.id)

    return asdict(costs)


@router.get("/productivity")
async def get_productivity_metrics(
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get productivity metrics

    Returns:
    - Contracts analyzed
    - Time saved (hours)
    - ROI multiplier
    - Automated tasks count
    - Average analysis time

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    productivity = analytics._calculate_productivity_metrics(
        start_date, end_date, current_user.id
    )

    return asdict(productivity)


@router.post("/export")
async def export_analytics(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export analytics report

    Generates downloadable report in requested format (JSON, CSV, PDF).

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    try:
        filepath = analytics.export_analytics_report(
            format=request.format,
            period_days=request.period_days,
            user_id=current_user.id
        )

        if not filepath or not os.path.exists(filepath):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate {request.format.upper()} report"
            )

        # Return file for download
        return FileResponse(
            path=filepath,
            filename=os.path.basename(filepath),
            media_type=f"application/{request.format}"
        )

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/track")
async def track_metric(
    request: TrackMetricRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track custom metric

    Allows tracking of custom business metrics for analytics.

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    analytics.track_metric(
        name=request.name,
        value=request.value,
        unit=request.unit,
        metric_type=request.metric_type
    )

    return {
        'success': True,
        'message': f'Metric "{request.name}" tracked successfully'
    }


@router.get("/top-risks")
async def get_top_risks(
    limit: int = Query(default=10, ge=1, le=50),
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get most common risks detected

    Returns top N risks by frequency with severity and trend information.

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    top_risks = analytics._get_top_risks(
        start_date, end_date, current_user.id, limit=limit
    )

    return {
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        },
        'top_risks': top_risks
    }


# Import needed for datetime
from datetime import timedelta
from dataclasses import asdict
import os
from loguru import logger
from sqlalchemy import func


@router.get("/personal")
async def get_personal_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Личная статистика пользователя.

    Агрегированные метрики за всё время + за последний месяц.
    """
    from src.models.database import Contract
    from src.models.analyzer_models import ContractRisk

    contract_owner_filter = Contract.assigned_to == current_user.id

    # Contracts total
    total_contracts = db.query(func.count(Contract.id)).filter(
        contract_owner_filter
    ).scalar() or 0

    # Contracts this month
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_contracts = db.query(func.count(Contract.id)).filter(
        contract_owner_filter,
        Contract.created_at >= month_start
    ).scalar() or 0

    # Risks found
    total_risks = db.query(func.count(ContractRisk.id)).join(
        Contract, Contract.id == ContractRisk.contract_id
    ).filter(
        contract_owner_filter
    ).scalar() or 0

    # Risks by severity
    risk_by_severity = dict(
        db.query(ContractRisk.severity, func.count(ContractRisk.id)).join(
            Contract, Contract.id == ContractRisk.contract_id
        ).filter(
            contract_owner_filter
        ).group_by(ContractRisk.severity).all()
    )

    return {
        "total_contracts": total_contracts,
        "month_contracts": month_contracts,
        "contracts_today": current_user.contracts_today or 0,
        "llm_requests_today": current_user.llm_requests_today or 0,
        "total_risks": total_risks,
        "risks_by_severity": {
            "critical": risk_by_severity.get("critical", 0),
            "high": risk_by_severity.get("high", 0),
            "medium": risk_by_severity.get("medium", 0),
            "low": risk_by_severity.get("low", 0),
        },
        "subscription_tier": current_user.subscription_tier,
    }


@router.get("/group")
async def get_group_stats(
    org_id: str = Query(..., description="ID организации"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Групповая статистика организации.

    Доступна только участникам организации.
    """
    from src.core.identity_org.models import OrganizationMembership
    from src.models.database import Contract
    from src.models.analyzer_models import ContractRisk

    # Verify membership
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == current_user.id,
        OrganizationMembership.org_id == org_id,
        OrganizationMembership.active == True
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этой организации")

    # Get all org member IDs
    member_ids = [
        m.user_id for m in db.query(OrganizationMembership.user_id).filter(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.active == True
        ).all()
    ]

    # Contracts total for org
    total_contracts = db.query(func.count(Contract.id)).filter(
        Contract.assigned_to.in_(member_ids)
    ).scalar() or 0

    # This month
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_contracts = db.query(func.count(Contract.id)).filter(
        Contract.assigned_to.in_(member_ids),
        Contract.created_at >= month_start
    ).scalar() or 0

    # Risks total
    total_risks = db.query(func.count(ContractRisk.id)).join(
        Contract, Contract.id == ContractRisk.contract_id
    ).filter(
        Contract.assigned_to.in_(member_ids)
    ).scalar() or 0

    # Per-member stats
    per_member = []
    for mid in member_ids:
        member_user = db.query(User).filter(User.id == mid).first()
        if not member_user:
            continue
        count = db.query(func.count(Contract.id)).filter(
            Contract.assigned_to == mid
        ).scalar() or 0
        per_member.append({
            "user_id": mid,
            "name": member_user.name,
            "contracts_count": count,
        })

    per_member.sort(key=lambda x: x["contracts_count"], reverse=True)

    return {
        "org_id": org_id,
        "total_members": len(member_ids),
        "total_contracts": total_contracts,
        "month_contracts": month_contracts,
        "total_risks": total_risks,
        "per_member": per_member,
    }
