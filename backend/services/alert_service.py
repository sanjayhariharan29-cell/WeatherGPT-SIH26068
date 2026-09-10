"""Official Weather Warnings & Alert Engine Service.

Dedicated service layer for retrieving, normalizing, active filtering, severity mapping,
persisting, and converting official meteorological disaster warnings (IMD primary)
to Person 1's AI models while strictly preserving official authority attribution.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.geocoding_service import GeocodingService
from backend.services.base_provider import BaseWeatherProvider
from backend.services.exceptions import ProviderError
from backend.services.schemas import NormalizedAlertItem
from backend.services.alert_engine import AlertEngine
from backend.schemas.weather import (
    AlertResponse,
    AlertItemSchema
)
from backend.db.models import Alert as DBAlert
from ai.models import OfficialAlert as AIOfficialAlert, RiskLevelEnum


class AlertService:
    """Service layer managing official weather alerts, severity normalization, active filtering, and DB persistence."""

    def __init__(
        self,
        primary_provider: Optional[BaseWeatherProvider] = None,
        secondary_provider: Optional[BaseWeatherProvider] = None,
        geocoding_service: Optional[GeocodingService] = None
    ):
        self.primary = primary_provider or IMDAdapter()
        self.secondary = secondary_provider or OpenMeteoAdapter()
        self.geocoding = geocoding_service or GeocodingService()
        self.engine = AlertEngine(imd_adapter=self.primary if isinstance(self.primary, IMDAdapter) else None)

    def validate_coordinates(self, lat: Optional[float], lon: Optional[float]) -> None:
        """Validates latitude and longitude numeric bounds."""
        if lat is not None:
            if not isinstance(lat, (int, float)) or lat < -90.0 or lat > 90.0:
                raise ValueError(f"Invalid latitude {lat}. Latitude must be between -90 and +90 degrees.")

        if lon is not None:
            if not isinstance(lon, (int, float)) or lon < -180.0 or lon > 180.0:
                raise ValueError(f"Invalid longitude {lon}. Longitude must be between -180 and +180 degrees.")

    def normalize_severity(self, raw_severity: str) -> str:
        """Normalizes provider alert severity into project risk levels."""
        sev = (raw_severity or "medium").lower().strip()
        sev_map = {
            "yellow": "low",
            "low": "low",
            "orange": "medium",
            "medium": "medium",
            "red": "high",
            "high": "high",
            "extreme": "extreme"
        }
        return sev_map.get(sev, "medium")

    def is_alert_active(self, issued_at_iso: str, expires_at_iso: str) -> bool:
        """Determines if an alert is currently active based on ISO 8601 UTC timestamps."""
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
            exp_dt = now + datetime.resolution

        return iss_dt <= now <= exp_dt

    async def fetch_alerts(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        active_only: bool = True,
        db_session: Optional[Session] = None
    ) -> AlertResponse:
        """Fetches, normalizes, filters active alerts, and optionally persists to DB."""
        self.validate_coordinates(lat, lon)

        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]
        resolved_name = loc["name"]

        source_label = f"{self.primary.name} Official"
        verification_status = "VERIFIED"
        try:
            raw_alerts = await self.primary.get_official_alerts(latitude, longitude, resolved_name)
        except ProviderError:
            raw_alerts = []
            source_label = f"{self.primary.name} Official (Degraded)"
            verification_status = "UNVERIFIED"

        from backend.services.alert_engine import normalize_and_validate_imd_alert

        now_utc = datetime.now(timezone.utc)
        now_utc_str = now_utc.isoformat()
        alert_schemas: List[AlertItemSchema] = []

        for item in raw_alerts:
            raw_dict = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            val_item, err_msg = normalize_and_validate_imd_alert(raw_dict, now_utc=now_utc)

            if val_item:
                normalized_sev = val_item.severity
                active_flag = (val_item.status == "ACTIVE")
                status_str = val_item.status
                alert_id_val = val_item.alert_id
                vf_val = val_item.valid_from
                instructions_val = val_item.instructions
                source_url_val = val_item.source_url
                version_val = val_item.version
                area_val = val_item.area or resolved_name
            else:
                normalized_sev = self.normalize_severity(item.severity)
                active_flag = self.is_alert_active(item.issued_at, item.expires_at)
                status_str = "ACTIVE" if active_flag else "EXPIRED"
                alert_id_val = getattr(item, "alert_id", None)
                vf_val = getattr(item, "valid_from", None)
                instructions_val = getattr(item, "instructions", None)
                source_url_val = getattr(item, "source_url", None)
                version_val = getattr(item, "version", 1)
                area_val = getattr(item, "area", None) or resolved_name

            schema_item = AlertItemSchema(
                alert_id=alert_id_val,
                alert_type=item.alert_type,
                severity=normalized_sev,
                title=item.title,
                description=item.description,
                instructions=instructions_val,
                area=area_val,
                source=item.source,
                source_url=source_url_val,
                is_official=True,
                is_active=active_flag,
                status=status_str,
                version=version_val,
                issued_at=item.issued_at,
                expires_at=item.expires_at,
                valid_from=vf_val,
                updated_at=item.updated_at,
                retrieved_at=item.retrieved_at
            )

            if not active_only or active_flag:
                alert_schemas.append(schema_item)

        # Optional DB persistence with deduplication
        if db_session is not None:
            self._persist_alerts(db_session, resolved_name, latitude, longitude, alert_schemas)

        active_count = sum(1 for a in alert_schemas if a.is_active)

        return AlertResponse(
            location=resolved_name,
            latitude=latitude,
            longitude=longitude,
            alerts=alert_schemas,
            active_count=active_count,
            source=source_label,
            status=verification_status,
            retrieved_at=now_utc_str
        )

    def _persist_alerts(
        self,
        db: Session,
        location_name: str,
        lat: float,
        lon: float,
        items: List[AlertItemSchema]
    ) -> None:
        """Persists official alert items to database with deduplication on location, title & issuance."""
        try:
            for item in items:
                try:
                    iss_dt = datetime.fromisoformat(item.issued_at)
                except Exception:
                    iss_dt = datetime.now(timezone.utc)

                try:
                    exp_dt = datetime.fromisoformat(item.expires_at)
                except Exception:
                    exp_dt = None

                existing = db.query(DBAlert).filter(
                    DBAlert.location_name == location_name,
                    DBAlert.alert_type == item.alert_type,
                    DBAlert.title == item.title,
                    DBAlert.issued_at == iss_dt
                ).first()

                if not existing:
                    rec = DBAlert(
                        location_name=location_name,
                        latitude=lat,
                        longitude=lon,
                        alert_type=item.alert_type,
                        severity=item.severity,
                        title=item.title,
                        description=item.description,
                        source=item.source,
                        issued_at=iss_dt,
                        expires_at=exp_dt
                    )
                    db.add(rec)
            db.commit()
        except Exception:
            db.rollback()

    async def get_ai_official_alerts(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore"
    ) -> List[AIOfficialAlert]:
        """Converts official alerts directly to Person 1's AIOfficialAlert list."""
        res = await self.fetch_alerts(lat, lon, location_name, active_only=True)
        sev_map = {
            "low": RiskLevelEnum.LOW,
            "green": RiskLevelEnum.LOW,
            "medium": RiskLevelEnum.MEDIUM,
            "yellow": RiskLevelEnum.MEDIUM,
            "high": RiskLevelEnum.HIGH,
            "orange": RiskLevelEnum.HIGH,
            "extreme": RiskLevelEnum.EXTREME,
            "red": RiskLevelEnum.EXTREME
        }

        ai_alerts = []
        for item in res.alerts:
            sev_enum = sev_map.get(item.severity.lower(), RiskLevelEnum.MEDIUM)
            iss_dt = datetime.fromisoformat(item.issued_at) if item.issued_at else datetime.now(timezone.utc)
            exp_dt = datetime.fromisoformat(item.expires_at) if item.expires_at else datetime.now(timezone.utc)
            vf_dt = datetime.fromisoformat(item.valid_from) if getattr(item, "valid_from", None) else None
            ai_alerts.append(
                AIOfficialAlert(
                    id=getattr(item, "alert_id", None),
                    type=item.alert_type,
                    severity=sev_enum,
                    title=item.title,
                    description=item.description,
                    instructions=getattr(item, "instructions", None),
                    source=item.source,
                    source_url=getattr(item, "source_url", None),
                    issued_at=iss_dt,
                    valid_from=vf_dt,
                    expires_at=exp_dt,
                    status=getattr(item, "status", "ACTIVE"),
                    version=getattr(item, "version", 1),
                    affected_locations=[item.area] if item.area else [res.location]
                )
            )
        return ai_alerts


    async def process_automatic_pipeline(
        self,
        location_name: str = "Nagapattinam",
        db_session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Executes full automated pipeline: Ingest -> Deduplicate/Update -> Target -> FCM Dispatch -> Track."""
        if db_session is None:
            return []
        loc = await self.geocoding.resolve_location(location_name)
        persisted = await self.engine.ingest_alerts_for_location(
            location_name=loc["name"],
            latitude=loc["latitude"],
            longitude=loc["longitude"],
            db=db_session
        )
        all_deliveries: List[Dict[str, Any]] = []
        for alert in persisted:
            deliveries = await self.engine.process_alert_delivery(alert, db_session)
            all_deliveries.extend(deliveries)
        return all_deliveries
