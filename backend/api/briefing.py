"""Personalized Weather SMS Briefing API Router.

Phase 1 & 2: Test triggers, authenticated previews, daily scheduler execution,
briefing notification history, and user SMS settings.
"""

import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User, UserPreference, BriefingDeliveryLog
from backend.core.security import get_current_user
from backend.schemas.briefing import (
    BriefingTestRequest,
    PersonalizedBriefingResponse,
    BriefingHistoryItem,
    BriefingHistoryResponse,
    SchedulerTriggerRequest,
    SchedulerTriggerResponse,
    ProactiveCheckRequest,
    ProactiveCheckResponse,
    BriefingSettingsUpdateRequest,
    BriefingSettingsResponse
)
from backend.services.briefing_service import PersonalizedBriefingService
from backend.services.briefing_scheduler import scheduler_service

logger = logging.getLogger("weathergpt.api.briefing")

router = APIRouter(prefix="/briefing", tags=["Personalized Briefing SMS"])
briefing_service = PersonalizedBriefingService()


@router.post("/test", response_model=PersonalizedBriefingResponse, status_code=status.HTTP_200_OK)
async def test_generate_briefing(
    req: BriefingTestRequest,
    db: Session = Depends(get_db)
):
    """Test and debug endpoint to generate personalized weather SMS briefings.
    
    Can be invoked with a user_id or with explicit test overrides (role, location, language).
    Does NOT require live SMS delivery or external carrier gateways.
    """
    try:
        response = await briefing_service.generate_personalized_briefing(
            user_id=req.user_id,
            db_session=db,
            override_role=req.role,
            override_location=req.location_name,
            override_latitude=req.latitude,
            override_longitude=req.longitude,
            override_language=req.language,
            override_phone=req.phone_number,
            is_last_known_override=req.is_last_known_location
        )
        return response
    except Exception as e:
        logger.exception("Failed to generate test briefing: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Briefing generation failed: {str(e)}"
        )


@router.get("/preview", response_model=PersonalizedBriefingResponse, status_code=status.HTTP_200_OK)
async def preview_authenticated_briefing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generates a personalized briefing for the currently authenticated user.
    
    Uses existing user profile, registered phone, role/persona, language, and latest location.
    """
    try:
        response = await briefing_service.generate_personalized_briefing(
            user_id=current_user.id,
            db_session=db
        )
        return response
    except Exception as e:
        logger.exception("Failed to preview briefing for user %s: %s", current_user.id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Briefing preview failed: {str(e)}"
        )


@router.post("/scheduler/trigger", response_model=SchedulerTriggerResponse, status_code=status.HTTP_200_OK)
async def trigger_scheduler_job(
    req: SchedulerTriggerRequest,
    db: Session = Depends(get_db)
):
    """Manually triggers the daily briefing scheduler and mock dispatch pipeline.
    
    Can run for a specific user_id or all enabled users with force_all=True.
    """
    try:
        results = await scheduler_service.trigger_daily_run(
            db=db,
            target_user_id=req.user_id,
            force_time=req.force_all
        )
        return SchedulerTriggerResponse(
            dispatched_count=len(results),
            status="completed",
            results=results
        )
    except Exception as e:
        logger.exception("Scheduler execution failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scheduler trigger failed: {str(e)}"
        )


@router.post("/proactive/check", response_model=ProactiveCheckResponse, status_code=status.HTTP_200_OK)
async def check_proactive_alerts(
    req: ProactiveCheckRequest,
    db: Session = Depends(get_db)
):
    """Evaluates developing weather conditions or simulated warnings and dispatches proactive severe alerts.
    
    Applies strict deduplication and cooldown: ongoing events for a user are suppressed unless severity escalates.
    """
    try:
        results = await scheduler_service.check_and_dispatch_proactive_alerts(
            db=db,
            target_user_id=req.user_id,
            simulated_alert=req.simulated_warning
        )
        triggered = sum(1 for r in results if r.get("status") == "MOCK_SMS_DELIVERY")
        return ProactiveCheckResponse(
            evaluated_count=len(results),
            alerts_triggered=triggered,
            status="completed",
            results=results
        )
    except Exception as e:
        logger.exception("Proactive alert check failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proactive alert check failed: {str(e)}"
        )


@router.get("/history", response_model=BriefingHistoryResponse, status_code=status.HTTP_200_OK)
async def get_briefing_history(
    user_id: Optional[str] = Query(None, description="Target user ID (for debugging/admin)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Retrieves briefing delivery logs for the user (ordered newest first)."""
    try:
        query = db.query(BriefingDeliveryLog)
        if user_id:
            query = query.filter(BriefingDeliveryLog.user_id == user_id)
        
        query = query.order_by(BriefingDeliveryLog.created_at.desc())
        total = query.count()
        logs = query.limit(limit).all()

        items: List[BriefingHistoryItem] = []
        for log in logs:
            bullets = []
            if log.reasoning_bullets:
                try:
                    bullets = json.loads(log.reasoning_bullets)
                except Exception:
                    bullets = [log.reasoning_bullets]

            items.append(
                BriefingHistoryItem(
                    id=log.id,
                    user_id=log.user_id,
                    message_type=log.message_type,
                    location_name=log.location_name,
                    role=log.role,
                    phone_number=log.phone_number,
                    risk_level=log.risk_level,
                    risk_status_label=log.risk_status_label,
                    delivery_status=log.delivery_status,
                    data_source=log.data_source,
                    data_freshness=log.data_freshness,
                    message_text=log.message_text,
                    character_count=log.character_count,
                    reasoning_bullets=bullets,
                    error_reason=log.error_reason,
                    delivered_at=log.delivered_at.isoformat() if log.delivered_at else None,
                    created_at=log.created_at.isoformat() if log.created_at else "",
                    event_fingerprint=log.event_fingerprint
                )
            )

        return BriefingHistoryResponse(items=items, total=total)
    except Exception as e:
        logger.exception("Failed to retrieve briefing history: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"History fetch failed: {str(e)}"
        )


