import os
from typing import List
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class Settings(BaseModel):
    """Centralized Backend Configuration for WeatherGPT."""

    APP_NAME: str = "WeatherGPT-SIH26068"
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    DEBUG: bool = Field(default_factory=lambda: os.getenv("DEBUG", "true").lower() == "true")
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))

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
    SECRET_KEY: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "weathergpt-super-secret-production-key-sih26068-min-32-chars"))
    JWT_ALGORITHM: str = Field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")))

    # Logging Settings
    LOG_LEVEL: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # External Provider Keys & Configurations (Kept server-side only)
    IMD_API_KEY: str = Field(default_factory=lambda: os.getenv("IMD_API_KEY", ""))
    IMD_BASE_URL: str = Field(default_factory=lambda: os.getenv("IMD_BASE_URL", "https://api.imd.gov.in"))
    OPEN_METEO_BASE_URL: str = Field(default_factory=lambda: os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1"))
    WEATHER_HTTP_TIMEOUT_SECONDS: float = Field(default_factory=lambda: float(os.getenv("WEATHER_HTTP_TIMEOUT_SECONDS", "5.0")))
    WEATHER_HTTP_MAX_RETRIES: int = Field(default_factory=lambda: int(os.getenv("WEATHER_HTTP_MAX_RETRIES", "2")))
    WEATHER_CACHE_TTL_SECONDS: int = Field(default_factory=lambda: int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "300")))
    OPENAI_API_KEY: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

settings = Settings()
