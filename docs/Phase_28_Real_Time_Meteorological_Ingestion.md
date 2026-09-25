# SkyZen Phase 28: Real-Time Meteorological Ingestion Architecture

## Executive Summary

SkyZen Phase 28 establishes an extensible, production-ready real-time meteorological ingestion architecture. The system is designed to consume streaming meteorological observations, radar telemetry, and institutional alerts from modern international distribution networks—specifically **WMO Information System 2.0 (WIS2.0)** and streaming transport protocols such as **MQTT** and **WebSockets**.

The implementation adheres to strict operational integrity requirements:
1. **Explicit Health States**: The system disambiguates between `CONFIGURED`, `AVAILABLE`, `UNAVAILABLE`, and `NOT_CONFIGURED`. It never simulates or fabricates a live WIS2.0 or MQTT connection when no broker or endpoint is configured.
2. **Deterministic Deduplication & Staleness**: Every event is validated using bounded LRU deduplication (both by `event_id` and SHA-256 content hash) and stale-event thresholds.
3. **Out-of-Order Safety**: Observations arriving out-of-order are recorded in the recovery buffer for historical integrity, but are prevented from clobbering active real-time current weather state.
4. **Authoritative Warning Precedence**: Official India Meteorological Department (IMD) warnings unconditionally override numerical forecasts and sensor telemetry, and are routed immediately to the push notification engine.
5. **Disconnected Client Recovery**: Clients that drop connection can replay missed events from an in-memory ring buffer or recover full state via REST endpoints.

---

## Architecture Overview

```
                      [ External Meteorological Producers ]
                                       |
          +----------------------------+----------------------------+
          |                            |                            |
          v                            v                            v
   [ MQTT Transport ]          [ WIS2.0 Transport ]         [ REST Ingestion ]
 (GenericMQTTAdapter)       (WIS2NotificationAdapter)      (FastAPI Endpoint)
          |                            |                            |
          +----------------------------+----------------------------+
                                       |
                                       v
                    +------------------------------------+
                    |    RealTimeIngestionPipeline       |
                    +------------------------------------+
                    |  1. Bounded Deduplication          |
                    |     - event_id LRU                 |
                    |     - SHA-256 payload hash LRU     |
                    |  2. Freshness & Staleness Check    |
                    |     - Stale threshold rejection    |
                    |  3. Out-of-Order Stream Tracking   |
                    |     - Stream sequence & watermarks |
                    |  4. In-Memory Recovery Ring Buffer |
                    +------------------------------------+
                                       |
         +-----------------------------+-----------------------------+
         |                             |                             |
         v                             v                             v
[ Weather Updates ]          [ Official Warnings ]         [ WebSocket Hub ]
- Provider Cache (TTL)       - IMD Priority Storage        (Client Location Sub)
- High-water mark state      - FCM Push Notification Engine          |
                                                                     v
                                                          [ Connected Clients ]
```

---

## 1. Normalized Meteorological Event Schema

