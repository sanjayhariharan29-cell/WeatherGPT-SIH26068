"""Device Token Registration & Push Notifications API.

WeatherGPT / SkyZen SIH26068.
Strictly restricted to Firebase Cloud Messaging (FCM).
Provides secure device token management (registration, refresh, deletion),
user ownership isolation, and controlled auditable test notification dispatch.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User, DeviceToken, AlertDeliveryLog
from backend.core.security import get_current_user
from backend.schemas.notifications import (
    DeviceTokenRegisterRequest,
    DeviceTokenDeleteRequest,
    DeviceTokenResponse,
    DeviceTokenListResponse,
    TestNotificationRequest,
    TestNotificationResponse
)
from backend.services.notification_service import NotificationService

logger = logging.getLogger("weathergpt.api.notifications")

router = APIRouter(prefix="/notifications", tags=["Notifications"])
notification_service = NotificationService()


@router.post("/devices", response_model=DeviceTokenResponse, status_code=status.HTTP_200_OK)
async def register_device_token(
    req: DeviceTokenRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Registers or refreshes an FCM device token for the authenticated user.

    Security & Lifecycle Invariants:
    1. Authenticated user identity is strictly enforced.
    2. A token belongs to a device installation.
    3. If token already belongs to the current user, it is activated and timestamps updated.
    4. If token previously belonged to another user (e.g. device transferred or account switched),
       ownership is reassigned to the current authenticated user.
    5. Clients can never register tokens on behalf of other users.
    """
    now = datetime.now(timezone.utc)
    token_str = req.token.strip()

    # Query if token already exists in database
    existing_token = db.query(DeviceToken).filter(DeviceToken.token == token_str).first()

    if existing_token:
        # Update existing record
        existing_token.user_id = current_user.id
        existing_token.platform = req.platform
        existing_token.device_name = req.device_name or existing_token.device_name
        existing_token.is_active = True
        existing_token.updated_at = now
        db.commit()
        db.refresh(existing_token)
        logger.info(f"Device token refreshed for user {current_user.id} (platform: {req.platform})")
        return DeviceTokenResponse(
            id=existing_token.id,
            user_id=existing_token.user_id,
            token=existing_token.token,
            platform=existing_token.platform,
            device_name=existing_token.device_name,
            is_active=existing_token.is_active,
            created_at=existing_token.created_at.isoformat() if existing_token.created_at else now.isoformat(),
            updated_at=existing_token.updated_at.isoformat() if existing_token.updated_at else now.isoformat()
        )

    # Register new device token
    new_device = DeviceToken(
        user_id=current_user.id,
        token=token_str,
        platform=req.platform,
        device_name=req.device_name,
        is_active=True,
        created_at=now,
        updated_at=now
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    logger.info(f"New device token registered for user {current_user.id} (platform: {req.platform})")

    return DeviceTokenResponse(
        id=new_device.id,
        user_id=new_device.user_id,
        token=new_device.token,
        platform=new_device.platform,
        device_name=new_device.device_name,
        is_active=new_device.is_active,
        created_at=new_device.created_at.isoformat() if new_device.created_at else now.isoformat(),
        updated_at=new_device.updated_at.isoformat() if new_device.updated_at else now.isoformat()
    )


@router.get("/devices", response_model=DeviceTokenListResponse, status_code=status.HTTP_200_OK)
async def list_user_device_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all active registered device tokens strictly belonging to the authenticated user."""
    devices = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == current_user.id, DeviceToken.is_active == True)
        .order_by(DeviceToken.updated_at.desc())
        .all()
    )

    items = [
        DeviceTokenResponse(
            id=d.id,
            user_id=d.user_id,
            token=d.token,
            platform=d.platform,
            device_name=d.device_name,
            is_active=d.is_active,
            created_at=d.created_at.isoformat() if d.created_at else "",
            updated_at=d.updated_at.isoformat() if d.updated_at else ""
        )
        for d in devices
    ]

    return DeviceTokenListResponse(
        devices=items,
        total_count=len(items)
    )


@router.delete("/devices", status_code=status.HTTP_200_OK)
async def delete_device_token_body(
    req: DeviceTokenDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivates/removes a registered device token.

    Security Invariant:
    A user can NEVER delete or deactivate a device token belonging to another user.
    Attempting to do so triggers 403 Forbidden.
    """
    return await _perform_device_token_deletion(req.token, current_user, db)


@router.delete("/devices/{token:path}", status_code=status.HTTP_200_OK)
async def delete_device_token_path(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivates/removes a registered device token via URL path parameter."""
    return await _perform_device_token_deletion(token, current_user, db)


async def _perform_device_token_deletion(token: str, current_user: User, db: Session) -> Dict[str, Any]:
    token_str = token.strip()
    device = db.query(DeviceToken).filter(DeviceToken.token == token_str).first()

    if not device:
        # Idempotent response if token does not exist
        return {
            "success": True,
            "message": "Device token not found or already removed",
            "token": token_str
        }

    # Strict ownership enforcement
    if device.user_id != current_user.id:
        logger.warning(
            f"Security violation: User {current_user.id} attempted to unregister device token {device.id} "
            f"belonging to User {device.user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot unregister a device token belonging to another user"
        )

    device.is_active = False
    device.updated_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"Device token {device.id} deactivated for user {current_user.id}")

    return {
        "success": True,
        "message": "Device token deactivated successfully",
        "token": token_str
    }


@router.post("/test", response_model=TestNotificationResponse, status_code=status.HTTP_200_OK)
async def send_test_notification(
    req: TestNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dispatches a controlled test notification.

    Safety & Compliance Rules:
    1. Authenticated users only.
    2. Must NOT send real IMD alerts.
    3. Clearly marked as test notification in title, body, and payload.
    4. Audited in AlertDeliveryLog with channel='test_fcm'.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Determine target tokens
    target_tokens: List[str] = []
    if req.device_token:
        # Validate that current user owns this token
        dev = db.query(DeviceToken).filter(
            DeviceToken.token == req.device_token.strip(),
            DeviceToken.is_active == True
        ).first()

        if not dev:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified device token not found or is inactive"
            )
        if dev.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot target a device token belonging to another user"
            )
        target_tokens.append(dev.token)
    else:
        # Use all active device tokens of current user
        devs = db.query(DeviceToken).filter(
            DeviceToken.user_id == current_user.id,
            DeviceToken.is_active == True
        ).all()
        target_tokens = [d.token for d in devs]

    if not target_tokens:
        # Safe response if no active device tokens registered
        return TestNotificationResponse(
            success=True,
            message="No active device tokens found for current user. Register a device token first.",
            dispatched_count=0,
            mode="no_active_devices",
            delivery_results=[],
            timestamp=now_iso
        )

    # Format test payload
    title = f"[TEST] {req.title or 'SkyZen Test Notification'}"
    body = req.body or "Controlled test of the SkyZen emergency warning notification system."
    test_data = {
        "is_test": "true",
        "alert_type": "controlled_test",
        "sender": "SkyZen Testing Harness",
        "recipient_user_id": current_user.id,
        "dispatched_at": now_iso
    }

    multicast_result = await notification_service.send_multicast(
        tokens=target_tokens,
        title=title,
        body=body,
        data=test_data
    )

    # Handle invalid/unregistered tokens by deactivating them in database
    if multicast_result.get("unregistered_tokens"):
        for unreg_token in multicast_result["unregistered_tokens"]:
            unreg_dev = db.query(DeviceToken).filter(DeviceToken.token == unreg_token).first()
            if unreg_dev:
                unreg_dev.is_active = False
                unreg_dev.updated_at = now
        db.commit()

    # Log to audit trail
    for res in multicast_result.get("delivery_results", []):
        log_entry = AlertDeliveryLog(
            alert_id=None,
            alert_fingerprint="controlled_test_fcm",
            user_id=current_user.id,
            location_name="Test Client Device",
            channel="test_fcm",
            status="SENT" if res.get("success") else "FAILED",
            reason="user_initiated_test" if res.get("success") else res.get("error", "fcm_failure"),
            language=current_user.language or "ta",
            payload_preview=body[:100],
            delivered_at=now if res.get("success") else None,
            created_at=now
        )
        db.add(log_entry)
    db.commit()

    mode = "live_fcm" if notification_service.is_live_fcm_available() else "mock_delivery"

    return TestNotificationResponse(
        success=multicast_result.get("success", False),
        message=f"Test notification dispatched to {len(target_tokens)} device(s).",
        dispatched_count=len(target_tokens),
        mode=mode,
        delivery_results=multicast_result.get("delivery_results", []),
        timestamp=now_iso
    )
