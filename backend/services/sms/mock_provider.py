"""Mock SMS Provider for Skizen Personalized Weather SMS.

Honest, DLT/TRAI-compliant simulated SMS gateway that logs messages and marks them
as MOCK_SMS_DELIVERY without claiming or implying transmission through telecom carriers.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from backend.services.sms.base import BaseSMSProvider, SMSDeliveryResult

logger = logging.getLogger("weathergpt.services.sms.mock")


class MockSMSProvider(BaseSMSProvider):
    """Honest Mock SMS Provider that logs SMS payloads cleanly."""

    @property
    def name(self) -> str:
        return "mock_logger"

    async def send_sms(
        self,
        to_phone: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SMSDeliveryResult:
        """Simulates SMS transmission honestly by logging the full payload."""
        meta = metadata or {}
        msg_id = f"mock-sms-{uuid.uuid4()}"
        char_count = len(message)

        # Log with explicit, honest indicator
        try:
            logger.info(
                "[MOCK_SMS_DELIVERY] Recipient: %s | Chars: %d | Role: %s | Location: %s | Risk: %s\n"
                "--- SMS BODY ---\n%s\n----------------",
                to_phone or "No Phone Provided",
                char_count,
                meta.get("role", "user"),
                meta.get("location_name", "Unknown"),
                meta.get("risk_level", "UNKNOWN"),
                message
            )
        except UnicodeEncodeError:
            logger.info(
                "[MOCK_SMS_DELIVERY] Recipient: %s | Chars: %d | Role: %s | Location: %s | Risk: %s\n"
                "--- SMS BODY ---\n%s\n----------------",
                to_phone or "No Phone Provided",
                char_count,
                meta.get("role", "user"),
                meta.get("location_name", "Unknown"),
                meta.get("risk_level", "UNKNOWN"),
                message.encode("ascii", "replace").decode("ascii")
            )

        return SMSDeliveryResult(
            success=True,
            provider=self.name,
            delivery_status="MOCK_SMS_DELIVERY",
            message_id=msg_id,
            to_phone=to_phone or "Simulated",
            character_count=char_count,
            delivered_at=datetime.now(timezone.utc)
        )
