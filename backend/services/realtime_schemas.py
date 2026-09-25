"""Real-Time Meteorological Ingestion Schemas & Event Contracts.

Phase 28: Real-Time Meteorological Ingestion.
Defines normalized event schemas, source metadata, provenance tracking,
WMO WIS2.0 notification schemas, and ingestion provider operational health states.
"""

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class IngestionProviderState(str, Enum):
    """Operational health and configuration state for streaming/institutional providers.

    Strict State Disambiguation (Phase 28 Requirement):
    - CONFIGURED: Required credentials, endpoints, or brokers are specified in configuration.
    - AVAILABLE: Active connection established and accepting telemetry / notifications.
    - UNAVAILABLE: Configured, but connection has failed, timed out, or broker is unreachable.
    - NOT_CONFIGURED: No credentials or endpoints specified. Never simulate live connection.
    """
    CONFIGURED = "CONFIGURED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class MeteorologicalEventType(str, Enum):
    """Categorization of real-time meteorological messages and events."""
    WEATHER_OBSERVATION = "WEATHER_OBSERVATION"      # Real-time surface/synop/AWS observation
    WEATHER_FORECAST = "WEATHER_FORECAST"            # Multi-hour or daily forecast update
    OFFICIAL_ALERT = "OFFICIAL_ALERT"                # Severe weather warning / CAP bulletin (IMD)
    NWP_RUN_NOTIFICATION = "NWP_RUN_NOTIFICATION"    # Numerical model run completion / cycle ready
    STATION_TELEMETRY = "STATION_TELEMETRY"          # Raw AWS ground station sensor telemetry
    HEARTBEAT = "HEARTBEAT"                          # Transport or provider liveness ping


class IngestionStatusEnum(str, Enum):
    """Result of event processing through the ingestion pipeline."""
    ACCEPTED = "ACCEPTED"                            # Ingested and routed successfully
    PROCESSED = "PROCESSED"                          # Successfully applied to weather state / alerts
    REJECTED_DUPLICATE = "REJECTED_DUPLICATE"        # Discarded due to identical ID or content hash
    REJECTED_STALE = "REJECTED_STALE"                # Discarded due to event timestamp exceeding stale threshold
    REJECTED_INVALID = "REJECTED_INVALID"            # Discarded due to schema or coordinate validation failure
    ACCEPTED_OUT_OF_ORDER = "ACCEPTED_OUT_OF_ORDER"  # Buffered/archived without overwriting newer state
    RETRY_QUEUED = "RETRY_QUEUED"                    # Downstream routing temporarily failed, retry queued


