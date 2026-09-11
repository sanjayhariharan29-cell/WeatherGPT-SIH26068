"""Configuration Management for WeatherGPT AI Intelligence.

Centralizes environment configuration, model selection, timeouts,
and meteorological thresholds per docs/05_Architectuaral.md.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class LLMConfig:
    """LLM generation settings with strict secret protection."""
    provider: str = field(
        default_factory=lambda: os.getenv("WEATHERGPT_LLM_PROVIDER", "gemini")
    )
    model_name: str = field(
        default_factory=lambda: os.getenv("WEATHERGPT_LLM_MODEL", "gemini-1.5-flash")
    )
    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )
    groq_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY")
    )
    groq_model: str = field(
        default_factory=lambda: os.getenv("WEATHERGPT_GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    fallback_provider: Optional[str] = field(
        default_factory=lambda: os.getenv("WEATHERGPT_FALLBACK_PROVIDER")
    )
    temperature: float = 0.2
    timeout_seconds: float = 10.0
    max_output_tokens: int = 1024
    fallback_enabled: bool = True

    def __repr__(self) -> str:
        """Masks sensitive credentials from logs, stack traces, and debug string representations."""
        masked_gemini = "***REDACTED***" if self.api_key else None
        masked_groq = "***REDACTED***" if self.groq_api_key else None
        return (
            f"LLMConfig(provider={self.provider!r}, model_name={self.model_name!r}, "
            f"api_key={masked_gemini!r}, groq_api_key={masked_groq!r}, "
            f"groq_model={self.groq_model!r}, fallback_provider={self.fallback_provider!r}, "
            f"temperature={self.temperature}, timeout_seconds={self.timeout_seconds}, "
            f"fallback_enabled={self.fallback_enabled})"
        )


@dataclass
class MeteorologicalThresholds:
    """Official IMD and domain thresholds for hazard detection and freshness."""
    # Freshness thresholds in minutes
    fresh_limit_mins: int = 60
    acceptable_limit_mins: int = 180

    # Precipitation thresholds
    heavy_rain_prob_threshold: float = 80.0
    moderate_rain_prob_threshold: float = 60.0
    heavy_rain_mm_threshold: float = 64.5
    extreme_rain_mm_threshold: float = 204.5
    very_heavy_rain_mm_threshold: float = 115.6
    moderate_rain_mm_threshold: float = 15.6

    # Wind speed thresholds (km/h)
    gale_wind_threshold: float = 62.0
    strong_wind_threshold: float = 40.0
    severe_gale_wind_threshold: float = 88.0

    # Temperature threshold (°C)
    heatwave_temp_threshold: float = 40.0
    severe_heatwave_temp_threshold: float = 45.0
    coldwave_temp_threshold: float = 10.0
    severe_coldwave_temp_threshold: float = 4.0

    # Visibility thresholds (meters)
    low_visibility_meters_threshold: float = 1000.0
    dense_fog_visibility_meters_threshold: float = 200.0


@dataclass
class AIConfig:
    """Unified master configuration for the WeatherGPT AI layer."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    thresholds: MeteorologicalThresholds = field(default_factory=MeteorologicalThresholds)
    default_language: str = "en"
    validation_strict_mode: bool = True


# Global default configuration instance
default_config = AIConfig()


def get_ai_config() -> AIConfig:
    """Returns the active AI layer configuration."""
    return default_config
