"""Pydantic Schemas for Skizen Personalized Weather SMS Briefing & Scheduling.

Covers Phase 1 (message generation) and Phase 2 (daily scheduler, mock delivery,
briefing history, and user notification settings).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class BriefingTestRequest(BaseModel):
    """Test payload to generate a personalized briefing manually."""
    user_id: Optional[str] = Field(None, description="Optional user ID to load profile from database")
    phone_number: Optional[str] = Field(None, description="Optional phone number override")
    role: Optional[str] = Field(None, description="Role / persona: fisherman, farmer, commuter, student, outdoor_worker")
    location_name: Optional[str] = Field(None, description="City or place name override (e.g. Chennai, Coimbatore)")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Optional latitude override")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Optional longitude override")
    language: Optional[str] = Field(None, description="Language code: en, ta, hi")
    is_last_known_location: Optional[bool] = Field(False, description="Flag indicating if location is last known rather than live GPS")


class PersonalizedBriefingResponse(BaseModel):
    """Response containing the composed SMS text (<320 chars) and structured reasoning metadata."""
    user_id: Optional[str] = None
    mobile_number: Optional[str] = None
    role: str
    location_name: str
    is_last_known_location: bool
    language: str
    notification_enabled: bool
    risk_level: str  # LOW, MODERATE, HIGH
    risk_status_label: str  # e.g. "🟢 LOW/FAVORABLE (Skizen-derived assessment)"
    message_text: str
    character_count: int
    reasoning_bullets: List[str]
    data_freshness: str
    timestamp: str
    raw_weather: Optional[Dict[str, Any]] = None


class BriefingHistoryItem(BaseModel):
    """Single historical entry for a generated and mock-delivered briefing."""
    id: str
    user_id: str
    message_type: str  # 'daily', 'proactive', 'manual_test'
    location_name: str
    role: str
    phone_number: Optional[str] = None
    risk_level: str  # 'LOW', 'MODERATE', 'HIGH'
    risk_status_label: str
    delivery_status: str  # 'MOCK_SMS_DELIVERY', 'FAILED', 'SKIPPED'
    data_source: str
    data_freshness: str
    message_text: str
    character_count: int
    reasoning_bullets: List[str] = Field(default_factory=list)
    error_reason: Optional[str] = None
    delivered_at: Optional[str] = None
    created_at: str
    event_fingerprint: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BriefingHistoryResponse(BaseModel):
    """List response of past briefing history items."""
    items: List[BriefingHistoryItem]
    total: int


class SchedulerTriggerRequest(BaseModel):
    """Request payload to manually trigger the daily briefing scheduler."""
    user_id: Optional[str] = Field(None, description="Optional specific user ID to run for")
    force_all: Optional[bool] = Field(False, description="If True, dispatches regardless of scheduled time-of-day")


class SchedulerTriggerResponse(BaseModel):
    """Response summarizing scheduler execution."""
    dispatched_count: int
    status: str = "completed"
    results: List[Dict[str, Any]] = Field(default_factory=list)


class ProactiveCheckRequest(BaseModel):
    """Request payload to trigger proactive severe weather checks."""
    user_id: Optional[str] = Field(None, description="Optional user ID to check for")
    simulated_warning: Optional[Dict[str, Any]] = Field(None, description="Optional simulated active warning for testing")


class ProactiveCheckResponse(BaseModel):
    """Response summarizing proactive alert check execution."""
    evaluated_count: int
    alerts_triggered: int
    status: str = "completed"
    results: List[Dict[str, Any]] = Field(default_factory=list)


class BriefingSettingsUpdateRequest(BaseModel):
    """Request payload to update notification and SMS preferences."""
    daily_sms_enabled: Optional[bool] = Field(None, description="Enable daily weather SMS briefing")
    professional_advisory_enabled: Optional[bool] = Field(None, description="Enable professional role-specific advisory")
    severe_alerts_enabled: Optional[bool] = Field(None, description="Enable severe weather alerts")
    briefing_time: Optional[str] = Field(None, description="Daily briefing dispatch time in HH:MM (e.g. 07:00)")
    phone_number: Optional[str] = Field(None, description="Registered mobile number for SMS")


class BriefingSettingsResponse(BaseModel):
    """Response containing user's current briefing and notification preferences."""
    daily_sms_enabled: bool = True
    professional_advisory_enabled: bool = True
    severe_alerts_enabled: bool = True
    briefing_time: str = "07:00"
    phone_number: Optional[str] = None
    role: str = "student"
    language: str = "ta"
    last_known_location: Optional[str] = None
