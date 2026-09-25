"""Deterministic Test Suite for SkyZen Phase 28: Real-Time Meteorological Ingestion.

Tests:
1. Duplicate event rejection (ID & content hash deduplication).
2. Stale event rejection against configured thresholds.
3. Out-of-order event tracking without clobbering active state.
4. Reconnection & replay recovery for disconnected clients.
5. Provider health states (CONFIGURED, AVAILABLE, UNAVAILABLE, NOT_CONFIGURED).
6. Unconfigured WIS2.0 and MQTT adapters returning NOT_CONFIGURED without mock fabrication.
7. WebSocket connection, broadcast, and graceful client disconnect.
8. Alert routing into notification pipeline preserving IMD priority.
9. WMO WIS2.0 notification message conversion and boundary ingestion.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.realtime_schemas import (
    MeteorologicalEvent,
    MeteorologicalEventType,
    EventSourceMetadata,
    EventIngestionResult,
    IngestionStatusEnum,
    IngestionProviderState,
    WIS2NotificationMessage,
)
from backend.services.realtime_ingestion_pipeline import (
    RealTimeIngestionPipeline,
    ingestion_pipeline,
    DuplicateDetector,
    OutOfOrderTracker,
)
from backend.services.realtime_adapters import (
    GenericMQTTAdapter,
    WIS2NotificationAdapter,
    DeterministicStreamingAdapter,
)
from backend.services.websocket_manager import MeteorologicalWebSocketManager, ws_manager
from backend.services.exceptions import ProviderUnavailableError
from backend.services.cache import provider_cache


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fresh_pipeline():
    """Returns an isolated ingestion pipeline instance for deterministic testing."""
    return RealTimeIngestionPipeline(stale_threshold_seconds=60, max_cache_size=100)


def create_sample_observation(
    event_id: str,
    event_time: datetime,
    temp_c: float = 28.0,
    location: str = "Coimbatore",
    sequence: int = 1
) -> MeteorologicalEvent:
    return MeteorologicalEvent(
        event_id=event_id,
        event_type=MeteorologicalEventType.WEATHER_OBSERVATION,
        topic="skyzen/met/surface/coimbatore",
        event_timestamp=event_time,
        location_name=location,
        latitude=11.0168,
        longitude=76.9558,
        sequence_number=sequence,
        source=EventSourceMetadata(
            provider_id="AWS_COIMBATORE_01",
            source_name="Automatic Weather Station Coimbatore",
            transport="REST",
            institution="IMD / AWS Network"
        ),
        payload={
            "temperature_c": temp_c,
            "humidity_pct": 65.0,
            "wind_speed_kmh": 14.0,
            "precipitation_mm": 0.0,
            "condition": "Partly Cloudy"
        }
    )


def create_sample_alert(
    event_id: str,
    event_time: datetime,
    severity: str = "extreme",
    headline: str = "Cyclone Warning"
) -> MeteorologicalEvent:
    return MeteorologicalEvent(
        event_id=event_id,
        event_type=MeteorologicalEventType.OFFICIAL_ALERT,
        topic="skyzen/alerts/coimbatore",
        event_timestamp=event_time,
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        source=EventSourceMetadata(
            provider_id="IMD_CAP_FEED",
            source_name="India Meteorological Department",
            transport="REST",
            authority_level="authoritative_official",
            institution="Ministry of Earth Sciences"
        ),
        payload={
            "headline": headline,
            "description": "Extremely heavy precipitation and gale winds expected.",
            "severity": severity,
            "warning_type": "CYCLONE",
            "expires_at": (event_time + timedelta(hours=24)).isoformat()
        }
    )


# ==============================================================================
# 1. Duplicate Detection
# ==============================================================================

@pytest.mark.asyncio
async def test_duplicate_event_id_rejection(fresh_pipeline):
    """Test identical event_id is rejected on secondary transmission."""
    now = datetime.now(timezone.utc)
    evt = create_sample_observation("evt_uniq_001", now)

    # First ingestion must be accepted/processed
    res1 = await fresh_pipeline.ingest_event(evt)
    assert res1.status in (IngestionStatusEnum.PROCESSED, IngestionStatusEnum.ACCEPTED)

    # Second identical event_id must be rejected as duplicate
    res2 = await fresh_pipeline.ingest_event(evt)
    assert res2.status == IngestionStatusEnum.REJECTED_DUPLICATE
    assert "duplicate" in res2.message.lower()


@pytest.mark.asyncio
async def test_duplicate_content_hash_rejection(fresh_pipeline):
    """Test duplicate detection catches identical payload even if event_id is randomly mutated."""
    now = datetime.now(timezone.utc)
    evt1 = create_sample_observation("evt_alpha_1", now, temp_c=31.5)
    evt2 = create_sample_observation("evt_alpha_2", now, temp_c=31.5)
    # Ensure content hashes match
    assert evt1.content_hash == evt2.content_hash

    res1 = await fresh_pipeline.ingest_event(evt1)
    assert res1.status in (IngestionStatusEnum.PROCESSED, IngestionStatusEnum.ACCEPTED)

    res2 = await fresh_pipeline.ingest_event(evt2)
    assert res2.status == IngestionStatusEnum.REJECTED_DUPLICATE


# ==============================================================================
# 2. Stale Event Rejection
# ==============================================================================

@pytest.mark.asyncio
async def test_stale_event_rejection(fresh_pipeline):
    """Test events with event_timestamp older than the configured threshold are rejected."""
    now = datetime.now(timezone.utc)
    # Threshold is 60 seconds on fresh_pipeline
    stale_time = now - timedelta(seconds=120)
    stale_evt = create_sample_observation("evt_stale_001", stale_time)

    res = await fresh_pipeline.ingest_event(stale_evt)
    assert res.status == IngestionStatusEnum.REJECTED_STALE
    assert "stale" in res.message.lower()
    assert "age_seconds" in res.diagnostics


@pytest.mark.asyncio
async def test_fresh_event_accepted(fresh_pipeline):
    """Test events within freshness threshold are accepted."""
    now = datetime.now(timezone.utc)
    fresh_time = now - timedelta(seconds=10)
    evt = create_sample_observation("evt_fresh_001", fresh_time)

    res = await fresh_pipeline.ingest_event(evt)
    assert res.status in (IngestionStatusEnum.PROCESSED, IngestionStatusEnum.ACCEPTED)


# ==============================================================================
# 3. Out-of-Order Event Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_out_of_order_event_preserves_current_state(fresh_pipeline):
    """
    CRITICAL REAL-TIME GUARANTEE:
    An older observation arriving out-of-order after a newer observation
    must NOT clobber the active current weather state.
    """
    now = datetime.now(timezone.utc)
    loc = "Coimbatore"
    cache_key = f"realtime:current:{loc.lower()}"

    # T1 (20s ago): Temp 25°C
    t1 = now - timedelta(seconds=20)
    evt_t1 = create_sample_observation("evt_order_1", t1, temp_c=25.0, sequence=1)
    res_t1 = await fresh_pipeline.ingest_event(evt_t1)
    assert res_t1.status == IngestionStatusEnum.PROCESSED
    cached_t1 = provider_cache.get(cache_key)
    assert cached_t1["telemetry"]["temperature_c"] == 25.0

    # T2 (5s ago): Temp 30°C (Newer)
    t2 = now - timedelta(seconds=5)
    evt_t2 = create_sample_observation("evt_order_2", t2, temp_c=30.0, sequence=2)
    res_t2 = await fresh_pipeline.ingest_event(evt_t2)
    assert res_t2.status == IngestionStatusEnum.PROCESSED
    cached_t2 = provider_cache.get(cache_key)
    assert cached_t2["telemetry"]["temperature_c"] == 30.0

    # T_late (15s ago): Temp 26°C (Arrives out of order, older than T2)
    t_late = now - timedelta(seconds=15)
    evt_late = create_sample_observation("evt_order_late", t_late, temp_c=26.0, sequence=1)
    res_late = await fresh_pipeline.ingest_event(evt_late)

    # Must be accepted as out-of-order without updating active live cache
    assert res_late.status == IngestionStatusEnum.ACCEPTED_OUT_OF_ORDER
    assert res_late.diagnostics["is_out_of_order"] is True
    # The active state MUST still be 30.0°C from T2, not clobbered by 26.0°C!
    cached_after = provider_cache.get(cache_key)
    assert cached_after["telemetry"]["temperature_c"] == 30.0


# ==============================================================================
# 4. Reconnect & Disconnected Client Recovery
# ==============================================================================

@pytest.mark.asyncio
async def test_disconnected_client_recovery_replay(fresh_pipeline):
    """Test replay buffer allows disconnected clients to recover missed events."""
    now = datetime.now(timezone.utc)
    for i in range(5):
        evt = create_sample_observation(f"evt_buf_{i}", now + timedelta(seconds=i), sequence=i)
        await fresh_pipeline.ingest_event(evt)

    # Replay all events since event 2
    recovered = await fresh_pipeline.get_recent_events(since_event_id="evt_buf_2")
    assert len(recovered) == 2
    assert [e.event_id for e in recovered] == ["evt_buf_3", "evt_buf_4"]


@pytest.mark.asyncio
async def test_deterministic_streaming_adapter_reconnect():
    """Test deterministic streaming adapter simulates connection drop and reconnect."""
    adapter = DeterministicStreamingAdapter("Mock_Stream")
    assert adapter.state == IngestionProviderState.AVAILABLE

    # Simulate network drop
    await adapter.disconnect()
    assert adapter.state == IngestionProviderState.UNAVAILABLE
    assert adapter.is_available is False

    # Ingesting during drop raises ProviderUnavailableError
    now = datetime.now(timezone.utc)
    evt = create_sample_observation("evt_drop_1", now)
    with pytest.raises(ProviderUnavailableError):
        await adapter.simulate_incoming_event(evt)

    # Reconnect successfully
    await adapter.connect()
    assert adapter.state == IngestionProviderState.AVAILABLE
    assert adapter.reconnect_count == 1

    # Delivery succeeds post-reconnect
    res = await adapter.simulate_incoming_event(evt)
    assert res.status in (IngestionStatusEnum.PROCESSED, IngestionStatusEnum.ACCEPTED)


# ==============================================================================
# 5. Provider Health States: CONFIGURED, AVAILABLE, UNAVAILABLE, NOT_CONFIGURED
# ==============================================================================

def test_unconfigured_mqtt_adapter_returns_not_configured():
    """
    REQUIREMENT:
    Do not simulate a live connection if unconfigured.
    System must expose NOT_CONFIGURED.
    """
    adapter = GenericMQTTAdapter(broker_host="", enabled=False)
    assert adapter.state == IngestionProviderState.NOT_CONFIGURED
    assert adapter.is_configured is False
    assert adapter.is_available is False

    meta = adapter.get_adapter_metadata()
    assert meta["status"] == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_unconfigured_mqtt_adapter_connect_raises():
    """Connecting to unconfigured MQTT adapter raises ProviderUnavailableError with NOT_CONFIGURED diagnostic."""
    adapter = GenericMQTTAdapter(broker_host="", enabled=False)
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await adapter.connect()

    assert exc_info.value.status == IngestionProviderState.NOT_CONFIGURED.value
    assert "not_configured" in str(exc_info.value).lower()


def test_unconfigured_wis2_adapter_returns_not_configured():
    """WMO WIS2.0 adapter exposes NOT_CONFIGURED when no live institutional endpoint exists."""
    adapter = WIS2NotificationAdapter(broker_endpoint="", enabled=False)
    assert adapter.state == IngestionProviderState.NOT_CONFIGURED
    assert adapter.is_configured is False


# ==============================================================================
# 6. WebSocket Connection, Broadcast, & Graceful Disconnect
# ==============================================================================

def test_api_websocket_client_lifecycle(client):
    """Test live WebSocket connection, welcome handshake, ping/pong, and graceful close."""
    with client.websocket_connect("/api/v1/weather/realtime/ws?client_id=tester_1&locations=Coimbatore") as ws:
        # 1. Handshake welcome
        welcome = ws.receive_json()
        assert welcome["type"] == "CONNECTION_ESTABLISHED"
        assert welcome["client_id"] == "tester_1"
        assert "coimbatore" in welcome["subscriptions"]

        # 2. Ping-pong
        ws.send_text('{"action": "ping"}')
        pong = ws.receive_json()
        assert pong["type"] == "pong"

    # Post-close, manager cleans up
    assert ws_manager.active_connections_count == 0


@pytest.mark.asyncio
async def test_websocket_broadcast_location_filtering():
    """Verify WebSocket manager routes broadcasts matching location subscriptions."""
    manager = MeteorologicalWebSocketManager()

    # Mock WebSocket instances
    class MockWS:
        def __init__(self):
            self.sent = []
            self.closed = False

        async def accept(self):
            pass

        async def send_json(self, data):
            if self.closed:
                raise RuntimeError("WebSocket closed")
            self.sent.append(data)

        async def close(self):
            self.closed = True

    ws_cbe = MockWS()
    ws_chn = MockWS()

    await manager.connect(ws_cbe, "cbe_client", locations=["Coimbatore"])
    await manager.connect(ws_chn, "chn_client", locations=["Chennai"])

    # Broadcast event for Coimbatore
    cbe_payload = {"location": "Coimbatore", "temp": 29.0}
    sent = await manager.broadcast(cbe_payload, location_name="Coimbatore")
    assert sent == 1
    assert len(ws_cbe.sent) == 1
    assert len(ws_chn.sent) == 0

    # Clean up
    await manager.disconnect("cbe_client")
    await manager.disconnect("chn_client")
    assert manager.active_connections_count == 0


# ==============================================================================
# 7. Alert Routing & Official Priority Preservation
# ==============================================================================

@pytest.mark.asyncio
async def test_official_alert_routing(fresh_pipeline):
    """Test official IMD warning is routed into official_warnings and notification_engine."""
    now = datetime.now(timezone.utc)
    alert_evt = create_sample_alert("alert_evt_999", now, severity="extreme")

    res = await fresh_pipeline.ingest_event(alert_evt)
    assert res.status == IngestionStatusEnum.PROCESSED
    assert "official_warnings" in res.routed_to
    assert "notification_engine" in res.routed_to

    # Verify cached under official alerts namespace
    alert_key = "realtime:alerts:coimbatore:alert_evt_999"
    cached = provider_cache.get(alert_key)
    assert cached is not None
    assert cached["is_official"] is True
    assert cached["severity"] == "extreme"


# ==============================================================================
# 8. WMO WIS2.0 Notification Conversion
# ==============================================================================

@pytest.mark.asyncio
async def test_wis2_notification_boundary_conversion():
    """Verify WMO WIS2.0 GeoJSON notification conforms to schema and produces normalized event."""
    wis2_data = {
        "id": "urn:wmo:md:in-imd:data.core.weather.surface.vomm",
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [80.18, 13.0]  # [lon, lat]
        },
        "properties": {
            "data_id": "VOMM_SYNOP_202609251200",
            "pubtime": datetime.now(timezone.utc).isoformat(),
            "station_name": "Chennai Meenambakkam",
            "centre_id": "in-imd",
            "temperature_c": 32.0,
            "humidity_pct": 78.0
        },
        "links": [
            {"rel": "canonical", "href": "https://wis2.imd.gov.in/data/VOMM_SYNOP.bufr4"}
        ],
        "topic": "origin/a/wis2/in-imd/data/core/weather/surface-based-observations/synop"
    }

    wis2_msg = WIS2NotificationMessage(**wis2_data)
    event = wis2_msg.to_meteorological_event()

    assert event.event_id == "urn:wmo:md:in-imd:data.core.weather.surface.vomm"
    assert event.latitude == 13.0
    assert event.longitude == 80.18
    assert event.source.provider_id == "WIS2_IN-IMD"
    assert event.source.authority_level == "authoritative_official"
    assert event.payload["temperature_c"] == 32.0


# ==============================================================================
# 9. Real-Time HTTP Endpoints
# ==============================================================================

def test_api_realtime_status(client):
    """Test GET /api/v1/weather/realtime/status returns expected schema and states."""
    resp = client.get("/api/v1/weather/realtime/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "pipeline" in data
    assert "adapters" in data
    assert data["adapters"]["mqtt"]["status"] in ["CONFIGURED", "AVAILABLE", "NOT_CONFIGURED"]
    assert data["adapters"]["wis2"]["status"] in ["CONFIGURED", "AVAILABLE", "NOT_CONFIGURED"]


def test_api_realtime_recovery(client):
    """Test GET /api/v1/weather/realtime/recovery returns recovery replay list."""
    resp = client.get("/api/v1/weather/realtime/recovery?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "recovered_count" in data
    assert isinstance(data["events"], list)
