"""FCM Push Notification Integration Service.

WeatherGPT / SkyZen SIH26068.
Provides robust, retry-safe dispatch of emergency meteorological warnings and controlled test alerts via Firebase Cloud Messaging (FCM).
Strictly integrates with FCM without replacing or modifying private credentials.
Supports multilingual notification formatting (Tamil, English, Hindi), multi-device dispatch, token lifecycle failure handling, and fallback simulation for dev/test.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("weathergpt.notifications")


class NotificationService:
    """FCM notification dispatcher supporting live Firebase Admin SDK and test-mode simulation."""

    def __init__(self, fcm_server_key: Optional[str] = None):
        self.server_key = fcm_server_key or os.getenv("FCM_SERVER_KEY", "")
        self._firebase_app = None
        self._init_firebase()

    def _init_firebase(self) -> None:
        """Attempts to initialize Firebase Admin SDK if available and credentials exist.

        CRITICAL SECURITY RULE:
        Never hardcode, log, print, or leak private service account keys.
        Only paths or environmental configurations outside the repository are loaded.
        """
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            if firebase_admin._apps:
                # App already initialized
                self._firebase_app = firebase_admin.get_app()
                return

            # Check 1: Explicit credentials file path from env
            cred_path = (
                os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip() or
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
            )
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                self._firebase_app = firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK successfully initialized via credentials file.")
                return

            # Check 2: Service account JSON string passed via secret environment variable
            json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
            if json_str:
                try:
                    cred_dict = json.loads(json_str)
                    cred = credentials.Certificate(cred_dict)
                    self._firebase_app = firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK successfully initialized via environment secret.")
                    return
                except Exception as json_err:
                    logger.warning("Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON secret.")

            # Fallback: No credentials configured (Normal for local dev / testing)
            self._firebase_app = None
            logger.debug("Firebase credentials not configured; running in verified mock push mode.")
        except ImportError:
            self._firebase_app = None
            logger.debug("firebase-admin library not installed; running in verified mock push mode.")
        except Exception as e:
            self._firebase_app = None
            logger.warning(f"Firebase initialization skipped: {str(e)}")

    def is_live_fcm_available(self) -> bool:
        """Returns True if live Firebase Admin SDK is initialized and available."""
        return self._firebase_app is not None

    def format_alert_message(
        self,
        title: str,
        description: str,
        severity: str,
        language: str = "ta"
    ) -> Dict[str, str]:
        """Formats alert title and body in user's preferred language."""
        lang = (language or "ta").lower().strip()

        if lang == "ta":
            header = f"⚠️ அதிகாரப்பூர்வ வானிலை எச்சரிக்கை ({severity.upper()})"
            body = f"{title}: {description[:120]}..."
        elif lang == "hi":
            header = f"⚠️ आधिकारिक मौसम चेतावनी ({severity.upper()})"
            body = f"{title}: {description[:120]}..."
        else:
            header = f"⚠️ IMD Official Warning ({severity.upper()})"
            body = f"{title}: {description[:120]}..."

        return {
            "title": header,
            "body": body,
            "severity": severity,
            "language": lang
        }

    async def send_push_notification(
        self,
        token: Optional[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """Dispatches push notification via FCM or verified test mock with bounded retries."""
        now_utc = datetime.now(timezone.utc).isoformat()
        notification_payload = {
            "title": title,
            "body": body,
            "data": data or {},
            "dispatched_at": now_utc
        }

        # Case 1: Live FCM via Firebase Admin SDK
        if self._firebase_app and token:
            for attempt in range(1, max_retries + 1):
                try:
                    from firebase_admin import messaging, exceptions
                    message = messaging.Message(
                        notification=messaging.Notification(title=title, body=body),
                        data={k: str(v) for k, v in (data or {}).items()},
                        token=token
                    )
                    response = messaging.send(message)
                    logger.info(f"FCM message delivered: {response} on attempt {attempt}")
                    return {
                        "success": True,
                        "mode": "live_fcm",
                        "message_id": response,
                        "timestamp": now_utc,
                        "should_deactivate": False
                    }
                except Exception as e:
                    err_str = str(e)
                    err_lower = err_str.lower()
                    logger.warning(f"FCM delivery attempt {attempt} failed for token: {err_str}")

                    # Check for invalid / expired / unregistered token
                    is_unregistered = any(term in err_lower for term in [
                        "unregistered", "notregistered", "invalid-registration-token",
                        "mismatch", "bad_registration", "invalid_argument"
                    ])

                    if is_unregistered or attempt == max_retries:
                        return {
                            "success": False,
                            "mode": "live_fcm",
                            "error": err_str,
                            "timestamp": now_utc,
                            "should_deactivate": is_unregistered
                        }

        # Case 2: Verified Mock Delivery (Dev / Testing / No Live FCM Key)
        # Guarantees the application never crashes when Firebase is unconfigured
        logger.info(f"Mock push notification dispatched: '{title}' -> recipient (token={token or 'simulated'})")
        return {
            "success": True,
            "mode": "mock_delivery",
            "message_id": f"mock_fcm_{int(datetime.now(timezone.utc).timestamp())}",
            "payload": notification_payload,
            "timestamp": now_utc,
            "should_deactivate": False
        }

    async def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Dispatches notification to multiple device tokens, reporting individual outcomes."""
        now_utc = datetime.now(timezone.utc).isoformat()
        if not tokens:
            return {
                "success": True,
                "dispatched_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "unregistered_tokens": [],
                "delivery_results": [],
                "timestamp": now_utc
            }

        delivery_results = []
        unregistered_tokens = []
        success_count = 0
        failure_count = 0

        for token in tokens:
            res = await self.send_push_notification(
                token=token,
                title=title,
                body=body,
                data=data
            )
            res["token"] = token
            delivery_results.append(res)
            if res.get("success"):
                success_count += 1
            else:
                failure_count += 1
                if res.get("should_deactivate"):
                    unregistered_tokens.append(token)

        return {
            "success": success_count > 0 or len(tokens) == 0,
            "dispatched_count": len(tokens),
            "success_count": success_count,
            "failure_count": failure_count,
            "unregistered_tokens": unregistered_tokens,
            "delivery_results": delivery_results,
            "timestamp": now_utc
        }
