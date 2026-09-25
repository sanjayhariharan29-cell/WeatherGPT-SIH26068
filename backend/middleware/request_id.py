"""Request Correlation ID & Access Logging Middleware.

Attaches a unique UUID request_id to each incoming HTTP request,
measures execution latency, propagates headers (X-Request-ID),
and writes structured operational log entries.
"""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from backend.config.logging import logger


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware attaching X-Request-ID correlation header and structured access logging."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            latency_ms = round((time.time() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(latency_ms)

            # Record API latency and error metrics in central observability engine
            from backend.services.observability_service import observability_service
            observability_service.record_api_request(status_code=response.status_code, latency_ms=latency_ms)

            logger.info(
                f"HTTP {request.method} {request.url.path} -> {response.status_code} "
                f"({latency_ms}ms) [request_id={request_id}]"
            )
            return response
        except Exception as exc:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            from backend.services.observability_service import observability_service
            observability_service.record_api_request(status_code=500, latency_ms=latency_ms)

            logger.error(
                f"HTTP {request.method} {request.url.path} -> EXCEPTION: {exc} "
                f"({latency_ms}ms) [request_id={request_id}]"
            )
            raise exc
