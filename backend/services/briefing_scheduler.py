"""Daily Background Scheduler and Mock Dispatch Pipeline for Skizen Weather SMS.

Orchestrates daily personalized weather briefings:
1. Queries users with daily weather SMS enabled.
2. Generates role-tailored briefings via Phase 1 PersonalizedBriefingService.
3. Dispatches messages through honest MockSMSProvider (MOCK_SMS_DELIVERY).
4. Persists execution history and audit logs in BriefingDeliveryLog.
5. Implements resilient per-user failure isolation.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.db.session import SessionLocal
from backend.db.models import User, UserPreference, BriefingDeliveryLog
from backend.services.briefing_service import PersonalizedBriefingService
from backend.services.sms.base import BaseSMSProvider
from backend.services.sms.mock_provider import MockSMSProvider
from ai.models import RiskLevelEnum

logger = logging.getLogger("weathergpt.services.briefing_scheduler")

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

SEVERITY_RANK = {
    "LOW": 1,
    "GREEN": 1,
    "MEDIUM": 2,
    "MODERATE": 2,
    "YELLOW": 2,
    "HIGH": 3,
    "ORANGE": 3,
    "EXTREME": 4,
    "RED": 4
}


def get_severity_rank(sev: Any) -> int:
    """Returns an integer severity rank for comparison and escalation."""
    if not sev:
        return 1
    if hasattr(sev, "value"):
        sev = sev.value
    return SEVERITY_RANK.get(str(sev).upper().strip(), 2)


def compute_event_fingerprint(
    warning_id: Optional[str] = None,
    hazard_type: Optional[str] = None,
    location_name: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """Generates a stable 64-character SHA-256 fingerprint for a severe weather event."""
    parts = []
    if warning_id:
        parts.append(f"warn:{str(warning_id).strip().lower()}")
    else:
        if hazard_type:
            parts.append(f"haz:{str(hazard_type).strip().lower()}")
        if title:
            parts.append(f"title:{str(title).strip().lower()}")
        if location_name:
            parts.append(f"loc:{str(location_name).strip().lower()}")

    raw = "|".join(parts) or "unknown_severe_event"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BriefingScheduler:
    """Manages scheduled daily briefings and on-demand mock SMS delivery."""

    def __init__(
        self,
        briefing_service: Optional[PersonalizedBriefingService] = None,
        sms_provider: Optional[BaseSMSProvider] = None
    ):
        self.briefing_service = briefing_service or PersonalizedBriefingService()
        self.sms_provider = sms_provider or MockSMSProvider()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def dispatch_user_briefing(
        self,
        user: User,
        db: Session,
        message_type: str = "daily",
        force_override: bool = False
    ) -> Dict[str, Any]:
        """Generates and delivers a personalized briefing for a single user with resilient error handling."""
        now_utc = datetime.now(timezone.utc)
        user_pref = user.preferences

        # Safety Check: Respect user's daily_sms_enabled preference unless explicitly forced
        if not force_override and user_pref and not user_pref.daily_sms_enabled:
            logger.info("Skipping user %s: Daily SMS preference is disabled.", user.id)
            return {"user_id": user.id, "status": "SKIPPED", "reason": "daily_sms_disabled"}

        user_phone = user.phone_number or (user.mobile_number if hasattr(user, "mobile_number") else "")

        try:
            # 1. Generate personalized message via Phase 1 reasoning engine
            briefing = await self.briefing_service.generate_personalized_briefing(
                user_id=user.id,
                db_session=db
            )

            # 2. Mock SMS Transmission
            sms_meta = {
                "user_id": user.id,
                "role": briefing.role,
                "location_name": briefing.location_name,
                "risk_level": briefing.risk_level,
                "message_type": message_type
            }
            delivery_result = await self.sms_provider.send_sms(
                to_phone=user_phone,
                message=briefing.message_text,
                metadata=sms_meta
            )

            # 3. Persist in BriefingDeliveryLog
            log_entry = BriefingDeliveryLog(
                user_id=user.id,
                message_type=message_type,
                location_name=briefing.location_name,
                role=briefing.role,
                phone_number=user_phone,
                risk_level=briefing.risk_level,
                risk_status_label=briefing.risk_status_label,
                delivery_status=delivery_result.delivery_status,  # 'MOCK_SMS_DELIVERY'
                data_source="OpenWeather / Open-Meteo / IMD",
                data_freshness=briefing.data_freshness,
                message_text=briefing.message_text,
                character_count=briefing.character_count,
                reasoning_bullets=json.dumps(briefing.reasoning_bullets, ensure_ascii=False),
                delivered_at=delivery_result.delivered_at,
                created_at=now_utc
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            logger.info(
                "Successfully generated and mock-delivered %s briefing for user %s (%s). Log ID: %s",
                message_type, user.id, user.name, log_entry.id
            )

            return {
                "user_id": user.id,
                "log_id": log_entry.id,
                "status": delivery_result.delivery_status,
                "role": briefing.role,
                "location": briefing.location_name,
                "risk_level": briefing.risk_level,
                "character_count": briefing.character_count,
                "message_text": briefing.message_text,
                "delivered_at": delivery_result.delivered_at.isoformat()
            }

        except Exception as ex:
            db.rollback()
            err_msg = str(ex)
            logger.error("Failed to generate or deliver briefing for user %s: %s", user.id, err_msg)

            # Record failure in history to maintain complete visibility
            try:
                fail_log = BriefingDeliveryLog(
                    user_id=user.id,
                    message_type=message_type,
                    location_name=(user_pref.last_known_location if user_pref and user_pref.last_known_location else "Unknown"),
                    role=(user.persona or "user"),
                    phone_number=user_phone,
                    risk_level="UNKNOWN",
                    risk_status_label="Data Unavailable",
                    delivery_status="FAILED",
                    data_source="Meteorological Provider Error",
                    data_freshness="stale",
                    message_text="Personalized briefing unavailable due to meteorological telemetry failure.",
                    character_count=0,
                    error_reason=err_msg[:250],
                    created_at=now_utc
                )
                db.add(fail_log)
                db.commit()
            except Exception as log_ex:
                db.rollback()
                logger.error("Could not write failure log for user %s: %s", user.id, str(log_ex))

            return {"user_id": user.id, "status": "FAILED", "error": err_msg}

    async def trigger_daily_run(
        self,
        db: Optional[Session] = None,
        target_user_id: Optional[str] = None,
        force_time: bool = True
    ) -> List[Dict[str, Any]]:
        """Executes a daily briefing run for all eligible users or a specific user on demand."""
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        results: List[Dict[str, Any]] = []
        try:
            now_ist = datetime.now(IST)
            current_time_str = now_ist.strftime("%H:%M")  # e.g. "07:00"

            query = db.query(User).join(UserPreference, User.id == UserPreference.user_id, isouter=True)

            if target_user_id:
                query = query.filter(User.id == target_user_id)
            else:
                # Filter for users with daily_sms_enabled
                query = query.filter(
                    (UserPreference.daily_sms_enabled == True) | (UserPreference.daily_sms_enabled == None)
                )
                if not force_time:
                    # Filter by configured briefing_time (default "07:00")
                    query = query.filter(
                        (UserPreference.briefing_time == current_time_str) |
                        ((UserPreference.briefing_time == None) & (current_time_str == "07:00"))
                    )

            users = query.all()
            logger.info("Found %d users for daily briefing execution (force_time=%s)", len(users), force_time)

            for user in users:
                # Per-user isolated execution
                res = await self.dispatch_user_briefing(
                    user=user,
                    db=db,
                    message_type="daily" if not target_user_id else "manual_test",
                    force_override=bool(target_user_id)
                )
                results.append(res)

        finally:
            if owns_db:
                db.close()

        return results

    async def dispatch_proactive_alert_for_user(
        self,
        user: User,
        db: Session,
        simulated_alert: Optional[Dict[str, Any]] = None,
        cooldown_hours: int = 12
    ) -> Dict[str, Any]:
        """Evaluates whether to generate, deduplicate, or dispatch an urgent proactive alert for a single user."""
        now_utc = datetime.now(timezone.utc)
        user_pref = user.preferences

        # 1. User Preference Check: severe_alerts_enabled must be True
        if user_pref and not user_pref.severe_alerts_enabled:
            logger.info("Skipping proactive alert for user %s: severe_alerts_enabled is False.", user.id)
            return {
                "user_id": user.id,
                "status": "SKIPPED",
                "reason": "severe_alerts_disabled"
            }

        user_phone = user.phone_number or (user.mobile_number if hasattr(user, "mobile_number") else "")
        loc_name = (user_pref.last_known_location if user_pref and user_pref.last_known_location else "Chennai")
        lat = user_pref.last_latitude if user_pref else None
        lon = user_pref.last_longitude if user_pref else None

        try:
            # 2. Event Identification & Severity Assessment
            if simulated_alert:
                warning_id = simulated_alert.get("id")
                hazard_type = simulated_alert.get("hazard_type") or simulated_alert.get("type", "Severe Weather")
                title = simulated_alert.get("title", hazard_type)
                sev_val = simulated_alert.get("severity", "HIGH")
                current_rank = get_severity_rank(sev_val)
                current_risk_level = "HIGH" if current_rank >= 3 else ("MODERATE" if current_rank == 2 else "LOW")
                fingerprint = compute_event_fingerprint(
                    warning_id=warning_id,
                    hazard_type=hazard_type,
                    location_name=loc_name,
                    title=title
                )
                trigger_alert_override = simulated_alert
            else:
                # Live evaluation
                obs, fc, active_alerts = await self.briefing_service.weather_manager.get_ai_weather_input(
                    lat=lat, lon=lon, location_name=loc_name
                )
                from ai.reasoner.reasoner import WeatherReasoner
                reasoning = WeatherReasoner.evaluate(primary_weather=obs, forecast=fc, active_alerts=active_alerts)

                # Check if significant event is active
                if active_alerts:
                    top_alert = active_alerts[0]
                    warning_id = getattr(top_alert, "id", None)
                    hazard_type = getattr(top_alert, "type", "Warning")
                    title = getattr(top_alert, "title", "Severe Weather Warning")
                    current_rank = get_severity_rank(top_alert.severity)
                    current_risk_level = "HIGH" if current_rank >= 3 else "MODERATE"
                    fingerprint = compute_event_fingerprint(
                        warning_id=warning_id,
                        hazard_type=hazard_type,
                        location_name=loc_name,
                        title=title
                    )
                    trigger_alert_override = top_alert
                elif reasoning.overall_risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or (reasoning.detected_hazards and any(h.severity in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) for h in reasoning.detected_hazards)):
                    top_hazard = reasoning.detected_hazards[0] if reasoning.detected_hazards else None
                    hazard_type = top_hazard.hazard_type.value if top_hazard and hasattr(top_hazard.hazard_type, "value") else "Hazard"
                    title = top_hazard.details if top_hazard else "Severe Weather"
                    current_rank = get_severity_rank(top_hazard.severity if top_hazard else RiskLevelEnum.HIGH)
                    current_risk_level = "HIGH"
                    fingerprint = compute_event_fingerprint(
                        hazard_type=hazard_type,
                        location_name=loc_name,
                        title=title
                    )
                    trigger_alert_override = None
                else:
                    return {
                        "user_id": user.id,
                        "status": "NO_ALERT_CONDITIONS",
                        "reason": "no_active_severe_event"
                    }

            # 3. Cooldown & Deduplication Window Check
            cooldown_cutoff = now_utc - timedelta(hours=cooldown_hours)
            prev_logs = db.query(BriefingDeliveryLog).filter(
                BriefingDeliveryLog.user_id == user.id,
                BriefingDeliveryLog.message_type == "proactive",
                BriefingDeliveryLog.event_fingerprint == fingerprint,
                BriefingDeliveryLog.delivery_status == "MOCK_SMS_DELIVERY",
                BriefingDeliveryLog.created_at >= cooldown_cutoff
            ).order_by(BriefingDeliveryLog.created_at.desc()).all()

            escalated = False
            if prev_logs:
                highest_prev_rank = max(get_severity_rank(l.risk_level) for l in prev_logs)
                if current_rank > highest_prev_rank:
                    escalated = True
                    logger.info(
                        "Proactive alert for user %s escalated (rank %d > prev %d)",
                        user.id, current_rank, highest_prev_rank
                    )
                else:
                    logger.info(
                        "Suppressing duplicate ongoing alert for user %s (fingerprint=%s, current_rank=%d <= prev_rank=%d)",
                        user.id, fingerprint, current_rank, highest_prev_rank
                    )
                    return {
                        "user_id": user.id,
                        "status": "SKIPPED",
                        "reason": "duplicate_ongoing_event_suppressed",
                        "event_fingerprint": fingerprint,
                        "current_severity": current_risk_level,
                        "cooldown_hours": cooldown_hours
                    }

            # 4. Generate Urgent Proactive Alert Message
            proactive_briefing = await self.briefing_service.generate_proactive_alert(
                user_id=user.id,
                db_session=db,
                active_alert_override=trigger_alert_override,
                escalated=escalated
            )

            # 5. Dispatch via MockSMSProvider
            sms_meta = {
                "user_id": user.id,
                "role": proactive_briefing.role,
                "location_name": proactive_briefing.location_name,
                "risk_level": proactive_briefing.risk_level,
                "message_type": "proactive",
                "event_fingerprint": fingerprint,
                "escalated": escalated
            }
            delivery_result = await self.sms_provider.send_sms(
                to_phone=user_phone,
                message=proactive_briefing.message_text,
                metadata=sms_meta
            )

            # 6. Persist to Delivery Log
            log_entry = BriefingDeliveryLog(
                user_id=user.id,
                message_type="proactive",
                event_fingerprint=fingerprint,
                location_name=proactive_briefing.location_name,
                role=proactive_briefing.role,
                phone_number=user_phone,
                risk_level=proactive_briefing.risk_level,
                risk_status_label=proactive_briefing.risk_status_label,
                delivery_status=delivery_result.delivery_status,  # 'MOCK_SMS_DELIVERY'
                data_source="OpenWeather / Open-Meteo / IMD",
                data_freshness=proactive_briefing.data_freshness,
                message_text=proactive_briefing.message_text,
                character_count=proactive_briefing.character_count,
                reasoning_bullets=json.dumps(proactive_briefing.reasoning_bullets, ensure_ascii=False),
                delivered_at=delivery_result.delivered_at,
                created_at=now_utc
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            logger.info(
                "Proactive alert dispatched for user %s. Log ID: %s, Fingerprint: %s, Escalated: %s",
                user.id, log_entry.id, fingerprint, escalated
            )

            return {
                "user_id": user.id,
                "log_id": log_entry.id,
                "status": delivery_result.delivery_status,
                "event_fingerprint": fingerprint,
                "escalated": escalated,
                "role": proactive_briefing.role,
                "location": proactive_briefing.location_name,
                "risk_level": proactive_briefing.risk_level,
                "character_count": proactive_briefing.character_count,
                "message_text": proactive_briefing.message_text,
                "delivered_at": delivery_result.delivered_at.isoformat()
            }

        except Exception as ex:
            db.rollback()
            err_msg = str(ex)
            logger.error("Failed proactive alert check for user %s: %s", user.id, err_msg)
            return {"user_id": user.id, "status": "FAILED", "error": err_msg}

    async def check_and_dispatch_proactive_alerts(
        self,
        db: Optional[Session] = None,
        target_user_id: Optional[str] = None,
        simulated_alert: Optional[Dict[str, Any]] = None,
        cooldown_hours: int = 12
    ) -> List[Dict[str, Any]]:
        """Evaluates active weather warnings/hazards and dispatches proactive alerts for eligible users."""
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        results: List[Dict[str, Any]] = []
        try:
            query = db.query(User).join(UserPreference, User.id == UserPreference.user_id, isouter=True)

            if target_user_id:
                query = query.filter(User.id == target_user_id)
            else:
                # Filter for users with severe_alerts_enabled
                query = query.filter(
                    (UserPreference.severe_alerts_enabled == True) | (UserPreference.severe_alerts_enabled == None)
                )

            users = query.all()
            logger.info("Evaluating %d users for proactive alerts (simulated=%s)", len(users), bool(simulated_alert))

            for user in users:
                res = await self.dispatch_proactive_alert_for_user(
                    user=user,
                    db=db,
                    simulated_alert=simulated_alert,
                    cooldown_hours=cooldown_hours
                )
                results.append(res)

        finally:
            if owns_db:
                db.close()

        return results

    async def _scheduler_loop(self):
        """Background daemon polling loop checking briefing_time every 60s."""
        logger.info("BriefingScheduler background loop started.")
        while self._running:
            try:
                now_ist = datetime.now(IST)
                # 1. Run matching scheduled daily briefings
                await self.trigger_daily_run(force_time=False)
                # 2. Check for newly developing proactive severe events
                await self.check_and_dispatch_proactive_alerts()
            except Exception as loop_ex:
                logger.error("Error in BriefingScheduler loop iteration: %s", loop_ex)

            # Sleep until next minute boundary
            await asyncio.sleep(60)

    def start(self):
        """Starts the scheduler background task."""
        if not self._running:
            self._running = True
            try:
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self._scheduler_loop())
            except RuntimeError:
                pass

    def stop(self):
        """Gracefully cancels the background task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        logger.info("BriefingScheduler stopped.")


# Global instance
scheduler_service = BriefingScheduler()
