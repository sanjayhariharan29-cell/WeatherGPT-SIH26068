"""Automatic IMD Alert Engine Pipeline.

Orchestrates the end-to-end meteorological warning pipeline:
IMD Ingestion -> Official Validation -> Expiry Validation -> Duplicate/Update Detection ->
Affected-Area Matching -> User Targeting -> Notification Eligibility -> FCM Dispatch -> Delivery Tracking.

CRITICAL SAFETY RULE:
IMD official warnings are authoritative.
The LLM / AI must NEVER create, cancel, modify severity, or invent warnings.
Only official IMD bulletins are ingested and processed.
"""

import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.db.models import (
    Alert as DBAlert,
    AlertDeliveryLog,
    User,
    UserPreference,
    SavedLocation
)
from backend.services.imd_adapter import IMDAdapter
from backend.services.schemas import NormalizedAlertItem
from backend.services.notification_service import NotificationService
from backend.services.exceptions import ProviderError

logger = logging.getLogger("weathergpt.alert_engine")


class AlertEngine:
    """Production automated IMD warning ingestion, targeting, and delivery engine."""

    def __init__(
        self,
        imd_adapter: Optional[IMDAdapter] = None,
        notification_service: Optional[NotificationService] = None
    ):
        self.imd = imd_adapter or IMDAdapter()
        self.notifications = notification_service or NotificationService()

    # =========================================================================
    # 1. OFFICIAL VALIDATION & EXPIRY
    # =========================================================================
    def validate_official_source(self, alert: NormalizedAlertItem) -> bool:
        """Enforces that alert originates strictly from official meteorological authorities (IMD)."""
        if not alert.source or "imd" not in alert.source.lower():
            raise ValueError(f"Unauthorized alert source '{alert.source}'. Only official IMD warnings are permitted.")
        return True

    def is_alert_active(self, issued_at_iso: str, expires_at_iso: str) -> bool:
        """Validates that alert is currently active with timezone-aware ISO UTC timestamps."""
        now = datetime.now(timezone.utc)
        try:
            iss_dt = datetime.fromisoformat(issued_at_iso)
            if iss_dt.tzinfo is None:
                iss_dt = iss_dt.replace(tzinfo=timezone.utc)
        except Exception:
            iss_dt = now

        try:
            exp_dt = datetime.fromisoformat(expires_at_iso)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        except Exception:
            exp_dt = now - timedelta(seconds=1)

        return iss_dt <= now <= exp_dt

    # =========================================================================
    # 2. INGESTION, DEDUPLICATION & UPDATE DETECTION
    # =========================================================================
    async def ingest_alerts_for_location(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        db: Session
    ) -> List[DBAlert]:
        """Ingests raw warnings, validates, normalizes, detects updates/duplicates, and persists."""
        raw_items = await self.imd.get_official_alerts(latitude, longitude, location_name)
        persisted_records: List[DBAlert] = []

        for item in raw_items:
            # 1. Official validation
            self.validate_official_source(item)

            # 2. Expiry check
            active_flag = self.is_alert_active(item.issued_at, item.expires_at)
            if not active_flag:
                logger.info(f"Skipping expired alert '{item.title}' (expired at {item.expires_at})")
                continue

            try:
                iss_dt = datetime.fromisoformat(item.issued_at)
            except Exception:
                iss_dt = datetime.now(timezone.utc)

            try:
                exp_dt = datetime.fromisoformat(item.expires_at)
            except Exception:
                exp_dt = None

            # 3. Duplicate Detection & Update Detection
            existing = db.query(DBAlert).filter(
                DBAlert.location_name == location_name,
                DBAlert.alert_type == item.alert_type,
                DBAlert.title == item.title
            ).first()

            if existing:
                # Check for Alert Update (e.g. upgraded severity or newer issuance)
                if existing.severity != item.severity or existing.issued_at != iss_dt:
                    logger.info(f"Alert update detected for '{item.title}': {existing.severity} -> {item.severity}")
                    existing.severity = item.severity
                    existing.description = item.description
                    existing.issued_at = iss_dt
                    existing.expires_at = exp_dt
                    db.commit()
                    db.refresh(existing)
                    persisted_records.append(existing)
                else:
                    logger.debug(f"Duplicate alert detected for '{item.title}' - skipping database insert.")
                    persisted_records.append(existing)
            else:
                # New Alert Ingestion
                record = DBAlert(
                    location_name=location_name,
                    latitude=latitude,
                    longitude=longitude,
                    alert_type=item.alert_type,
                    severity=item.severity,
                    title=item.title,
                    description=item.description,
                    source=item.source,
                    issued_at=iss_dt,
                    expires_at=exp_dt
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                persisted_records.append(record)

        return persisted_records

    # =========================================================================
    # 3. AFFECTED-AREA DETERMINATION & MATCHING
    # =========================================================================
    def calculate_distance_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine geodesic distance in kilometers between two GPS coordinates."""
        r = 6371.0  # Earth's radius in km
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
        return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def match_affected_area(
        self,
        alert_area: str,
        alert_lat: Optional[float],
        alert_lon: Optional[float],
        user_location_name: str,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None
    ) -> bool:
        """Determines whether a user location falls within the official affected warning zone."""
        if not alert_area:
            return False

        area_lower = alert_area.lower()
        user_loc_lower = user_location_name.lower()

        # 1. Direct name / district containment
        if user_loc_lower in area_lower or area_lower in user_loc_lower:
            return True

        # 2. Known regional zone keywords (e.g. coastal belt, Nilgiris, delta)
        coastal_districts = ["nagapattinam", "cuddalore", "chennai", "thoothukudi", "ramanathapuram", "kancheepuram"]
        if "coastal" in area_lower and any(d in user_loc_lower for d in coastal_districts):
            return True

        # 3. Coordinate proximity radius (within 60km of alert epicenter if coordinates exist)
        if alert_lat is not None and alert_lon is not None and user_lat is not None and user_lon is not None:
            dist = self.calculate_distance_km(alert_lat, alert_lon, user_lat, user_lon)
            if dist <= 60.0:
                return True

        return False

    # =========================================================================
    # 4. NOTIFICATION ELIGIBILITY & USER TARGETING
    # =========================================================================
    def check_eligibility(
        self,
        user: User,
        alert_fingerprint: str,
        db: Session
    ) -> Tuple[bool, str]:
        """Validates user notification preferences, quiet period, and delivery deduplication."""
        # 1. Preference check
        pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
        if pref and not pref.notification_enabled:
            return False, "notification_disabled"

        # 2. Duplicate notification suppression (within 12 hours for same alert fingerprint)
        twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
        prior_delivery = db.query(AlertDeliveryLog).filter(
            AlertDeliveryLog.user_id == user.id,
            AlertDeliveryLog.alert_fingerprint == alert_fingerprint,
            AlertDeliveryLog.status == "SENT",
            AlertDeliveryLog.created_at >= twelve_hours_ago
        ).first()

        if prior_delivery:
            return False, "already_delivered"

        return True, "eligible_in_affected_area"

    # =========================================================================
    # 5. DISPATCH & DELIVERY TRACKING
    # =========================================================================
    async def process_alert_delivery(
        self,
        alert: DBAlert,
        db: Session
    ) -> List[Dict[str, Any]]:
        """Processes targeted notification delivery for an active alert across registered users."""
        alert_fp = self.imd.generate_alert_fingerprint(
            alert.source or "IMD",
            alert.alert_type,
            alert.location_name,
            alert.issued_at.isoformat() if alert.issued_at else ""
        )

        all_users = db.query(User).all()
        delivery_results: List[Dict[str, Any]] = []

        for user in all_users:
            # Check user locations (both saved locations and default city)
            user_locations: List[Tuple[str, Optional[float], Optional[float]]] = []
            saved_locs = db.query(SavedLocation).filter(SavedLocation.user_id == user.id).all()

            for sl in saved_locs:
                user_locations.append((sl.name, sl.latitude, sl.longitude))

            # Default fallback location if user has no saved locations
            if not user_locations:
                user_locations.append(("Coimbatore", 11.0168, 76.9558))

            # Determine if any of the user's locations match the affected area
            matched_location: Optional[str] = None
            for loc_name, lat, lon in user_locations:
                if self.match_affected_area(
                    alert_area=alert.location_name,
                    alert_lat=alert.latitude,
                    alert_lon=alert.longitude,
                    user_location_name=loc_name,
                    user_lat=lat,
                    user_lon=lon
                ):
                    matched_location = loc_name
                    break

            if not matched_location:
                # User is outside the affected area -> DO NOT BROADCAST!
                log_entry = AlertDeliveryLog(
                    alert_id=alert.id,
                    alert_fingerprint=alert_fp,
                    user_id=user.id,
                    location_name=user_locations[0][0],
                    channel="fcm",
                    status="SKIPPED",
                    reason="out_of_area",
                    language=user.language or "ta",
                    payload_preview=f"{alert.title} (Out of affected area)"
                )
                db.add(log_entry)
                db.commit()
                delivery_results.append({
                    "user_id": user.id,
                    "status": "SKIPPED",
                    "reason": "out_of_area"
                })
                continue

            # User is in affected area -> Check notification eligibility
            is_eligible, reason = self.check_eligibility(user, alert_fp, db)
            if not is_eligible:
                log_entry = AlertDeliveryLog(
                    alert_id=alert.id,
                    alert_fingerprint=alert_fp,
                    user_id=user.id,
                    location_name=matched_location,
                    channel="fcm",
                    status="SKIPPED",
                    reason=reason,
                    language=user.language or "ta",
                    payload_preview=f"{alert.title} ({reason})"
                )
                db.add(log_entry)
                db.commit()
                delivery_results.append({
                    "user_id": user.id,
                    "status": "SKIPPED",
                    "reason": reason
                })
                continue

            # Eligible & in affected area -> Format multilingual message & dispatch via FCM
            msg = self.notifications.format_alert_message(
                title=alert.title,
                description=alert.description,
                severity=alert.severity,
                language=user.language or "ta"
            )

            dispatch_res = await self.notifications.send_push_notification(
                token=None,  # Live FCM token or simulated test device
                title=msg["title"],
                body=msg["body"],
                data={
                    "alert_id": alert.id,
                    "severity": alert.severity,
                    "area": alert.location_name
                }
            )

            now_utc = datetime.now(timezone.utc)
            delivery_status = "SENT" if dispatch_res.get("success") else "FAILED"
            delivery_reason = "eligible_in_affected_area" if delivery_status == "SENT" else dispatch_res.get("error", "fcm_error")

            log_entry = AlertDeliveryLog(
                alert_id=alert.id,
                alert_fingerprint=alert_fp,
                user_id=user.id,
                location_name=matched_location,
                channel="fcm",
                status=delivery_status,
                reason=delivery_reason,
                language=user.language or "ta",
                payload_preview=msg["body"][:100],
                delivered_at=now_utc if delivery_status == "SENT" else None
            )
            db.add(log_entry)
            db.commit()

            delivery_results.append({
                "user_id": user.id,
                "status": delivery_status,
                "reason": delivery_reason,
                "language": user.language or "ta",
                "matched_location": matched_location
            })

        return delivery_results
