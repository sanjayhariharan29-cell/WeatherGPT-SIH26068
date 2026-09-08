"""Request Correlation ID Middleware.

Attaches a unique UUID request_id to each incoming HTTP request,
propagates it through request.state and response headers (X-Request-ID),
and enables end-to-end request tracing across backend & AI components.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware attaching X-Request-ID correlation header to every request and response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