class EventSourceMetadata(BaseModel):
    """Detailed provenance and transport metadata for real-time meteorological sources."""
    provider_id: str = Field(description="Unique provider identifier, e.g. 'IMD_CAP', 'WIS2_WMO', 'AWS_COIMBATORE'")
    source_name: str = Field(description="Human-readable institutional name e.g. 'India Meteorological Department'")
    transport: str = Field(default="REST", description="Ingestion transport: 'MQTT', 'WIS2_NOTIFICATION', 'WEBSOCKET', 'REST'")
    protocol_version: str = Field(default="1.0", description="Protocol version, e.g. 'WIS2.0-v1', 'MQTT-3.1.1', 'CAP-v1.2'")
    institution: str = Field(default="Ministry of Earth Sciences / IMD", description="Authoritative issuing agency")
    authority_level: str = Field(
        default="authoritative_official",
        description="'authoritative_official', 'nwp_guidance', 'crowdsourced_secondary'"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary headers or protocol flags")


class MeteorologicalEvent(BaseModel):
    """Normalized meteorological event schema supporting streaming transports and institutional feeds."""
    event_id: str = Field(description="Unique message/event identifier (UUID, provider message ID, or hash)")
    event_type: MeteorologicalEventType = Field(description="Event classification")
    topic: str = Field(default="skyzen/met/default", description="WMO or MQTT topic hierarchy path")
    event_timestamp: datetime = Field(description="Time of observation, warning issuance, or simulation valid time")
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Local SkyZen reception timestamp"
    )
    source: EventSourceMetadata = Field(description="Source provenance and institutional metadata")
    location_name: Optional[str] = Field(default=None, description="Location / station / district name")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    sequence_number: Optional[int] = Field(default=None, description="Monotonically increasing sequence number from publisher")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Raw meteorological payload (telemetry, warning, or forecast)")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 fingerprint for deduplication fallback")

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.content_hash:
            self.content_hash = self.compute_content_hash()

    def compute_content_hash(self) -> str:
        """Generates a deterministic SHA-256 digest of key event parameters for payload deduplication."""
        fingerprint_data = {
            "source": self.source.provider_id,
            "event_type": self.event_type.value,
            "topic": self.topic,
            "event_timestamp": self.event_timestamp.isoformat() if hasattr(self.event_timestamp, "isoformat") else str(self.event_timestamp),
            "location_name": self.location_name or "",
            "latitude": round(self.latitude, 4) if self.latitude is not None else None,
            "longitude": round(self.longitude, 4) if self.longitude is not None else None,
            "payload_keys": sorted(list(self.payload.keys())),
        }
        # Include selected high-cardinality payload fields if present
        for key in ("headline", "temperature_c", "warning_id", "severity", "headline_en", "temperature"):
            if key in self.payload:
                fingerprint_data[key] = str(self.payload[key])

        encoded = json.dumps(fingerprint_data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class EventIngestionResult(BaseModel):
    """Result returned after an event passes through the ingestion pipeline."""
    event_id: str
    status: IngestionStatusEnum
    message: str
    routed_to: List[str] = Field(default_factory=list, description="Downstream services receiving the event")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_timestamp: Optional[datetime] = None
    processing_time_ms: float = 0.0
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class WIS2NotificationMessage(BaseModel):
    """Standard WMO Information System 2.0 (WIS2.0) Notification Message schema.

    Conforms to WMO-No. 1061 / WIS2 Notification Message specification (GeoJSON Feature).
    Used to receive notifications of new meteorological data products available for retrieval.
    """
    id: str = Field(description="Unique message identifier")
    type: str = Field(default="Feature", description="GeoJSON Feature type")
    geometry: Optional[Dict[str, Any]] = Field(default=None, description="GeoJSON geometry (Point or Polygon)")
    properties: Dict[str, Any] = Field(
        description="WIS2 metadata: data_id, pubtime, integrity, links, content, centre_id"
    )
    links: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Links to canonical data object, update notification, or documentation"
    )
    topic: str = Field(description="WMO WIS2 topic hierarchy (e.g. 'origin/a/wis2/in-imd/data/core/weather/surface-based-observations/synop')")

    def to_meteorological_event(self) -> MeteorologicalEvent:
        """Converts WIS2 notification into SkyZen normalized MeteorologicalEvent."""
        pub_time_str = self.properties.get("pubtime")
        try:
            event_dt = datetime.fromisoformat(pub_time_str) if pub_time_str else datetime.now(timezone.utc)
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
        except Exception:
            event_dt = datetime.now(timezone.utc)

        # Extract coordinates if geometry is Point
        lat, lon = None, None
        if self.geometry and self.geometry.get("type") == "Point":
            coords = self.geometry.get("coordinates", [])
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]

        data_id = self.properties.get("data_id", self.id)
        centre_id = self.properties.get("centre_id", "in-imd")

        source_meta = EventSourceMetadata(
            provider_id=f"WIS2_{centre_id.upper()}",
            source_name=f"WMO WIS2.0 Node ({centre_id})",
            transport="WIS2_NOTIFICATION",
            protocol_version="WIS2.0-v1",
            institution="WMO / IMD",
            authority_level="authoritative_official",
            metadata={"data_id": data_id, "wis2_topic": self.topic}
        )

        return MeteorologicalEvent(
            event_id=self.id,
            event_type=MeteorologicalEventType.WEATHER_OBSERVATION,
            topic=self.topic,
            event_timestamp=event_dt,
            source=source_meta,
            location_name=self.properties.get("station_name", "WIS2_Station"),
            latitude=lat,
            longitude=lon,
            payload=self.properties
        )
