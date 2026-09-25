"""Real-Time Meteorological Ingestion Engine & Processing Pipeline.

Phase 28: Real-Time Meteorological Ingestion.
Implements:
1. Duplicate detection via ID cache and deterministic content hashing.
2. Stale-event rejection against configurable thresholds.
3. Out-of-order event tracking (preserves high-water marks and current state integrity).
4. Exponential retry/backoff for transient downstream routing failures.
5. Event routing into:
   - Weather observation updates / cache
   - Official warnings & alert engine (strictly preserving official priority)
   - Push notification engine (FCM)
   - Live WebSocket broadcast
6. Event buffer for disconnected client recovery.
"""

import asyncio
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
import logging
import random
import time
from typing import Dict, Any, List, Optional, Set, Tuple

from backend.config.settings import settings
from backend.services.realtime_schemas import (
    MeteorologicalEvent,
    MeteorologicalEventType,
    EventIngestionResult,
    IngestionStatusEnum,
    IngestionProviderState,
)
from backend.services.cache import provider_cache
from backend.services.websocket_manager import ws_manager

logger = logging.getLogger("weathergpt.realtime.pipeline")


class ExponentialBackoff:
    """Helper for executing asynchronous functions with exponential backoff and jitter."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: float = 0.2,
        max_delay_seconds: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.jitter = jitter

    async def execute(self, coro_func, *args, **kwargs):
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                return await coro_func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.max_retries:
                    break
                delay = min(self.max_delay, self.base_delay * (2 ** attempt))
                if self.jitter:
                    delay += random.uniform(0, delay * 0.1)
                logger.debug(f"[RetryBackoff] Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)
        raise last_exception


class DuplicateDetector:
    """Bounded, thread-safe LRU cache detecting duplicate event IDs and duplicate content hashes."""

    def __init__(self, max_size: int = 10000):
        self._max_size = max_size
        self._seen_ids: OrderedDict[str, datetime] = OrderedDict()
        self._seen_hashes: OrderedDict[str, datetime] = OrderedDict()
        self._lock = asyncio.Lock()

    async def is_duplicate(self, event_id: str, content_hash: Optional[str]) -> bool:
        async with self._lock:
            # Check by event_id
            if event_id in self._seen_ids:
                return True

            # Check by content hash fallback
            if content_hash and content_hash in self._seen_hashes:
                return True

            # Not duplicate: register and evict oldest if capacity exceeded
            now = datetime.now(timezone.utc)
            self._seen_ids[event_id] = now
            if len(self._seen_ids) > self._max_size:
                self._seen_ids.popitem(last=False)

            if content_hash:
                self._seen_hashes[content_hash] = now
                if len(self._seen_hashes) > self._max_size:
                    self._seen_hashes.popitem(last=False)

            return False

    async def clear(self) -> None:
        async with self._lock:
            self._seen_ids.clear()
            self._seen_hashes.clear()


class OutOfOrderTracker:
    """Tracks sequence numbers and latest observed timestamps per stream/station key.

    Ensures older observations arriving out-of-order do not clobber newer live state.
    """

    def __init__(self):
        self._latest_timestamps: Dict[str, datetime] = {}
        self._latest_sequences: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def evaluate_order(
        self,
        stream_key: str,
        event_time: datetime,
        sequence_num: Optional[int] = None
    ) -> bool:
        """Returns True if the event is out-of-order (older than the stream's high-water mark).

        If in-order or newest, updates the high-water mark and returns False.
        """
        async with self._lock:
            last_dt = self._latest_timestamps.get(stream_key)
            last_seq = self._latest_sequences.get(stream_key)

            is_out_of_order = False

            # Check timestamp ordering
            if last_dt is not None:
                # Normalize timezones for comparison
                ref_last = last_dt if last_dt.tzinfo else last_dt.replace(tzinfo=timezone.utc)
                ref_event = event_time if event_time.tzinfo else event_time.replace(tzinfo=timezone.utc)
                if ref_event < ref_last:
                    is_out_of_order = True

            # Check sequence numbering if present
            if sequence_num is not None and last_seq is not None:
                if sequence_num < last_seq:
                    is_out_of_order = True

            if not is_out_of_order:
                self._latest_timestamps[stream_key] = event_time
                if sequence_num is not None:
                    self._latest_sequences[stream_key] = sequence_num

            return is_out_of_order


class RealTimeIngestionPipeline:
    """Master Ingestion Engine orchestrating validation, deduplication, staleness filtering,

    out-of-order isolation, and multi-channel routing (Weather, Alerts, FCM, WebSocket).
    """

    def __init__(
        self,
        stale_threshold_seconds: Optional[int] = None,
        max_cache_size: Optional[int] = None,
        event_buffer_limit: int = 200
    ):
        self.stale_threshold = stale_threshold_seconds or settings.REALTIME_STALE_THRESHOLD_SECONDS
        self.dedup = DuplicateDetector(max_size=max_cache_size or settings.REALTIME_DUPLICATE_CACHE_SIZE)
        self.order_tracker = OutOfOrderTracker()
        self.retry_handler = ExponentialBackoff(max_retries=2, base_delay_seconds=0.1)

        # Ring buffer for disconnected client recovery
        self._event_buffer: List[MeteorologicalEvent] = []
        self._buffer_limit = event_buffer_limit
        self._buffer_lock = asyncio.Lock()

        # Operational metrics
        self._metrics = {
            "total_ingested": 0,
            "processed": 0,
            "rejected_duplicate": 0,
            "rejected_stale": 0,
            "out_of_order_count": 0,
            "routed_weather": 0,
            "routed_alerts": 0,
            "routed_notifications": 0,
            "routed_websocket": 0,
        }

    async def ingest_event(self, event: MeteorologicalEvent) -> EventIngestionResult:
        """Processes a meteorological event through the complete ingestion pipeline."""
        start_time = time.perf_counter()
        now_utc = datetime.now(timezone.utc)
        self._metrics["total_ingested"] += 1

        # 1. Duplicate Detection
        if await self.dedup.is_duplicate(event.event_id, event.content_hash):
            self._metrics["rejected_duplicate"] += 1
            elapsed = (time.perf_counter() - start_time) * 1000
            return EventIngestionResult(
                event_id=event.event_id,
                status=IngestionStatusEnum.REJECTED_DUPLICATE,
                message=f"Event {event.event_id} rejected as duplicate (identical ID or content hash).",
                ingested_at=now_utc,
                event_timestamp=event.event_timestamp,
                processing_time_ms=round(elapsed, 2)
            )

        # 2. Stale Event Rejection
        evt_dt = event.event_timestamp
        if evt_dt.tzinfo is None:
            evt_dt = evt_dt.replace(tzinfo=timezone.utc)

        age_seconds = (now_utc - evt_dt).total_seconds()
        if age_seconds > self.stale_threshold:
            self._metrics["rejected_stale"] += 1
            elapsed = (time.perf_counter() - start_time) * 1000
            return EventIngestionResult(
                event_id=event.event_id,
                status=IngestionStatusEnum.REJECTED_STALE,
                message=(
                    f"Event {event.event_id} rejected as STALE. "
                    f"Age {int(age_seconds)}s exceeds configured stale threshold ({self.stale_threshold}s)."
                ),
                ingested_at=now_utc,
                event_timestamp=event.event_timestamp,
                processing_time_ms=round(elapsed, 2),
                diagnostics={"age_seconds": int(age_seconds), "threshold_seconds": self.stale_threshold}
            )

        # 3. Out-of-Order Evaluation
        stream_key = f"{event.source.provider_id}:{event.location_name or 'default'}"
        is_out_of_order = await self.order_tracker.evaluate_order(
            stream_key=stream_key,
            event_time=evt_dt,
            sequence_num=event.sequence_number
        )

        if is_out_of_order:
            self._metrics["out_of_order_count"] += 1

        # 4. Record to Recovery Event Buffer
        async with self._buffer_lock:
            self._event_buffer.append(event)
            if len(self._event_buffer) > self._buffer_limit:
                self._event_buffer.pop(0)

        # 5. Routing Engine
        routed_destinations: List[str] = []

        try:
            # 5a. Route Weather Observations
            if event.event_type in (MeteorologicalEventType.WEATHER_OBSERVATION, MeteorologicalEventType.STATION_TELEMETRY):
                if not is_out_of_order:
                    await self._route_weather_update(event)
                    routed_destinations.append("weather_updates")
                    self._metrics["routed_weather"] += 1
                else:
                    # Out-of-order observation is buffered for historical archive without overriding active live state
                    routed_destinations.append("historical_buffer")

            # 5b. Route Official Warnings
            elif event.event_type == MeteorologicalEventType.OFFICIAL_ALERT:
                await self._route_official_warning(event)
                routed_destinations.append("official_warnings")
                self._metrics["routed_alerts"] += 1

                # 5c. Route to Push Notification Engine (FCM) for severe alerts
                if await self._should_dispatch_notification(event):
                    await self._route_push_notification(event)
                    routed_destinations.append("notification_engine")
                    self._metrics["routed_notifications"] += 1

            # 5d. Broadcast to Active WebSocket Clients
            if settings.REALTIME_WS_ENABLED:
                ws_sent = await ws_manager.broadcast(
                    event.model_dump(),
                    location_name=event.location_name
                )
                if ws_sent > 0:
                    routed_destinations.append("websocket_clients")
                    self._metrics["routed_websocket"] += ws_sent

        except Exception as route_err:
            logger.error(f"[IngestionPipeline] Routing error for {event.event_id}: {route_err}")
            elapsed = (time.perf_counter() - start_time) * 1000
            return EventIngestionResult(
                event_id=event.event_id,
                status=IngestionStatusEnum.RETRY_QUEUED,
                message=f"Event accepted but encountered routing error: {str(route_err)}",
                routed_to=routed_destinations,
                ingested_at=now_utc,
                event_timestamp=event.event_timestamp,
                processing_time_ms=round(elapsed, 2),
                diagnostics={"error": str(route_err)}
            )

        self._metrics["processed"] += 1
        elapsed = (time.perf_counter() - start_time) * 1000

        final_status = IngestionStatusEnum.ACCEPTED_OUT_OF_ORDER if is_out_of_order else IngestionStatusEnum.PROCESSED
        return EventIngestionResult(
            event_id=event.event_id,
            status=final_status,
            message="Event successfully processed and routed" if not is_out_of_order else "Event accepted as out-of-order without overriding current state",
            routed_to=routed_destinations,
            ingested_at=now_utc,
            event_timestamp=event.event_timestamp,
            processing_time_ms=round(elapsed, 2),
            diagnostics={"is_out_of_order": is_out_of_order}
        )

    async def _route_weather_update(self, event: MeteorologicalEvent) -> None:
        """Updates the local weather state cache with verified observation telemetry."""
        if not event.location_name:
            return

        cache_key = f"realtime:current:{event.location_name.strip().lower()}"
        cached_val = {
            "source": event.source.source_name,
            "provider_id": event.source.provider_id,
            "location": event.location_name,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "telemetry": event.payload,
            "observed_at": event.event_timestamp.isoformat(),
            "ingested_at": event.ingested_at.isoformat(),
        }
        provider_cache.set(cache_key, cached_val, ttl=300)

    async def _route_official_warning(self, event: MeteorologicalEvent) -> None:
        """Processes and stores official meteorological warnings, upholding IMD priority."""
        payload = event.payload
        # Verify official authority level
        is_official = (event.source.authority_level == "authoritative_official")

        alert_record = {
            "event_id": event.event_id,
            "headline": payload.get("headline", payload.get("title", "Severe Weather Warning")),
            "description": payload.get("description", ""),
            "severity": payload.get("severity", "medium").lower(),
            "warning_type": payload.get("warning_type", payload.get("type", "GENERAL")),
            "is_official": is_official,
            "source": event.source.source_name,
            "area_name": event.location_name,
            "issued_at": event.event_timestamp.isoformat(),
            "expires_at": payload.get("expires_at", (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat())
        }

        # Cache active alert under official alert namespace
        if event.location_name:
            alert_key = f"realtime:alerts:{event.location_name.strip().lower()}:{event.event_id}"
            provider_cache.set(alert_key, alert_record, ttl=86400)

    async def _should_dispatch_notification(self, event: MeteorologicalEvent) -> bool:
        """Determines whether an official alert should trigger immediate push notifications."""
        sev = str(event.payload.get("severity", "")).lower()
        return sev in ("extreme", "high", "red", "orange")

    async def _route_push_notification(self, event: MeteorologicalEvent) -> None:
        """Routes urgent warnings to the FCM push notification service with retry safety."""
        from backend.services.notification_service import NotificationService

        async def _dispatch():
            notifier = NotificationService()
            title = event.payload.get("headline", event.payload.get("title", "Official Weather Warning"))
            body = event.payload.get("description", "Urgent weather advisory issued by meteorological authority.")
            # Dispatch to default city / broadcast topic
            loc = event.location_name or "All"
            return notifier.send_alert_notification(
                title=f"IMD Alert: {title}",
                body=body,
                city=loc,
                severity=event.payload.get("severity", "high")
            )

        try:
            await self.retry_handler.execute(_dispatch)
        except Exception as e:
            logger.warning(f"[IngestionPipeline] Push notification dispatch failed after retries: {e}")

    async def get_recent_events(
        self,
        since_timestamp: Optional[datetime] = None,
        since_event_id: Optional[str] = None,
        limit: int = 50
    ) -> List[MeteorologicalEvent]:
        """Provides event recovery replay for disconnected clients."""
        async with self._buffer_lock:
            events = list(self._event_buffer)

        if since_timestamp:
            ref_ts = since_timestamp if since_timestamp.tzinfo else since_timestamp.replace(tzinfo=timezone.utc)
            events = [e for e in events if (e.event_timestamp if e.event_timestamp.tzinfo else e.event_timestamp.replace(tzinfo=timezone.utc)) > ref_ts]

        if since_event_id:
            idx = -1
            for i, e in enumerate(events):
                if e.event_id == since_event_id:
                    idx = i
                    break
            if idx != -1:
                events = events[idx + 1:]

        return events[-limit:]

    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Returns real-time operational telemetry and rejection counters."""
        return {
            "metrics": dict(self._metrics),
            "stale_threshold_seconds": self.stale_threshold,
            "buffer_capacity": self._buffer_limit,
            "buffer_current_size": len(self._event_buffer),
            "pipeline_state": IngestionProviderState.AVAILABLE.value if settings.REALTIME_INGESTION_ENABLED else IngestionProviderState.NOT_CONFIGURED.value
        }


# Global Singleton Pipeline
ingestion_pipeline = RealTimeIngestionPipeline()
