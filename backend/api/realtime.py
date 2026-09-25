"""Real-Time Meteorological Ingestion & Streaming API Router.

Phase 28: Real-Time Meteorological Ingestion.
Endpoints:
1. GET /weather/realtime/status: Ingestion pipeline & adapter health states.
2. POST /weather/realtime/ingest: Direct HTTP event ingestion.
3. POST /weather/realtime/wis2/notification: WMO WIS2.0 notification ingestion boundary.
4. GET /weather/realtime/recovery: Disconnected client state recovery replay.
5. WebSocket /weather/realtime/ws: Live WebSocket feed with subscription filtering.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, List, Optional
import uuid
from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect

from backend.config.settings import settings
from backend.services.realtime_schemas import (
    MeteorologicalEvent,
    EventIngestionResult,
    WIS2NotificationMessage,
)
from backend.services.realtime_ingestion_pipeline import ingestion_pipeline
from backend.services.realtime_adapters import mqtt_adapter, wis2_adapter
from backend.services.websocket_manager import ws_manager

logger = logging.getLogger("weathergpt.api.realtime")

router = APIRouter(prefix="/weather/realtime", tags=["RealTime Meteorological Ingestion"])


@router.get("/status")
async def get_realtime_status() -> Dict[str, Any]:
    """Returns the operational health, configuration status, and rejection metrics for all real-time ingestion subsystems."""
    metrics = ingestion_pipeline.get_pipeline_metrics()
    return {
        "realtime_enabled": settings.REALTIME_INGESTION_ENABLED,
        "pipeline": metrics,
        "adapters": {
            "mqtt": mqtt_adapter.get_adapter_metadata(),
            "wis2": wis2_adapter.get_adapter_metadata(),
            "websocket": ws_manager.get_diagnostics()
        },
        "safety_hierarchy": "Official IMD alerts take unconditional priority over real-time telemetry."
    }


@router.post("/ingest", response_model=EventIngestionResult)
async def ingest_meteorological_event(event: MeteorologicalEvent) -> EventIngestionResult:
    """Ingests a normalized meteorological event through deduplication, staleness filtering,

    out-of-order tracking, and multi-channel routing.
    """
    if not settings.REALTIME_INGESTION_ENABLED:
        raise HTTPException(status_code=503, detail="Real-time meteorological ingestion pipeline is currently disabled.")

    return await ingestion_pipeline.ingest_event(event)


@router.post("/wis2/notification", response_model=EventIngestionResult)
async def ingest_wis2_notification(notification: WIS2NotificationMessage) -> EventIngestionResult:
    """Ingests a WMO WIS2.0 Notification Message GeoJSON Feature.

    Boundary adapter converts the message and routes it without fabricating a live broker connection.
    """
    return await wis2_adapter.process_notification(notification)


@router.get("/recovery")
async def get_recovery_events(
    since: Optional[str] = Query(None, description="ISO 8601 UTC timestamp to replay events since"),
    since_id: Optional[str] = Query(None, description="Last acknowledged event_id"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of historical events to recover")
) -> Dict[str, Any]:
    """Replay buffer endpoint enabling disconnected clients to recover missed weather updates and alerts."""
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed 'since' timestamp format. Use ISO 8601 UTC.")

    events = await ingestion_pipeline.get_recent_events(
        since_timestamp=since_dt,
        since_event_id=since_id,
        limit=limit
    )

    return {
        "recovered_count": len(events),
        "events": [e.model_dump() for e in events]
    }


@router.websocket("/ws")
async def realtime_weather_websocket(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None),
    locations: Optional[str] = Query(None)
):
    """Live WebSocket stream pushing verified meteorological events and severe warnings to connected clients.

    Supports location filtering and graceful disconnect handling.
    """
    if not settings.REALTIME_WS_ENABLED:
        await websocket.close(code=1003, reason="WebSocket streaming is disabled.")
        return

    cid = client_id or f"client_{uuid.uuid4().hex[:8]}"
    sub_locations = [loc.strip() for loc in locations.split(",")] if locations else None

    sub = await ws_manager.connect(websocket, client_id=cid, locations=sub_locations)

    # Send initial welcome and synchronization handshake
    welcome_msg = {
        "type": "CONNECTION_ESTABLISHED",
        "client_id": cid,
        "subscriptions": list(sub.locations) if sub.locations else ["ALL"],
        "connected_at": sub.connected_at.isoformat(),
        "info": "Real-time SkyZen verified meteorological stream. Recover missed events via /recovery."
    }
    await ws_manager.send_personal(cid, welcome_msg)

    try:
        while True:
            # Keep connection alive; handle potential client heartbeats or subscription changes
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                if msg.get("action") == "subscribe" and "location" in msg:
                    sub.locations.add(msg["location"].lower().strip())
                    await ws_manager.send_personal(cid, {
                        "type": "SUBSCRIPTION_UPDATED",
                        "subscriptions": list(sub.locations)
                    })
                elif msg.get("action") == "ping":
                    await ws_manager.send_personal(cid, {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
            except Exception:
                pass
    except (WebSocketDisconnect, Exception) as e:
        logger.debug(f"[WebSocketEndpoint] Client {cid} connection closed: {e}")
    finally:
        await ws_manager.disconnect(cid)
