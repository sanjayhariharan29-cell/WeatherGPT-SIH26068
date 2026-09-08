import os
from typing import List
from pydantic import BaseModel, Field

class Settings(BaseModel):
    """Centralized Backend Configuration for WeatherGPT."""

    APP_NAME: str = "WeatherGPT-SIH26068"
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    DEBUG: bool = Field(default_factory=lambda: os.getenv("DEBUG", "true").lower() == "true")
    API_V1_PREFIX: str = "/api/v1"

    # Database Settings
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./weathergpt.db"))

    # Security & CORS Settings
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "ALLOWED_ORIGINS",
                "http://localhost:8000,http://127.0.0.1:8000,*"
            ).split(",")
            if origin.strip()
        ]
    )
    SECRET_KEY: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"))

    # Logging Settings
    LOG_LEVEL: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # External Provider Keys (Kept server-side only)
    IMD_API_KEY: str = Field(default_factory=lambda: os.getenv("IMD_API_KEY", ""))
    OPENAI_API_KEY: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

settings = Settings()