Located in [`backend/services/realtime_schemas.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/services/realtime_schemas.py):

### Event Types (`MeteorologicalEventType`)
- `WEATHER_OBSERVATION`: Surface station telemetry (temp, humidity, wind, precip).
- `OFFICIAL_ALERT`: Institutional emergency warning (IMD, WMO, NDMA).
- `STATION_TELEMETRY`: Automated Weather Station (AWS) raw diagnostics.
- `RADAR_NOWCAST`: High-frequency radar reflectivity and Doppler vectors.
- `NWP_STREAM_UPDATE`: Real-time numerical model cycle packet.

### Source Metadata & Provenance (`EventSourceMetadata`)
Tracks the exact origin and authority of incoming messages:
- `provider_id`: Unique identifier (e.g., `AWS_COIMBATORE_01`, `IN_IMD_CAP`).
- `source_name`: Human-readable name.
- `transport`: Delivery mechanism (`REST`, `MQTT`, `WIS2_NOTIFICATION`, `WEBSOCKET`).
- `institution`: Responsible meteorological agency (e.g., `India Meteorological Department`, `WMO`).
- `authority_level`: `authoritative_official`, `operational_network`, `research_community`, or `experimental`.

### Message Envelope (`MeteorologicalEvent`)
- `event_id`: Unique message identifier.
- `topic`: Hierarchical routing topic (e.g., `skyzen/met/surface/delhi`, `origin/a/wis2/in-imd/data/core/...`).
- `event_timestamp`: Time the meteorological event or observation was measured.
- `ingested_at`: UTC timestamp when SkyZen received the packet.
- `location_name`, `latitude`, `longitude`, `elevation_m`: Geospatial binding.
- `sequence_number`: Producer sequence counter for out-of-order detection.
- `content_hash`: Deterministic SHA-256 hash of coordinates, event type, timestamp, and payload.

---

## 2. Ingestion Pipeline & Reliability Controls

Located in [`backend/services/realtime_ingestion_pipeline.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/services/realtime_ingestion_pipeline.py):

### A. Deduplication Engine (`DuplicateDetector`)
Dual-layer duplicate suppression:
1. **Identifier Tracking**: LRU cache of recently seen `event_id`s.
2. **Content Hash Tracking**: SHA-256 hash computed across normalized payload keys. Protects against upstream producers that assign random UUIDs to identical retransmissions.

### B. Freshness & Staleness (`stale_threshold_seconds`)
Rejects observations older than the configured threshold (`settings.REALTIME_STALE_THRESHOLD_SECONDS`, default 3600s). Prevents historic batches or backfilled datasets from masquerading as current real-time weather.

### C. Out-of-Order Handling (`OutOfOrderTracker`)
Streams are tracked per `(topic, location)`:
- High-water marks track the latest observation timestamp and sequence number.
- When an event arrives with an older timestamp than the high-water mark, it is flagged as `ACCEPTED_OUT_OF_ORDER`.
- **Active State Guard**: The event is accepted into the recovery buffer for historical correctness, but is **NOT** written to the active current weather cache (`realtime:current:...`), ensuring newer telemetry is never overwritten by delayed packets.

### D. Exponential Backoff & Retry (`ExponentialBackoff`)
Full-jitter exponential backoff for downstream dispatchers (such as push notification delivery or broker reconnects).

---

## 3. Streaming Adapter Interfaces & Boundaries