@router.get("/settings", response_model=BriefingSettingsResponse, status_code=status.HTTP_200_OK)
async def get_briefing_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves briefing and notification settings for the authenticated user."""
    pref = current_user.preferences
    return BriefingSettingsResponse(
        daily_sms_enabled=bool(pref.daily_sms_enabled) if (pref and pref.daily_sms_enabled is not None) else True,
        professional_advisory_enabled=bool(pref.professional_advisory_enabled) if (pref and pref.professional_advisory_enabled is not None) else True,
        severe_alerts_enabled=bool(pref.severe_alerts_enabled) if (pref and pref.severe_alerts_enabled is not None) else True,
        briefing_time=pref.briefing_time if (pref and pref.briefing_time) else "07:00",
        phone_number=current_user.phone_number,
        role=current_user.persona or "student",
        language=current_user.language or "ta",
        last_known_location=pref.last_known_location if pref else None
    )


@router.put("/settings", response_model=BriefingSettingsResponse, status_code=status.HTTP_200_OK)
async def update_briefing_settings(
    req: BriefingSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates briefing and notification preferences for the authenticated user."""
    if not current_user.preferences:
        pref = UserPreference(
            user_id=current_user.id,
            persona=current_user.persona or "student",
            daily_sms_enabled=req.daily_sms_enabled if req.daily_sms_enabled is not None else True,
            professional_advisory_enabled=req.professional_advisory_enabled if req.professional_advisory_enabled is not None else True,
            severe_alerts_enabled=req.severe_alerts_enabled if req.severe_alerts_enabled is not None else True,
            briefing_time=req.briefing_time or "07:00"
        )
        db.add(pref)
    else:
        pref = current_user.preferences
        if req.daily_sms_enabled is not None:
            pref.daily_sms_enabled = req.daily_sms_enabled
        if req.professional_advisory_enabled is not None:
            pref.professional_advisory_enabled = req.professional_advisory_enabled
        if req.severe_alerts_enabled is not None:
            pref.severe_alerts_enabled = req.severe_alerts_enabled
        if req.briefing_time is not None:
            pref.briefing_time = req.briefing_time

    if req.phone_number is not None:
        current_user.phone_number = req.phone_number

    db.commit()
    db.refresh(current_user)

    return await get_briefing_settings(current_user=current_user, db=db)
