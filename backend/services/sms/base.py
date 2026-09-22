"""Base SMS Provider Interface and Data Models.

Defines the clean abstraction layer for SMS delivery so providers like
Twilio, MSG91, or Fast2SMS can be plugged in without changing business logic.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SMSDeliveryResult(BaseModel):
    """Result of an SMS transmission attempt."""
    success: bool
    provider: str = "mock"
    delivery_status: str = "MOCK_SMS_DELIVERY"  # 'MOCK_SMS_DELIVERY', 'SENT', 'FAILED'
    message_id: Optional[str] = None
    to_phone: str
    character_count: int = 0
    error: Optional[str] = None
    delivered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BaseSMSProvider(ABC):
    """Abstract SMS Gateway Provider Interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier string."""
        pass

    @abstractmethod
    async def send_sms(
        self,
        to_phone: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SMSDeliveryResult:
        """Dispatches an SMS message or logs it in mock mode."""
        pass
