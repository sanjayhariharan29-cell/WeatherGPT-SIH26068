"""Pydantic Schemas for Device Token Registration & FCM Push Notification Infrastructure.

WeatherGPT / SkyZen SIH26068.
Strictly restricted to Firebase Cloud Messaging (FCM).
"""

import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class DeviceTokenRegisterRequest(BaseModel):
    """Schema for registering or refreshing a client FCM device token."""
    token: str = Field(..., description="Firebase Cloud Messaging (FCM) registration token")
    platform: str = Field(default="android", description="Device platform: android, ios, or web")
    device_name: Optional[str] = Field(default=None, description="Human-readable device model or browser client identifier")

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        token = v.strip()
        if not token:
            raise ValueError("Device token cannot be empty")
        if len(token) < 10:
            raise ValueError("Device token is too short to be a valid FCM token")
        if len(token) > 4096:
            raise ValueError("Device token exceeds maximum permissible length")
        # Ensure no control characters or suspicious injection patterns
        if any(c in token for c in ["\r", "\n", "\0", "<", ">", '"', "'"]):
            raise ValueError("Device token contains invalid characters")
        return token

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        plat = v.lower().strip()
        allowed = ["android", "ios", "web"]
        if plat not in allowed:
            raise ValueError(f"Unsupported platform '{v}'. Permitted platforms: {', '.join(allowed)}")
        return plat


class DeviceTokenDeleteRequest(BaseModel):
    """Schema for removing/deactivating a client device token."""
    token: str = Field(..., description="Device token to unregister")

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        token = v.strip()
        if not token:
            raise ValueError("Device token cannot be empty")
        return token


class DeviceTokenResponse(BaseModel):
    """Normalized response schema for a registered device token."""
    id: str
    user_id: str
    token: str
    platform: str
    device_name: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class DeviceTokenListResponse(BaseModel):
    """List of device tokens registered to the authenticated user."""
    devices: List[DeviceTokenResponse] = Field(default_factory=list)
    total_count: int = 0


class TestNotificationRequest(BaseModel):
    """Controlled test notification dispatch request."""
    title: Optional[str] = Field(default="SkyZen Test Warning Notification", description="Test notification title")
    body: Optional[str] = Field(default="This is a controlled verification test of the SkyZen emergency warning notification system.", description="Test notification body")
    device_token: Optional[str] = Field(default=None, description="Target specific device token (optional, defaults to user's registered active devices)")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> str:
        title = (v or "").strip()
        if not title:
            return "SkyZen Test Warning Notification"
        if len(title) > 100:
            return title[:100]
        return title

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: Optional[str]) -> str:
        body = (v or "").strip()
        if not body:
            return "This is a controlled test of SkyZen push notification infrastructure."
        if len(body) > 255:
            return body[:255]
        return body


class TestNotificationResponse(BaseModel):
    """Structured response contract for controlled test notification execution."""
    success: bool
    message: str
    dispatched_count: int
    mode: str
    delivery_results: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str
