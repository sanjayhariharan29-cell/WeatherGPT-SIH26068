"""Configuration Management for WeatherGPT AI Intelligence.

Centralizes environment configuration, model selection, timeouts,
and meteorological thresholds per docs/05_Architectuaral.md.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """LLM generation settings."""
    provider: str = field(
        default_factory=lambda: os.getenv("WEATHERGPT_LLM_PROVIDER", "gemini")
    )
    model_name: str = field(
        default_factory=lambda: os.getenv("WEATHERGPT_LLM_MODEL", "gemini-1.5-flash")
    )
    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )
    temperature: float = 0.2
    timeout_seconds: float = 10.0
    max_output_tokens: int = 1024
    fallback_enabled: bool = True


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

    # Wind speed thresholds (km/h)
    gale_wind_threshold: float = 62.0
    strong_wind_threshold: float = 40.0

    # Temperature threshold (°C)
    heatwave_temp_threshold: float = 40.0


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
