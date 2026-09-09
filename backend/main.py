import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config.settings import settings
from backend.config.logging import logger
from backend.middleware import (
    register_exception_handlers,
    RequestIDMiddleware,
    RateLimiterMiddleware
)
from backend.db.init_db import init_db
from backend.api import health, auth, weather, locations, users, chat, voice

# Initialize Database on Module Import
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting WeatherGPT Backend Server...")
    init_db()
    yield
    logger.info("Shutting down WeatherGPT Backend Server...")

app = FastAPI(
    title=f"{settings.APP_NAME} Backend",
    description="Conversational AI for Weather Forecasting, Alerts, and Climate Information (Ministry of Earth Sciences / IMD)",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Register Centralized Sanitized Exception Handlers
register_exception_handlers(app)

# Register Middleware (Request ID & Rate Limiter)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimiterMiddleware, max_requests=60, window_seconds=60)

# Configurable CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers under /api/v1
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(weather.router, prefix=settings.API_V1_PREFIX)
app.include_router(locations.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(chat.router, prefix=settings.API_V1_PREFIX)
app.include_router(voice.router, prefix=settings.API_V1_PREFIX)

# Mount Static Frontend Directory if present
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
