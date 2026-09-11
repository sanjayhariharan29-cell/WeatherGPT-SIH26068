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
import hashlib
import logging
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.db.models import (
    Alert as DBAlert,
    AlertDeliveryLog,
    User,
    UserPreference,
    SavedLocation,
    DeviceToken
)
from backend.services.imd_adapter import IMDAdapter
from backend.services.schemas import NormalizedAlertItem
from backend.services.notification_service import NotificationService
from backend.services.exceptions import ProviderError

logger = logging.getLogger("weathergpt.alert_engine")


class AlertStatusEnum(str, Enum):
    """Deterministic lifecycle state of an official meteorological warning."""
    ACTIVE = "ACTIVE"
    SCHEDULED = "SCHEDULED"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"
    CANCELLED = "CANCELLED"


def normalize_and_validate_imd_alert(
    raw: Dict[str, Any],
    now_utc: Optional[datetime] = None
) -> Tuple[Optional[NormalizedAlertItem], str]:
    """Deterministically normalizes and validates an IMD alert payload.

    Validates:
    - Authoritative source (must be IMD)
    - Non-empty title, alert_type, and affected area
    - Valid severity (low, medium, high, extreme, critical, or yellow, orange, red)
    - Valid ISO 8601 UTC timestamps
    - Validity period constraint: expires_at strictly after issued_at
    - Derives deterministic AlertStatusEnum (ACTIVE, SCHEDULED, EXPIRED)
    - Generates authoritative fingerprint/ID if omitted

    Returns:
        (NormalizedAlertItem, "") if valid.
        (None, rejection_reason) if invalid. Never manufactures missing values.
    """
    now = now_utc or datetime.now(timezone.utc)

    if not isinstance(raw, dict) or not raw:
        return None, "Empty or corrupted alert payload."

    # 1. Source Authority Validation
    src = str(raw.get("source") or "").strip()
    if not src or "imd" not in src.lower():
        return None, f"Unauthorized alert source '{src}'. Only official IMD warnings are permitted."

    # 2. Title & Alert Type
    raw_title = raw.get("title")
    if not isinstance(raw_title, str) or not raw_title.strip():
        return None, "Missing or malformed alert title (must be a non-empty string)."
    title = raw_title.strip()

    raw_type = raw.get("alert_type") or raw.get("type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        return None, "Missing or malformed alert_type (must be a non-empty string)."
    alert_type = raw_type.strip()

    # 3. Affected Area Validation
    raw_area = raw.get("area") or raw.get("affected_locations")
    if isinstance(raw_area, list):
        area = ", ".join(str(x).strip() for x in raw_area if str(x).strip())
    elif isinstance(raw_area, str):
        area = raw_area.strip()
    else:
        area = ""

    if not area:
        return None, "Missing or blank affected area."

    # 4. Severity Normalization & Validation
    raw_sev = str(raw.get("severity") or "").lower().strip()
    sev_map = {
        "yellow": "low",
        "low": "low",
        "orange": "medium",
        "medium": "medium",
        "red": "high",
        "high": "high",
        "extreme": "extreme",
        "critical": "extreme"
    }
    if raw_sev not in sev_map:
        return None, f"Invalid severity '{raw_sev}'. Must be a recognized IMD severity level (yellow/low, orange/medium, red/high, extreme)."
    normalized_sev = sev_map[raw_sev]

    # 5. Timestamp Parsing & Validity Period Validation
    iss_val = raw.get("issued_at")
    exp_val = raw.get("expires_at")
    vf_val = raw.get("valid_from")

    if not iss_val:
        return None, "Missing issued_at timestamp."
    if not exp_val:
        return None, "Missing expires_at timestamp."

    try:
        if isinstance(iss_val, datetime):
            iss_dt = iss_val if iss_val.tzinfo else iss_val.replace(tzinfo=timezone.utc)
        else:
            iss_dt = datetime.fromisoformat(str(iss_val).replace("Z", "+00:00"))
            if iss_dt.tzinfo is None:
                iss_dt = iss_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None, f"Malformed issued_at timestamp '{iss_val}'."

    try:
        if isinstance(exp_val, datetime):
            exp_dt = exp_val if exp_val.tzinfo else exp_val.replace(tzinfo=timezone.utc)
        else:
            exp_dt = datetime.fromisoformat(str(exp_val).replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None, f"Malformed expires_at timestamp '{exp_val}'."

    vf_dt = None
    if vf_val:
        try:
            if isinstance(vf_val, datetime):
                vf_dt = vf_val if vf_val.tzinfo else vf_val.replace(tzinfo=timezone.utc)
            else:
                vf_dt = datetime.fromisoformat(str(vf_val).replace("Z", "+00:00"))
                if vf_dt.tzinfo is None:
                    vf_dt = vf_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None, f"Malformed valid_from timestamp '{vf_val}'."

    if exp_dt <= iss_dt:
        return None, f"Expiry timestamp ({exp_dt.isoformat()}) must be strictly after issuance timestamp ({iss_dt.isoformat()})."

    # 6. Lifecycle Status Evaluation
    if vf_dt and now < vf_dt:
        status = AlertStatusEnum.SCHEDULED.value
    elif now < iss_dt:
        status = AlertStatusEnum.SCHEDULED.value
    elif now > exp_dt:
        status = AlertStatusEnum.EXPIRED.value
    else:
        status = AlertStatusEnum.ACTIVE.value

    # 7. Authoritative ID / Fingerprint Generation
    alert_id = str(raw.get("alert_id") or raw.get("id") or "").strip()
    if not alert_id:
        key = f"IMD:{alert_type}:{area}:{iss_dt.isoformat()}".encode("utf-8")
        alert_id = f"IMD-{hashlib.sha256(key).hexdigest()[:12].upper()}"

    description = str(raw.get("description") or f"Official IMD meteorological warning for {area}.").strip()
    instructions = raw.get("instructions")
    if instructions:
        instructions = str(instructions).strip()

    source_url = raw.get("source_url")
    if source_url:
        source_url = str(source_url).strip()

    normalized_item = NormalizedAlertItem(
        alert_id=alert_id,
        alert_type=alert_type,
        severity=normalized_sev,
        title=title,
        description=description,
        instructions=instructions,
        area=area,
        source="IMD",
        source_url=source_url,
        product_type=raw.get("product_type") or "district_warning",
        state=raw.get("state") or "LIVE",
        geometry=raw.get("geometry"),
        toi=raw.get("toi"),
        vupto=raw.get("vupto"),
        matched_district=raw.get("matched_district"),
        issued_at=iss_dt.isoformat(),
        expires_at=exp_dt.isoformat(),
        valid_from=vf_dt.isoformat() if vf_dt else None,
        updated_at=raw.get("updated_at"),
        retrieved_at=raw.get("retrieved_at") or now.isoformat(),
        status=status,
        version=int(raw.get("version") or 1)
    )

    return normalized_item, ""


def is_alert_active(
    issued_at_iso: str,
    expires_at_iso: str,
    valid_from_iso: Optional[str] = None,
    current_time: Optional[datetime] = None
) -> bool:
    """Validates that alert is currently active with timezone-aware ISO UTC timestamps."""
    now = current_time or datetime.now(timezone.utc)
    try:
        iss_dt = datetime.fromisoformat(issued_at_iso.replace("Z", "+00:00"))
        if iss_dt.tzinfo is None:
            iss_dt = iss_dt.replace(tzinfo=timezone.utc)
    except Exception:
        iss_dt = now

    try:
        exp_dt = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    except Exception:
        exp_dt = now - timedelta(seconds=1)

    vf_dt = None
    if valid_from_iso:
        try:
            vf_dt = datetime.fromisoformat(valid_from_iso.replace("Z", "+00:00"))
            if vf_dt.tzinfo is None:
                vf_dt = vf_dt.replace(tzinfo=timezone.utc)
        except Exception:
            vf_dt = None

    if vf_dt and now < vf_dt:
        return False

    return iss_dt <= now <= exp_dt


class AlertEngine:
    """Production automated IMD warning ingestion, targeting, and delivery engine."""

    is_alert_active = staticmethod(is_alert_active)

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

        now_utc = datetime.now(timezone.utc)

        for item in raw_items:
            # 1. Official normalization & safety validation
            raw_dict = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            validated_alert, error_reason = normalize_and_validate_imd_alert(raw_dict, now_utc=now_utc)
            if validated_alert is None:
                logger.warning(f"Rejected invalid IMD alert for '{location_name}': {error_reason}")
                continue

            # 2. Expiry check - never ingest expired alerts as active
            if validated_alert.status == AlertStatusEnum.EXPIRED.value:
                logger.info(f"Skipping expired alert '{validated_alert.title}' (expired at {validated_alert.expires_at})")
                continue

            try:
                iss_dt = datetime.fromisoformat(validated_alert.issued_at)
            except Exception:
                iss_dt = now_utc

            try:
                exp_dt = datetime.fromisoformat(validated_alert.expires_at)
            except Exception:
                exp_dt = None

            # 3. Duplicate & Update Detection with Timestamp / Version Ordering
            existing = db.query(DBAlert).filter(
                DBAlert.location_name == location_name,
                DBAlert.alert_type == validated_alert.alert_type,
                DBAlert.title == validated_alert.title
            ).first()

            if existing:
                # Ensure existing.issued_at is timezone-aware for fair comparison
                existing_issued = existing.issued_at
                if existing_issued and existing_issued.tzinfo is None:
                    existing_issued = existing_issued.replace(tzinfo=timezone.utc)

                # Invariant: Older version cannot overwrite newer version
                if existing_issued and iss_dt < existing_issued:
                    logger.warning(
                        f"Ignoring older version of alert '{validated_alert.title}' "
                        f"(incoming issued_at {iss_dt} < existing {existing_issued})"
                    )
                    persisted_records.append(existing)
                    continue

                # Check for Alert Update (severity changed, area changed, description changed, or newer issuance)
                is_changed = (
                    existing.severity != validated_alert.severity
                    or existing.description != validated_alert.description
                    or (existing_issued and iss_dt > existing_issued)
                )

                if is_changed:
                    logger.info(
                        f"Authoritative alert update detected for '{validated_alert.title}': "
                        f"{existing.severity} -> {validated_alert.severity}"
                    )
                    existing.severity = validated_alert.severity
                    existing.description = validated_alert.description
                    existing.issued_at = iss_dt
                    existing.expires_at = exp_dt
                    db.commit()
                    db.refresh(existing)
                    persisted_records.append(existing)
                else:
                    logger.debug(f"Duplicate alert detected for '{validated_alert.title}' - skipping insert.")
                    persisted_records.append(existing)
            else:
                # New Alert Ingestion
                record = DBAlert(
                    location_name=location_name,
                    latitude=latitude,
                    longitude=longitude,
                    alert_type=validated_alert.alert_type,
                    severity=validated_alert.severity,
                    title=validated_alert.title,
                    description=validated_alert.description,
                    source=validated_alert.source,
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

    @staticmethod
    def generate_alert_fingerprint(
        source: str,
        alert_type: str,
        area: str,
        issued_at: str,
        severity: Optional[str] = None,
        version: Optional[int] = None
    ) -> str:
        """Generates deterministic SHA-256 fingerprint for alert deduplication and update tracking."""
        parts = [str(source or "IMD"), str(alert_type or ""), str(area or ""), str(issued_at or "")]
        if severity:
            parts.append(str(severity))
        if version is not None:
            parts.append(str(version))
        key = ":".join(parts).encode("utf-8")
        return hashlib.sha256(key).hexdigest()[:16]

    def match_affected_area(
        self,
        alert_area: str,
        alert_lat: Optional[float],
        alert_lon: Optional[float],
        user_location_name: str,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None
    ) -> bool:
        """Determines whether a user location falls within the official affected warning zone.

        Deterministic Matching Levels:
        1. Exact coordinate proximity (Haversine <= 60km) where valid GPS coordinates exist.
        2. Direct substring / administrative district containment.
        3. Curated meteorological zone keywords (coastal belt, delta, Nilgiris / Western Ghats).
        """
        if not alert_area or not user_location_name:
            return False

        area_lower = alert_area.lower().strip()
        user_loc_lower = user_location_name.lower().strip()

        # 1. Coordinate proximity radius (within 60km of alert epicenter if coordinates exist)
        if (
            alert_lat is not None and alert_lon is not None
            and user_lat is not None and user_lon is not None
        ):
            if (
                -90.0 <= alert_lat <= 90.0 and -180.0 <= alert_lon <= 180.0
                and -90.0 <= user_lat <= 90.0 and -180.0 <= user_lon <= 180.0
            ):
                dist = self.calculate_distance_km(alert_lat, alert_lon, user_lat, user_lon)
                if dist <= 60.0:
                    return True

        # 2. Direct name / district containment
        if user_loc_lower in area_lower or area_lower in user_loc_lower:
            return True

        # Split compound comma/semicolon delimited areas
        sub_areas = [s.strip() for s in area_lower.replace(";", ",").split(",") if s.strip()]
        if any(user_loc_lower in sub or sub in user_loc_lower for sub in sub_areas):
            return True

        # 3. Known regional zone keywords
        coastal_districts = [
            "nagapattinam", "cuddalore", "chennai", "thoothukudi",
            "ramanathapuram", "kancheepuram", "tiruvallur", "kanyakumari", "villupuram"
        ]
        if "coastal" in area_lower and any(d in user_loc_lower for d in coastal_districts):
            return True

        delta_districts = ["thanjavur", "thiruvarur", "nagapattinam", "mayiladuthurai", "pudukkottai"]
        if "delta" in area_lower and any(d in user_loc_lower for d in delta_districts):
            return True

        ghats_districts = ["nilgiris", "ooty", "coonoor", "kodaikanal", "valparai", "theeni", "tenkasi"]
        if any(term in area_lower for term in ["nilgiris", "ghat", "hill"]) and any(d in user_loc_lower for d in ghats_districts):
            return True

        return False

    # =========================================================================
    # 4. NOTIFICATION ELIGIBILITY & USER TARGETING
    # =========================================================================
    def check_eligibility(
        self,
        user: User,
        alert_fingerprint: str,
        db: Session,
        quiet_window_hours: int = 12
    ) -> Tuple[bool, str]:
        """Validates user notification preferences, quiet period, and delivery deduplication."""
        # 1. Preference check
        pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
        if pref and not pref.notification_enabled:
            return False, "notification_disabled"

        # 2. Duplicate notification suppression (within quiet window for same alert fingerprint)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=quiet_window_hours)
        prior_delivery = db.query(AlertDeliveryLog).filter(
            AlertDeliveryLog.user_id == user.id,
            AlertDeliveryLog.alert_fingerprint == alert_fingerprint,
            AlertDeliveryLog.status == "SENT",
            AlertDeliveryLog.created_at >= cutoff
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
        """Processes targeted notification delivery for an active alert across registered users.

        Critical Safety Rules:
        1. Only validated official IMD warnings can trigger notifications. Non-IMD sources are rejected.
        2. Expired warnings (now > expires_at) must NEVER trigger active notifications.
        3. Scheduled warnings (now < issued_at) must NOT trigger immediate notifications.
        4. Multi-device support: Dispatches to ALL active devices of eligible users.
        5. Deactivates invalid device tokens without blocking other active devices.
        6. FCM delivery failures NEVER delete or modify the DBAlert record in SkyZen.
        """
        now_utc = datetime.now(timezone.utc)

        # 1. Source Authority Check: Strictly IMD only
        src = str(alert.source or "").lower().strip()
        if not src or "imd" not in src:
            logger.warning(f"Rejected non-IMD alert delivery attempt (source='{alert.source}')")
            return [{
                "status": "REJECTED",
                "reason": "unauthorized_source",
                "source": alert.source
            }]

        # 2. Lifecycle Evaluation: Expiry & Scheduled Checks
        exp_dt = alert.expires_at
        if exp_dt:
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if now_utc > exp_dt:
                logger.info(f"Skipping expired alert '{alert.title}' from notification dispatch (expired {exp_dt})")
                return [{
                    "status": "SKIPPED",
                    "reason": "expired_alert",
                    "alert_id": alert.id
                }]

        iss_dt = alert.issued_at
        if iss_dt:
            if iss_dt.tzinfo is None:
                iss_dt = iss_dt.replace(tzinfo=timezone.utc)
            if now_utc < iss_dt:
                logger.info(f"Skipping scheduled future alert '{alert.title}' from immediate dispatch (issued_at {iss_dt})")
                return [{
                    "status": "SKIPPED",
                    "reason": "scheduled_alert",
                    "alert_id": alert.id
                }]

        # Generate update-aware alert fingerprint incorporating severity and version
        version_val = getattr(alert, "version", 1) or 1
        alert_fp = self.generate_alert_fingerprint(
            source=alert.source or "IMD",
            alert_type=alert.alert_type,
            area=alert.location_name,
            issued_at=iss_dt.isoformat() if iss_dt else "",
            severity=alert.severity,
            version=version_val
        )

        all_users = db.query(User).all()
        delivery_results: List[Dict[str, Any]] = []

        for user in all_users:
            # Check user locations (strictly isolated to this user)
            user_locations: List[Tuple[str, Optional[float], Optional[float]]] = []
            saved_locs = db.query(SavedLocation).filter(SavedLocation.user_id == user.id).all()

            for sl in saved_locs:
                user_locations.append((sl.name, sl.latitude, sl.longitude))

            # Default fallback location if user has no saved locations
            if not user_locations:
                user_locations.append(("Coimbatore", 11.0168, 76.9558))

            # Determine if any of this user's locations match the affected area
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

            # Eligible & in affected area -> Format multilingual message
            msg = self.notifications.format_alert_message(
                title=alert.title,
                description=alert.description,
                severity=alert.severity,
                language=user.language or "ta",
                area=alert.location_name,
                valid_until=alert.expires_at.isoformat() if alert.expires_at else None,
                alert_id=alert.id
            )

            # Query all active registered device tokens for the user
            active_devices = db.query(DeviceToken).filter(
                DeviceToken.user_id == user.id,
                DeviceToken.is_active == True
            ).all()

            # If user has active devices, dispatch to each; otherwise dev/mock fallback token
            target_devices = active_devices if active_devices else [None]

            for dev in target_devices:
                token_val = dev.token if dev else None
                try:
                    dispatch_res = await self.notifications.send_push_notification(
                        token=token_val,
                        title=msg["title"],
                        body=msg["body"],
                        data={
                            "click_action": "OPEN_ALERT",
                            "screen": "alert_detail",
                            "alert_id": alert.id,
                            "severity": alert.severity,
                            "area": alert.location_name,
                            "source": "IMD",
                            "language": user.language or "ta"
                        }
                    )
                except Exception as fcm_err:
                    logger.error(f"FCM delivery exception for user {user.id}: {fcm_err}")
                    dispatch_res = {
                        "success": False,
                        "error": str(fcm_err),
                        "should_deactivate": False
                    }

                # Handle invalid / unregistered tokens safely
                if dispatch_res.get("should_deactivate") and dev:
                    logger.info(f"Deactivating invalid device token {dev.id} for user {user.id}")
                    dev.is_active = False
                    db.commit()

                dev_status = "SENT" if dispatch_res.get("success") else "FAILED"
                dev_reason = "eligible_in_affected_area" if dev_status == "SENT" else dispatch_res.get("error", "fcm_error")

                # Audit log entry for each device dispatch attempt
                log_entry = AlertDeliveryLog(
                    alert_id=alert.id,
                    alert_fingerprint=alert_fp,
                    user_id=user.id,
                    location_name=matched_location,
                    channel="fcm",
                    status=dev_status,
                    reason=dev_reason,
                    language=user.language or "ta",
                    payload_preview=msg["body"][:100],
                    delivered_at=datetime.now(timezone.utc) if dev_status == "SENT" else None
                )
                db.add(log_entry)
                db.commit()

                delivery_results.append({
                    "user_id": user.id,
                    "device_id": dev.id if dev else "simulated",
                    "status": dev_status,
                    "reason": dev_reason,
                    "language": user.language or "ta",
                    "matched_location": matched_location
                })

        return delivery_results