Located in [`backend/services/realtime_adapters.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/services/realtime_adapters.py):

### Provider Health State Enum
Explicitly distinguishes:
- `CONFIGURED`: Broker host/endpoint is provided in settings.
- `AVAILABLE`: Broker is connected, responsive, and healthy.
- `UNAVAILABLE`: Broker host is configured, but connection failed or dropped.
- `NOT_CONFIGURED`: Default state when no connection URL or broker is configured.

```python
class IngestionProviderState(str, Enum):
    CONFIGURED = "CONFIGURED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
```

### A. Generic MQTT Adapter (`GenericMQTTAdapter`)
- Conforms to standard pub/sub contracts (`connect()`, `disconnect()`, `subscribe()`, `publish()`).
- Does **not** require an external broker running during tests or local operation.
- Gracefully reports `NOT_CONFIGURED` when `MQTT_ENABLED=False` or `MQTT_BROKER_HOST=None`.
- Raises `ProviderUnavailableError` if attempted without configuration, preventing false availability claims.

### B. WMO WIS2.0 Boundary Adapter (`WIS2NotificationAdapter`)
- Compliant with **WMO-No. 1061 / WIS2 Notification Message** specification (GeoJSON Feature with `canonical_href`, data ID, geometry, and ISO 8601 validity period).
- Validates the GeoJSON schema, parses geometry and topic hierarchies (`origin/a/wis2/...`), and converts the notification into a normalized `MeteorologicalEvent`.
- Reports `NOT_CONFIGURED` when `WIS2_ENABLED=False` or `WIS2_BROKER_ENDPOINT=None`.

### C. Deterministic Adapter (`DeterministicStreamingAdapter`)
A test double providing deterministic connection failure simulation, packet injection, reconnect counting, and latency simulation.

---

## 4. Real-Time WebSocket Hub & Client Recovery

Located in [`backend/services/websocket_manager.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/services/websocket_manager.py) and [`backend/api/realtime.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/api/realtime.py):

### WebSocket Hub (`MeteorologicalWebSocketManager`)
- Endpoint: `ws://<host>:<port>/weather/realtime/ws?client_id=...&locations=Delhi,Mumbai&include_alerts=true`
- **Location Filtering**: Clients receive updates tailored to their subscribed locations or global warnings.
- **Graceful Lifecycle**: Handles client drops, abnormal disconnects, and stale client sweep without leaking memory.

### Disconnected Client Recovery
Clients that disconnect can recover in two ways:
1. **Replay Buffer API**: `GET /weather/realtime/recovery?since=<iso8601>&limit=100` allows clients to fetch all events missed while offline.
2. **Current State REST**: `GET /weather/current` and `GET /alerts/live` provide canonical current state.

---

## 5. Official Warning Priority & Safety

> **Safety Invariant**: Official warnings issued by authorized authorities (IMD, NDMA, State Disaster Management) take absolute priority over real-time station telemetry and numerical model forecasts.

When an `OFFICIAL_ALERT` is ingested:
1. It is stored under the `realtime:alerts:{location}:{event_id}` authoritative cache namespace.
2. If severity is `extreme`, `high`, `red`, or `orange`, it is synchronously passed to `NotificationService.send_alert_notification` for push broadcast.
3. Broadcasted immediately to all active WebSocket clients regardless of fine-grained location filters.

---

## 6. Deterministic Verification & Test Coverage

The test suite in [`tests/test_realtime_ingestion.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/tests/test_realtime_ingestion.py) provides 100% deterministic testing without external dependencies:

| Test Case | Verification Target |
|:---|:---|
| `test_duplicate_event_id_rejection` | Identical `event_id` rejected on secondary ingestion. |
| `test_duplicate_content_hash_rejection` | Identical payload with randomized UUID rejected via SHA-256 content hash. |
| `test_stale_event_rejection` | Events older than threshold rejected as `REJECTED_STALE`. |
| `test_fresh_event_accepted` | Events within threshold processed and routed successfully. |
| `test_out_of_order_event_preserves_current_state` | Delayed observation accepted out-of-order without overwriting newer state. |
| `test_disconnected_client_recovery_replay` | Recovery buffer replays events missed by disconnected client. |
| `test_deterministic_streaming_adapter_reconnect` | Adapter simulates network drop, raises error during drop, and recovers upon reconnect. |
| `test_unconfigured_mqtt_adapter_returns_not_configured` | Unconfigured MQTT adapter returns `NOT_CONFIGURED` and `is_available=False`. |
| `test_unconfigured_mqtt_adapter_connect_raises` | Connecting unconfigured MQTT adapter raises `ProviderUnavailableError`. |
| `test_unconfigured_wis2_adapter_returns_not_configured` | Unconfigured WIS2 adapter returns `NOT_CONFIGURED`. |
| `test_api_websocket_client_lifecycle` | WebSocket connects, receives welcome packet, pings, and disconnects gracefully. |
| `test_websocket_broadcast_location_filtering` | Subscribed location receives broadcast; unsubscribed location receives nothing. |
| `test_official_alert_routing` | Official IMD alert routes to warnings and FCM notification service. |
| `test_wis2_notification_boundary_conversion` | WMO-No. 1061 GeoJSON converted into normalized event. |
| `test_api_realtime_status` | Status endpoint returns state of pipeline and unconfigured adapters. |
| `test_api_realtime_recovery` | HTTP recovery endpoint returns missed events filtered by timestamp. |
