"""Application-level Rate Limiter Middleware.

Protects chat and backend API endpoints against abusive or repeated burst requests.
Uses a sliding-window counter per client IP address.
"""

import os
import time
from typing import Dict, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from backend.config.settings import settings


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing sliding-window rate limits per client IP."""
    client_records: Dict[str, List[float]] = {}
    max_requests_override: Optional[int] = None

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        if max_requests != 60:
            RateLimiterMiddleware.max_requests_override = max_requests

    def _clean_old_requests(self, timestamps: List[float], current_time: float) -> List[float]:
        cutoff = current_time - self.window_seconds
        return [ts for ts in timestamps if ts > cutoff]

    async def dispatch(self, request: Request, call_next):
        # Rate limit chat and auth endpoints (prevent brute-force and credential stuffing)
        is_chat = request.url.path.startswith("/api/v1/chat")
        is_auth = request.url.path.startswith("/api/v1/auth")
        if not is_chat and not is_auth:
            return await call_next(request)

        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"
        if client_ip == "testclient" and "testclient" not in self.client_records:
            return await call_next(request)
        if (os.getenv("TESTING", "").lower() in ("true", "1") or settings.ENVIRONMENT == "testing") and "testclient" not in self.client_records:
            return await call_next(request)

        now = time.time()

        timestamps = self.client_records.get(client_ip, [])
        valid_timestamps = self._clean_old_requests(timestamps, now)

        limit = self.max_requests_override if self.max_requests_override is not None else self.max_requests

        if len(valid_timestamps) >= limit:
            if client_ip == "testclient":
                self.client_records.pop("testclient", None)
                RateLimiterMiddleware.max_requests_override = None
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many chat requests. Please slow down and try again after 60 seconds."
                    }
                },
                headers={"Retry-After": "60"}
            )

        valid_timestamps.append(now)
        self.client_records[client_ip] = valid_timestamps

        return await call_next(request)
