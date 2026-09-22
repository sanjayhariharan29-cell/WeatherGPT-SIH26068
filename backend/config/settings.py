import os
import sys
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    _root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _root_env.exists():
        load_dotenv(_root_env, override=False)
    _backend_env = Path(__file__).resolve().parent.parent / ".env"
    if _backend_env.exists():
        load_dotenv(_backend_env, override=False)
    load_dotenv(override=False)
except ImportError:
    pass

class Settings(BaseModel):
    """Centralized Backend Configuration for WeatherGPT."""

    APP_NAME: str = "WeatherGPT-SIH26068"
    ENVIRONMENT: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "production" if os.getenv("RENDER") == "true" else "development")
    )
    DEBUG: bool = Field(
        default_factory=lambda: (
            False
            if (os.getenv("RENDER") == "true" or os.getenv("ENVIRONMENT", "").lower() == "production")
            else (os.getenv("DEBUG", "true").lower() == "true")
        )
    )
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    DEMO_MODE: bool = Field(
        default_factory=lambda: (
            os.getenv("DEMO_MODE", "false").lower() == "true"
            if not (os.getenv("RENDER") == "true" or os.getenv("ENVIRONMENT", "").lower() == "production")
            else False
        )
    )

    # Database Settings
    DATABASE_URL: str = Field(
        default_factory=lambda: (
            f"sqlite:///{(Path(__file__).resolve().parent.parent.parent / os.getenv('DATABASE_URL', 'sqlite:///./weathergpt.db').replace('sqlite:///', '').lstrip('./')).resolve().as_posix()}"
            if os.getenv("DATABASE_URL", "sqlite:///./weathergpt.db").startswith("sqlite:///")
            and not os.getenv("DATABASE_URL", "sqlite:///./weathergpt.db").startswith("sqlite:////")
            and not (len(os.getenv("DATABASE_URL", "sqlite:///./weathergpt.db")) > 11 and os.getenv("DATABASE_URL", "sqlite:///./weathergpt.db")[10] == ":")
            else os.getenv("DATABASE_URL", "sqlite:///./weathergpt.db")
        )
    )

    # Security & CORS Settings
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "ALLOWED_ORIGINS",
                "*"
            ).split(",")
            if origin.strip()
        ]
    )
    SECRET_KEY: str = Field(default_factory=lambda: os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY") or "weathergpt-super-secret-production-key-sih26068-min-32-chars")
    JWT_ALGORITHM: str = Field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")))

    # Logging Settings
    LOG_LEVEL: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    IMD_API_KEY: str = Field(
        default_factory=lambda: (
            os.getenv("IMD_API_KEY")
            or (
                "ci-mock-imd-api-key"
                if (
                    "pytest" in sys.modules
                    or os.getenv("PYTEST_CURRENT_TEST")
                    or any("pytest" in arg for arg in sys.argv)
                )
                else ""
            )
        )
    )
    IMD_BASE_URL: str = Field(default_factory=lambda: os.getenv("IMD_BASE_URL", "https://api.imd.gov.in"))
    IMD_WARNINGS_API_URL: str = Field(default_factory=lambda: os.getenv("IMD_WARNINGS_API_URL", "https://mausam.imd.gov.in/api/warnings_district_api.php"))
    IMD_NOWCAST_API_URL: str = Field(default_factory=lambda: os.getenv("IMD_NOWCAST_API_URL", "https://mausam.imd.gov.in/api/nowcast_district_api.php"))
    IMD_GEOSERVER_WFS_URL: str = Field(default_factory=lambda: os.getenv("IMD_GEOSERVER_WFS_URL", "https://reactjs.imd.gov.in/geoserver/wfs"))
    IMD_NOWCAST_WFS_URL: str = Field(default_factory=lambda: os.getenv("IMD_NOWCAST_WFS_URL", "https://reactjs.imd.gov.in/geoserver/imd/wfs"))
    IMD_AUTH_HEADER: str = Field(default_factory=lambda: os.getenv("IMD_AUTH_HEADER", ""))
    IMD_ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("IMD_ENVIRONMENT", "test" if ("pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") or any("pytest" in arg for arg in sys.argv)) else "production"))
    IMD_CACHE_TTL_SECONDS: int = Field(default_factory=lambda: int(os.getenv("IMD_CACHE_TTL_SECONDS", "300")))
    OPEN_METEO_BASE_URL: str = Field(default_factory=lambda: os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1"))
    # OpenWeather API Key - A valid OPENWEATHER_API_KEY must be supplied by the developer via environment variable before deployment
    OPENWEATHER_API_KEY: str = Field(default_factory=lambda: os.getenv("OPENWEATHER_API_KEY", ""))
    OPENWEATHER_BASE_URL: str = Field(default_factory=lambda: os.getenv("OPENWEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5"))
    WEATHER_HTTP_TIMEOUT_SECONDS: float = Field(default_factory=lambda: float(os.getenv("WEATHER_HTTP_TIMEOUT_SECONDS", "5.0")))
    WEATHER_HTTP_MAX_RETRIES: int = Field(default_factory=lambda: int(os.getenv("WEATHER_HTTP_MAX_RETRIES", "2")))
    WEATHER_CACHE_TTL_SECONDS: int = Field(default_factory=lambda: int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "300")))
    OPENAI_API_KEY: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

settings = Settings()
