"""Meteorological WebSocket Broadcast & Connection Manager.

Phase 28: Real-Time Meteorological Ingestion.
Provides WebSocket connection lifecycle management, location-based subscription routing,
graceful disconnect handling, and disconnected client broadcast resilience.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("weathergpt.realtime.ws")


class ClientSubscription:
    """Tracks state and subscriptions for a single connected WebSocket client."""
    def __init__(self, client_id: str, websocket: WebSocket, locations: Optional[List[str]] = None):
        self.client_id = client_id
        self.websocket = websocket
        self.locations: Set[str] = {loc.lower().strip() for loc in (locations or [])}
        self.connected_at = datetime.now(timezone.utc)
        self.last_activity = self.connected_at
        self.messages_sent: int = 0


class MeteorologicalWebSocketManager:
    """Manages WebSocket connections for streaming live verified meteorological events."""

    def __init__(self):
        self._active_connections: Dict[str, ClientSubscription] = {}
        self._lock = asyncio.Lock()

    @property
    def active_connections_count(self) -> int:
        return len(self._active_connections)

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        locations: Optional[List[str]] = None
    ) -> ClientSubscription:
        """Accepts and registers a new client WebSocket connection."""
        await websocket.accept()
        sub = ClientSubscription(client_id, websocket, locations)
        async with self._lock:
            self._active_connections[client_id] = sub
        logger.info(f"[WebSocketManager] Client connected: {client_id} (subscriptions={locations or ['ALL']})")
        return sub

    async def disconnect(self, client_id: str) -> None:
        """Gracefully removes a client connection."""
        async with self._lock:
            sub = self._active_connections.pop(client_id, None)
        if sub:
            try:
                await sub.websocket.close()
            except Exception:
                pass
            logger.info(f"[WebSocketManager] Client disconnected and cleaned up: {client_id}")

    async def broadcast(
        self,
        event_dict: Dict[str, Any],
        location_name: Optional[str] = None
    ) -> int:
        """Broadcasts a verified event to all matching subscribed clients.

        Gracefully prunes any disconnected clients without interrupting broadcast to others.
        """
        async with self._lock:
            subscribers = list(self._active_connections.values())

        if not subscribers:
            return 0

        target_loc = location_name.lower().strip() if location_name else None
        dead_clients: List[str] = []
        sent_count = 0

        for sub in subscribers:
            # Check location subscription match: if empty, client receives all updates
            if target_loc and sub.locations and target_loc not in sub.locations:
                continue

            try:
                await sub.websocket.send_json(event_dict)
                sub.messages_sent += 1
                sub.last_activity = datetime.now(timezone.utc)
                sent_count += 1
            except (WebSocketDisconnect, RuntimeError, Exception) as e:
                logger.debug(f"[WebSocketManager] Failed to send to {sub.client_id} (disconnected): {e}")
                dead_clients.append(sub.client_id)

        # Cleanup dead clients discovered during broadcast
        for cid in dead_clients:
            await self.disconnect(cid)

        return sent_count

    async def send_personal(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Sends a direct message to a specific client."""
        async with self._lock:
            sub = self._active_connections.get(client_id)

        if not sub:
            return False

        try:
            await sub.websocket.send_json(message)
            sub.messages_sent += 1
            sub.last_activity = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.debug(f"[WebSocketManager] Direct send to {client_id} failed: {e}")
            await self.disconnect(client_id)
            return False

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns health diagnostics and active connection telemetry."""
        return {
            "status": "AVAILABLE" if self._active_connections else "CONFIGURED",
            "active_clients": len(self._active_connections),
            "client_ids": list(self._active_connections.keys())
        }


# Global Singleton WebSocket Manager
ws_manager = MeteorologicalWebSocketManager()
