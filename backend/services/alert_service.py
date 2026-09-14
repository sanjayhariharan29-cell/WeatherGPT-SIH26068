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
        db_session: Optional[Session] = None,
        all_cities: bool = False
    ) -> AlertResponse:
        """Fetches developer-declared official alerts with strict city scoping (or global multi-city view)."""
        now_utc = datetime.now(timezone.utc)
        now_utc_str = now_utc.isoformat()

        if all_cities or location_name.strip().lower() == "all":
            all_cities = True
            resolved_name = "All Regions (India)"
            latitude = 20.5937
            longitude = 78.9629
            loc = {"name": resolved_name, "latitude": latitude, "longitude": longitude}
        else:
            self.validate_coordinates(lat, lon)
            loc = await self.geocoding.resolve_location(location_name)
            latitude = lat if lat is not None else loc["latitude"]
            longitude = lon if lon is not None else loc["longitude"]
            resolved_name = loc["name"]


        # 1. Official Alert Retrieval from Primary Provider (IMD)
        official_alerts: List[Any] = []
        imd_state_val = "LIVE"
        system_state_val = "ONLINE"
        status_val = "VERIFIED"

        if self.primary:
            if getattr(self.primary, "mode", None) == "test":
                imd_state_val = "FIXTURE"
            elif getattr(self.primary, "mode", None) == "live" and hasattr(self.primary, "is_live_configured") and not self.primary.is_live_configured:
                imd_state_val = "NOT_CONFIGURED"
                system_state_val = "DEGRADED"
                status_val = "UNCONFIGURED"

            try:
                raw_official = await self.primary.get_official_alerts(latitude, longitude, resolved_name)
                if raw_official:
                    official_alerts.extend(raw_official)
            except ProviderError as pe:
                diag = getattr(pe, "diagnostics", {}) or {}
                if diag.get("live_configured") is False or "not configured" in str(pe).lower():
                    imd_state_val = "NOT_CONFIGURED"
                    system_state_val = "DEGRADED"
                    status_val = "UNCONFIGURED"
                else:
                    imd_state_val = "UNAVAILABLE"
                    system_state_val = "DEGRADED"
                    status_val = "UNVERIFIED"
            except Exception as e:
                logger.warning(f"Error fetching alerts from {getattr(self.primary, 'name', 'primary')}: {e}")

        # 2. Developer Manual Entry System (DBAlert table)
        session = db_session
        should_close = False
        if session is None:
            from backend.db.session import SessionLocal
            session = SessionLocal()
            should_close = True

        db_alerts: List[DBAlert] = []
        try:
            query = session.query(DBAlert)
            all_records = query.order_by(DBAlert.issued_at.desc()).all()

            if all_cities:
                for pa in all_records:
                    exp = pa.expires_at
                    if exp and exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    is_active = (exp > now_utc) if exp else True
                    if not active_only or is_active:
                        db_alerts.append(pa)
            else:
                r_lower = resolved_name.lower().strip()
                r_dist = (loc.get("district") or "").lower().strip()
                for pa in all_records:
                    exp = pa.expires_at
                    if exp and exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    is_active = (exp > now_utc) if exp else True
                    if active_only and not is_active:
                        continue

                    pa_loc = (pa.location_name or "").lower().strip()
                    # City-scoping: strictly matches the target city / district
                    matched = False
                    if r_lower and (r_lower in pa_loc or pa_loc in r_lower):
                        matched = True
                    elif r_dist and (r_dist in pa_loc or pa_loc in r_dist):
                        matched = True

                    if matched:
                        db_alerts.append(pa)
        finally:
            if should_close:
                session.close()

        # 3. Combine and Normalize Alert Items
        alert_schemas: List[AlertItemSchema] = []

        # Process Official Provider Alerts
        for m in official_alerts:
            exp_str = getattr(m, "expires_at", None) or now_utc_str
            iss_str = getattr(m, "issued_at", None) or now_utc_str
            is_active = self.is_alert_active(iss_str, exp_str)
            if active_only and not is_active:
                continue

            alert_schemas.append(AlertItemSchema(
                alert_id=getattr(m, "alert_id", None) or f"imd_{latitude}_{longitude}_{len(alert_schemas)}",
                alert_type=getattr(m, "alert_type", "heavy_rain"),
                severity=self.normalize_severity(getattr(m, "severity", "high")),
                title=getattr(m, "title", "Official Warning"),
                description=getattr(m, "description", ""),
                instructions=getattr(m, "instructions", None),
                area=getattr(m, "area", None) or resolved_name,
                source=getattr(m, "source", None) or "IMD",
                source_url=getattr(m, "source_url", None) or "https://mausam.imd.gov.in",
                product_type=getattr(m, "product_type", "district_warning"),
                state=getattr(m, "state", "FIXTURE" if imd_state_val == "FIXTURE" else "LIVE"),
                geometry=getattr(m, "geometry", None),
                toi=getattr(m, "toi", None),
                vupto=getattr(m, "vupto", None),
                matched_district=getattr(m, "matched_district", None) or resolved_name,
                is_official=True,
                is_active=is_active,
                status="ACTIVE" if is_active else "EXPIRED",
                version=getattr(m, "version", 1),
                issued_at=iss_str,
                expires_at=exp_str,
                valid_from=getattr(m, "valid_from", None) or iss_str,
                updated_at=getattr(m, "updated_at", None) or iss_str,
                retrieved_at=now_utc_str
            ))

        # Process Developer-Declared DB Alerts
        for pa in db_alerts:
            exp_dt = pa.expires_at
            if exp_dt and exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            iss_dt = pa.issued_at
            if iss_dt and iss_dt.tzinfo is None:
                iss_dt = iss_dt.replace(tzinfo=timezone.utc)

            is_active = (exp_dt > now_utc) if exp_dt else True
            if active_only and not is_active:
                continue

            alert_schemas.append(AlertItemSchema(
                alert_id=str(pa.id),
                alert_type=pa.alert_type,
                severity=self.normalize_severity(pa.severity),
                title=pa.title,
                description=pa.description,
                instructions=getattr(pa, "instructions", None),
                area=pa.location_name,
                source=pa.source or "IMD",
                source_url="https://mausam.imd.gov.in",
                product_type="district_warning",
                state="LIVE",
                matched_district=pa.location_name,
                is_official=True,
                is_active=is_active,
                status="ACTIVE" if is_active else "EXPIRED",
                version=1,
                issued_at=iss_dt.isoformat() if iss_dt else now_utc_str,
                expires_at=exp_dt.isoformat() if exp_dt else now_utc_str,
                valid_from=iss_dt.isoformat() if iss_dt else now_utc_str,
                updated_at=iss_dt.isoformat() if iss_dt else now_utc_str,
                retrieved_at=now_utc_str
            ))

        # Persist if requested and running in test harness
        if db_session is not None and alert_schemas:
            self._persist_alerts(db_session, resolved_name, latitude, longitude, alert_schemas)

        active_count = sum(1 for a in alert_schemas if a.is_active)
        if imd_state_val == "FIXTURE":
            source_label = "IMD Official (Test Fixture)"
        elif imd_state_val == "NOT_CONFIGURED" and not db_alerts:
            source_label = "IMD Official (Not Configured)"
        elif imd_state_val == "UNAVAILABLE" and not db_alerts:
            source_label = "IMD Official (Unavailable / Degraded)"
        elif db_alerts and not official_alerts:
            source_label = "IMD Official (Developer Declared)"
        else:
            source_label = "IMD Official"

        if alert_schemas:
            status_val = "VERIFIED"
            system_state_val = "ONLINE"

        return AlertResponse(
            location=resolved_name,
            latitude=latitude,
            longitude=longitude,
            alerts=alert_schemas,
            active_count=active_count,
            source=source_label,
            source_identity="IMD",
            status=status_val,
            imd_state=imd_state_val,
            retrieved_at=now_utc_str,
            system_state=system_state_val
        )

    async def fetch_all_active_alerts(
        self,
        db_session: Optional[Session] = None
    ) -> AlertResponse:
        """Returns all currently active developer-declared alerts across all cities."""
        return await self.fetch_alerts(active_only=True, db_session=db_session, all_cities=True)

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
            import sys
            is_test = (getattr(self.primary, "mode", None) == "test") or ("pytest" in sys.modules) or bool(os.getenv("PYTEST_CURRENT_TEST"))
            for item in items:
                # Outside test suite execution, never persist test fixtures to database
                if not is_test and (getattr(item, "state", None) == "FIXTURE" or getattr(item, "is_fixture", False) or "FIXTURE" in str(getattr(item, "source", "")).upper()):
                    continue

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
                    DBAlert.title == item.title
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
        location_name: str = "Coimbatore",
        db_session: Optional[Session] = None
    ) -> List[AIOfficialAlert]:
        """Converts official alerts directly to Person 1's AIOfficialAlert list."""
        res = await self.fetch_alerts(lat, lon, location_name, active_only=True, db_session=db_session, all_cities=False)
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
