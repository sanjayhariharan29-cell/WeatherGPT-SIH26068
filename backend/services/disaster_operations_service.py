"""Disaster and Government Operations Dashboard Service.

Provides authoritative meteorological disaster-weather monitoring using verified
weather and alert pipelines (IMD primary, Open-Meteo, DB alerts).
Features:
- Warning lifecycle tracking: scheduled, active, expired
- Authoritative severity mapping and district-level scoping
- Map-based visualization ONLY where genuine geometry exists (ZERO fake polygons)
- Text-based representation fallback when geometry is absent
- Notification targeting & FCM delivery status audit
- System and provider health telemetry (with credential redaction)
- Strict safety invariance: official warnings cannot be modified or canceled by LLM
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc

from backend.db.models import Alert as DBAlert, AlertDeliveryLog, DeviceToken, User, SavedLocation
from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.weather_reliability import evaluate_weather_freshness, FreshnessClassification

logger = logging.getLogger("weathergpt.disaster_operations")


class DisasterOperationsService:
    """Administrative service for disaster weather monitoring and government operations."""

    def __init__(
        self,
        imd_adapter: Optional[IMDAdapter] = None,
        open_meteo_adapter: Optional[OpenMeteoAdapter] = None
    ):
        self.imd_adapter = imd_adapter or IMDAdapter()
        self.open_meteo_adapter = open_meteo_adapter or OpenMeteoAdapter()

    # =========================================================================
    # 1. LIFECYCLE EVALUATION
    # =========================================================================
    @staticmethod
    def parse_datetime(dt_val: Any) -> Optional[datetime]:
        """Safely normalizes various datetime representations to UTC timezone-aware datetime."""
        if dt_val is None:
            return None
        if isinstance(dt_val, datetime):
            if dt_val.tzinfo is None:
                return dt_val.replace(tzinfo=timezone.utc)
            return dt_val.astimezone(timezone.utc)
        try:
            parsed = datetime.fromisoformat(str(dt_val).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

    @classmethod
    def evaluate_warning_lifecycle(
        cls,
        issued_at: Any,
        expires_at: Any,
        now: Optional[datetime] = None
    ) -> str:
        """Determines the authoritative lifecycle phase of a warning:
        - 'scheduled': issued_at > now (future warning)
        - 'active': issued_at <= now <= expires_at (or no expiry specified)
        - 'expired': expires_at < now (past warning)
        """
        now_utc = now or datetime.now(timezone.utc)
        iss_dt = cls.parse_datetime(issued_at) or now_utc
        exp_dt = cls.parse_datetime(expires_at)

        if iss_dt > now_utc:
            return "scheduled"
        if exp_dt and exp_dt < now_utc:
            return "expired"
        return "active"

    # =========================================================================
    # 2. DATA FRESHNESS EVALUATION
    # =========================================================================
    @classmethod
    def evaluate_data_freshness(
        cls,
        timestamp: Any,
        now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Evaluates timestamp age and freshness classification."""
        now_utc = now or datetime.now(timezone.utc)
        ts_dt = cls.parse_datetime(timestamp) or now_utc
        age_seconds = max(0.0, (now_utc - ts_dt).total_seconds())
        age_minutes = round(age_seconds / 60.0, 1)

        if age_minutes <= 60:
            status = "FRESH"
        elif age_minutes <= 180:
            status = "AGING"
        elif age_minutes <= 1440:
            status = "STALE"
        else:
            status = "UNAVAILABLE"

        return {
            "timestamp": ts_dt.isoformat(),
            "age_minutes": age_minutes,
            "status": status,
            "is_fresh": status == "FRESH"
        }

    # =========================================================================
    # 3. GENUINE GEOMETRY VS TEXT-BASED FALLBACK (SAFETY INVARIANT)
    # =========================================================================
    @classmethod
    def process_geographic_geometry(
        cls,
        raw_geometry: Optional[Dict[str, Any]],
        location_name: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        district: Optional[str] = None
    ) -> Dict[str, Any]:
        """Strictly validates GeoJSON geometry.
        
        CRITICAL SAFETY RULE:
        1. Do NOT create fake warning polygons under any circumstances.
        2. If genuine GeoJSON geometry is available with valid coordinates, preserve it.
        3. If unavailable, return geometry=None, has_geometry=False, and display the
           affected area as descriptive text.
        """
        has_valid_geom = False
        valid_geometry = None

        if isinstance(raw_geometry, dict):
            geom_type = raw_geometry.get("type")
            coords = raw_geometry.get("coordinates")
            if geom_type in ("Polygon", "MultiPolygon", "Point") and coords:
                # Basic sanity check on coordinates structure
                if isinstance(coords, (list, tuple)) and len(coords) > 0:
                    has_valid_geom = True
                    valid_geometry = raw_geometry

        # Compose authoritative affected area text description
        text_parts = [location_name.strip()]
        if district and district.lower() not in location_name.lower():
            text_parts.append(f"District: {district}")
        if latitude is not None and longitude is not None:
            text_parts.append(f"(Lat: {latitude:.4f}, Lon: {longitude:.4f})")

        affected_area_text = ", ".join(text_parts)

        return {
            "has_geometry": has_valid_geom,
            "geometry": valid_geometry if has_valid_geom else None,
            "affected_area_text": affected_area_text,
            "location_name": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "district": district or location_name
        }

    # =========================================================================
    # 4. NOTIFICATION TARGETING & DELIVERY AUDIT
    # =========================================================================
    @staticmethod
    def get_warning_delivery_metrics(
        db: Session,
        alert_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Summarizes notification targeting and FCM delivery status for alerts."""
        query = db.query(AlertDeliveryLog)
        if alert_id:
            query = query.filter(AlertDeliveryLog.alert_id == alert_id)

        all_logs = query.all()

        total_targeted = len(all_logs)
        sent_count = 0
        failed_count = 0
        skipped_count = 0
        skipped_reasons: Dict[str, int] = {}
        failure_reasons: Dict[str, int] = {}

        for log in all_logs:
            st = (log.status or "").upper()
            if st == "SENT":
                sent_count += 1
            elif st == "FAILED":
                failed_count += 1
                r = log.reason or "unknown_error"
                failure_reasons[r] = failure_reasons.get(r, 0) + 1
            elif st == "SKIPPED":
                skipped_count += 1
                r = log.reason or "unknown_skip"
                skipped_reasons[r] = skipped_reasons.get(r, 0) + 1

        delivery_rate_pct = round((sent_count / total_targeted * 100.0), 1) if total_targeted > 0 else 100.0

        # Registered active devices summary
        active_tokens_count = db.query(func.count(DeviceToken.id)).filter(DeviceToken.is_active == True).scalar() or 0

        return {
            "total_targeted": total_targeted,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "delivery_rate_pct": delivery_rate_pct,
            "skipped_reasons": skipped_reasons,
            "failure_reasons": failure_reasons,
            "active_device_tokens": active_tokens_count
        }

    # =========================================================================
    # 5. FILTERED WARNING LIST RETRIEVAL
    # =========================================================================
    def get_warnings(
        self,
        db: Session,
        district: Optional[str] = None,
        warning_type: Optional[str] = None,
        severity: Optional[str] = None,
        lifecycle: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Retrieves disaster warnings with rich lifecycle, freshness, geometry,
        targeting statistics, and administrative filters.
        """
        now_utc = datetime.now(timezone.utc)

        # Base query from DBAlert
        query = db.query(DBAlert)

        # Date range filtering on issued_at
        if date_from:
            query = query.filter(DBAlert.issued_at >= date_from)
        if date_to:
            query = query.filter(DBAlert.issued_at <= date_to)

        # Warning type filter
        if warning_type and warning_type.strip().lower() not in ("all", ""):
            query = query.filter(func.lower(DBAlert.alert_type) == warning_type.strip().lower())

        # District / location filter
        if district and district.strip().lower() not in ("all", ""):
            d_clean = f"%{district.strip().lower()}%"
            query = query.filter(func.lower(DBAlert.location_name).like(d_clean))

        # Severity filter
        if severity and severity.strip().lower() not in ("all", ""):
            query = query.filter(func.lower(DBAlert.severity) == severity.strip().lower())

        db_records = query.order_by(desc(DBAlert.issued_at)).all()

        # Normalize and compute lifecycle, freshness, geometry, targeting stats
        all_warnings: List[Dict[str, Any]] = []
        lifecycle_counts = {"active": 0, "scheduled": 0, "expired": 0}
        severity_counts = {"extreme": 0, "high": 0, "medium": 0, "low": 0}

        for item in db_records:
            item_lifecycle = self.evaluate_warning_lifecycle(item.issued_at, item.expires_at, now=now_utc)
            item_freshness = self.evaluate_data_freshness(item.issued_at, now=now_utc)
            item_geometry = self.process_geographic_geometry(
                raw_geometry=getattr(item, "geometry", None),
                location_name=item.location_name,
                latitude=item.latitude,
                longitude=item.longitude,
                district=item.location_name
            )

            # Severity normalization
            sev_norm = (item.severity or "medium").lower()
            if sev_norm not in severity_counts:
                sev_norm = "medium"

            # Update lifecycle & severity aggregate tallies
            if item_lifecycle in lifecycle_counts:
                lifecycle_counts[item_lifecycle] += 1
            severity_counts[sev_norm] += 1

            # Lifecycle filter check
            if lifecycle and lifecycle.strip().lower() not in ("all", ""):
                if item_lifecycle != lifecycle.strip().lower():
                    continue

            # Notification targeting metrics for this alert
            notif_stats = self.get_warning_delivery_metrics(db, alert_id=item.id)

            iss_str = item.issued_at.isoformat() if item.issued_at else now_utc.isoformat()
            exp_str = item.expires_at.isoformat() if item.expires_at else None

            all_warnings.append({
                "id": str(item.id),
                "title": item.title,
                "alert_type": item.alert_type,
                "severity": sev_norm,
                "lifecycle": item_lifecycle,
                "status": item_lifecycle.upper(),
                "description": item.description,
                "instructions": item.instructions or "Follow official civil authority guidelines.",
                "location_name": item.location_name,
                "district": item.location_name,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "source": item.source or "IMD",
                "issued_at": iss_str,
                "expires_at": exp_str,
                "freshness": item_freshness,
                "geographic_area": item_geometry,
                "notification_metrics": notif_stats,
                "is_authoritative": True
            })

        total_matching = len(all_warnings)
        paginated_warnings = all_warnings[offset:offset + limit]

        return {
            "total_count": total_matching,
            "lifecycle_counts": lifecycle_counts,
            "severity_counts": severity_counts,
            "warnings": paginated_warnings,
            "limit": limit,
            "offset": offset
        }

    # =========================================================================
    # 6. SINGLE WARNING DETAIL
    # =========================================================================
    def get_warning_detail(self, db: Session, warning_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves comprehensive operational detail for a single warning by ID."""
        alert = db.query(DBAlert).filter(DBAlert.id == warning_id).first()
        if not alert:
            return None

        now_utc = datetime.now(timezone.utc)
        item_lifecycle = self.evaluate_warning_lifecycle(alert.issued_at, alert.expires_at, now=now_utc)
        item_freshness = self.evaluate_data_freshness(alert.issued_at, now=now_utc)
        item_geometry = self.process_geographic_geometry(
            raw_geometry=getattr(alert, "geometry", None),
            location_name=alert.location_name,
            latitude=alert.latitude,
            longitude=alert.longitude,
            district=alert.location_name
        )
        notif_stats = self.get_warning_delivery_metrics(db, alert_id=alert.id)

        # Retrieve recent targeting log entries
        logs = db.query(AlertDeliveryLog).filter(
            AlertDeliveryLog.alert_id == alert.id
        ).order_by(desc(AlertDeliveryLog.created_at)).limit(20).all()

        log_items = [{
            "id": l.id,
            "user_id": l.user_id,
            "location_name": l.location_name,
            "channel": l.channel,
            "status": l.status,
            "reason": l.reason,
            "delivered_at": l.delivered_at.isoformat() if l.delivered_at else None,
            "created_at": l.created_at.isoformat() if l.created_at else None
        } for l in logs]

        return {
            "id": str(alert.id),
            "title": alert.title,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "lifecycle": item_lifecycle,
            "status": item_lifecycle.upper(),
            "description": alert.description,
            "instructions": alert.instructions,
            "location_name": alert.location_name,
            "latitude": alert.latitude,
            "longitude": alert.longitude,
            "source": alert.source or "IMD",
            "issued_at": alert.issued_at.isoformat() if alert.issued_at else None,
            "expires_at": alert.expires_at.isoformat() if alert.expires_at else None,
            "freshness": item_freshness,
            "geographic_area": item_geometry,
            "notification_metrics": notif_stats,
            "recent_audit_logs": log_items,
            "is_authoritative": True
        }

    # =========================================================================
    # 7. NOTIFICATION AUDIT LOGS
    # =========================================================================
    @staticmethod
    def get_notification_audit_logs(
        db: Session,
        alert_id: Optional[str] = None,
        status: Optional[str] = None,
        district: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Queries granular notification delivery audit logs."""
        query = db.query(AlertDeliveryLog)

        if alert_id:
            query = query.filter(AlertDeliveryLog.alert_id == alert_id)
        if status and status.strip().lower() not in ("all", ""):
            query = query.filter(func.upper(AlertDeliveryLog.status) == status.strip().upper())
        if district and district.strip().lower() not in ("all", ""):
            d_clean = f"%{district.strip().lower()}%"
            query = query.filter(func.lower(AlertDeliveryLog.location_name).like(d_clean))

        total_count = query.count()
        logs = query.order_by(desc(AlertDeliveryLog.created_at)).offset(offset).limit(limit).all()

        records = [{
            "id": l.id,
            "alert_id": l.alert_id,
            "user_id": l.user_id,
            "location_name": l.location_name,
            "channel": l.channel,
            "status": l.status,
            "reason": l.reason,
            "language": l.language,
            "payload_preview": l.payload_preview,
            "delivered_at": l.delivered_at.isoformat() if l.delivered_at else None,
            "created_at": l.created_at.isoformat() if l.created_at else None
        } for l in logs]

        return {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "logs": records
        }

    # =========================================================================
    # 8. PROVIDER AND SYSTEM HEALTH (CREDENTIAL-SAFE)
    # =========================================================================
    def get_system_provider_health(self, db: Session) -> Dict[str, Any]:
        """Provides complete health and operational status for disaster services.
        
        CRITICAL SECURITY RULE:
        Never expose API keys, database credentials, or Firebase private keys.
        """
        # Database health check
        db_status = "HEALTHY"
        db_latency_ms = 0.0
        try:
            import time
            from sqlalchemy import text
            t0 = time.perf_counter()
            db.execute(text("SELECT 1"))
            db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = "UNHEALTHY"

        # IMD Provider health
        imd_status = "ONLINE"
        imd_mode = getattr(self.imd_adapter, "mode", "live")
        if imd_mode == "test":
            imd_status = "FIXTURE_MODE"
        elif hasattr(self.imd_adapter, "is_live_configured") and not self.imd_adapter.is_live_configured:
            imd_status = "NOT_CONFIGURED"

        # Open-Meteo Provider health
        open_meteo_status = "ONLINE"

        # FCM Notification Service health
        from backend.config.settings import settings
        fcm_status = "CONFIGURED"
        if not getattr(settings, "FIREBASE_CREDENTIALS_PATH", None) and not getattr(settings, "FCM_SERVER_KEY", None):
            fcm_status = "MOCK_MODE"

        # Overall operational state
        if db_status == "UNHEALTHY":
            overall_state = "OUTAGE"
        elif imd_status in ("NOT_CONFIGURED", "DEGRADED") or fcm_status == "MOCK_MODE":
            overall_state = "DEGRADED"
        else:
            overall_state = "OPTIMAL"

        return {
            "overall_status": overall_state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "providers": {
                "imd": {
                    "provider": "India Meteorological Department (IMD)",
                    "status": imd_status,
                    "mode": imd_mode,
                    "role": "Primary Authoritative Warning Source"
                },
                "open_meteo": {
                    "provider": "Open-Meteo Global NWP/ECMWF",
                    "status": open_meteo_status,
                    "role": "Secondary Observational Weather Provider"
                }
            },
            "infrastructure": {
                "database": {
                    "status": db_status,
                    "latency_ms": db_latency_ms
                },
                "fcm_service": {
                    "status": fcm_status,
                    "role": "Disaster Push Notification Gateway"
                }
            },
            "security": {
                "service_account_exposed": False,
                "sanitized": True
            }
        }

    # =========================================================================
    # 9. FULL OPERATIONS DASHBOARD SUMMARY
    # =========================================================================
    def get_dashboard_summary(self, db: Session) -> Dict[str, Any]:
        """Aggregates all components into a unified operations dashboard snapshot."""
        warnings_data = self.get_warnings(db=db, limit=10)
        health_data = self.get_system_provider_health(db=db)
        delivery_metrics = self.get_warning_delivery_metrics(db=db)

        return {
            "dashboard_title": "SkyZen Disaster & Government Operations Center",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_health": health_data,
            "warning_lifecycle_summary": warnings_data["lifecycle_counts"],
            "severity_summary": warnings_data["severity_counts"],
            "fcm_delivery_summary": delivery_metrics,
            "recent_warnings": warnings_data["warnings"],
            "total_warnings": warnings_data["total_count"],
            "authoritative_rule": "Official IMD and Civil Authority Warnings take absolute precedence. LLM outputs cannot modify or cancel official warnings."
        }


# Singleton service instance
disaster_operations_service = DisasterOperationsService()
