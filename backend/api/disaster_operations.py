"""Disaster and Government Operations Dashboard API.

Exposes administrative disaster-weather monitoring endpoints strictly isolated from
public user functionality:
- Active/Scheduled/Expired warning lifecycle
- Warning severity and affected area tracking
- Notification targeting & FCM delivery status
- Genuine geometry map payload / text fallback
- Provider and infrastructure health monitoring
- RBAC enforcement (admin / operations only)
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User
from backend.core.security import get_current_user
from backend.services.disaster_operations_service import disaster_operations_service

logger = logging.getLogger("weathergpt.api.disaster_operations")

router = APIRouter(prefix="/operations/disaster", tags=["disaster-operations"])


def require_operations_access(current_user: User = Depends(get_current_user)) -> User:
    """RBAC guard: Strictly requires 'admin' or 'developer' role.
    
    1. Unauthenticated requests -> 401 Unauthorized.
    2. Regular users ('user') -> 403 Forbidden.
    3. Admins/Developers -> Authorized.
    """
    if current_user.role not in ("admin", "developer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative access required. Insufficient permissions for Disaster Operations."
        )
    return current_user


@router.get(
    "/dashboard",
    summary="Disaster Operations Center Dashboard Overview",
    response_description="Consolidated operations telemetry, warning lifecycle tallies, and health states"
)
def get_operations_dashboard(
    current_user: User = Depends(require_operations_access),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Retrieves operational overview for disaster management authorities."""
    return disaster_operations_service.get_dashboard_summary(db=db)


@router.get(
    "/warnings",
    summary="Filtered Disaster Warnings List",
    response_description="List of disaster warnings matching administrative criteria"
)
def get_operational_warnings(
    district: Optional[str] = Query(None, description="Filter by district name or substring"),
    warning_type: Optional[str] = Query(None, description="Filter by category (heavy_rain, thunderstorm, cyclone, etc.)"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, extreme)"),
    lifecycle: Optional[str] = Query(None, description="Filter by lifecycle (scheduled, active, expired, all)"),
    date_from: Optional[datetime] = Query(None, description="Filter warnings issued after ISO datetime"),
    date_to: Optional[datetime] = Query(None, description="Filter warnings issued before ISO datetime"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset index"),
    current_user: User = Depends(require_operations_access),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Filters disaster warnings with lifecycle states, geometry validation, and delivery metrics."""
    return disaster_operations_service.get_warnings(
        db=db,
        district=district,
        warning_type=warning_type,
        severity=severity,
        lifecycle=lifecycle,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset
    )


@router.get(
    "/warnings/{warning_id}",
    summary="Warning Operational Detail",
    response_description="Detailed view of a single warning with targeting audit and geometry"
)
def get_warning_detail(
    warning_id: str,
    current_user: User = Depends(require_operations_access),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Retrieves comprehensive operational detail and delivery logs for a specific warning."""
    detail = disaster_operations_service.get_warning_detail(db=db, warning_id=warning_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disaster warning with ID '{warning_id}' not found."
        )
    return detail


@router.get(
    "/notifications",
    summary="Notification Targeting & FCM Delivery Audit Logs",
    response_description="Detailed notification logs for disaster warnings"
)
def get_notification_logs(
    alert_id: Optional[str] = Query(None, description="Filter by alert ID"),
    delivery_status: Optional[str] = Query(None, alias="status", description="Filter by status (SENT, SKIPPED, FAILED)"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    limit: int = Query(50, ge=1, le=200, description="Limit records"),
    offset: int = Query(0, ge=0, description="Offset records"),
    current_user: User = Depends(require_operations_access),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Audits notification delivery tracking, skip reasons, and FCM dispatch states."""
    return disaster_operations_service.get_notification_audit_logs(
        db=db,
        alert_id=alert_id,
        status=delivery_status,
        district=district,
        limit=limit,
        offset=offset
    )


@router.get(
    "/health",
    summary="Disaster Pipeline Provider & Infrastructure Health",
    response_description="Sanitized health telemetry of IMD, Open-Meteo, DB, and FCM"
)
def get_operations_health(
    current_user: User = Depends(require_operations_access),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Health check for weather providers and notification infrastructure."""
    return disaster_operations_service.get_system_provider_health(db=db)


@router.get(
    "/ui",
    summary="Disaster Operations Web Dashboard HTML",
    response_class=HTMLResponse
)
def get_operations_dashboard_ui(
    current_user: User = Depends(require_operations_access)
) -> HTMLResponse:
    """Renders the administrative disaster monitoring HTML interface."""
    html_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "frontend",
        "operations_dashboard.html"
    )
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>SkyZen Disaster & Operations Dashboard</h1><p>UI template ready.</p>",
        status_code=200
    )
