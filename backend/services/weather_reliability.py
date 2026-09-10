"""Weather Reliability, Provenance, Freshness, and Completeness Validation.

Implements deterministic evaluation of meteorological data reliability:
- Provenance preservation: source, location, timestamps, variables, units
- Freshness classification: FRESH, AGING, STALE, UNAVAILABLE
- Completeness classification: COMPLETE, PARTIAL, INVALID, UNAVAILABLE
- Provider failure diagnostics & health tracking: HEALTHY, DEGRADED, FAILED, UNAVAILABLE
- Physical meteorological plausibility checks (no impossible values)
- Cache awareness (never calls cached data 'real-time')
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


class FreshnessClassification(str, Enum):
    """Classification of meteorological observation age."""
    FRESH = "FRESH"              # Observation < 60 mins old
    AGING = "AGING"              # Observation 60 - 180 mins old (acceptable operational age)
    STALE = "STALE"              # Observation > 180 mins old
    UNAVAILABLE = "UNAVAILABLE"  # Timestamp missing, unparseable, or no telemetry


class CompletenessClassification(str, Enum):
    """Classification of observation field completeness."""
    COMPLETE = "COMPLETE"        # All core and expected observation metrics present & valid
    PARTIAL = "PARTIAL"          # Core temperature/condition present, but secondary variables missing
    INVALID = "INVALID"          # Values violate physical plausibility limits or impossible numbers
    UNAVAILABLE = "UNAVAILABLE"  # Data entirely missing or empty payload


class ProviderStatusEnum(str, Enum):
    """Provider operational status."""
    HEALTHY = "HEALTHY"          # Provider operating normally, fresh telemetry
    DEGRADED = "DEGRADED"        # Partial fields, aging telemetry, or high latency
    FAILED = "FAILED"            # Provider returned error, timed out, or unparseable
    UNAVAILABLE = "UNAVAILABLE"  # Provider not configured or unreachable


class ValidationStatusEnum(str, Enum):
    """Observation data validation status."""
    VALID = "VALID"              # Passed all physical bounds and type checks
    WARNING = "WARNING"          # Missing optional fields or borderline variance
    INVALID = "INVALID"          # Physical limit violations or corrupted types


class SystemStateEnum(str, Enum):
    """Deterministic system/data operational state of SkyZen."""
    ONLINE = "ONLINE"                          # Fresh verified live weather data is available
    DEGRADED = "DEGRADED"                      # Some providers failed or telemetry is aging, but verified data exists
    OFFLINE = "OFFLINE"                        # Network / backend connectivity is unavailable
    DATA_STALE = "DATA_STALE"                  # Cached weather exists outside fresh threshold, labeled transparently
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE" # Required providers cannot provide usable data and no usable cache exists


def determine_system_state(
    is_primary_healthy: bool,
    is_secondary_healthy: bool,
    is_cached: bool = False,
    freshness: FreshnessClassification = FreshnessClassification.FRESH,
    is_offline: bool = False
) -> SystemStateEnum:
    """Deterministically derives the SkyZen operational system state.

    Never allows the LLM or arbitrary heuristics to determine state.
    """
    if is_offline:
        return SystemStateEnum.OFFLINE

    if not is_primary_healthy and not is_secondary_healthy:
        if is_cached and freshness in (
            FreshnessClassification.FRESH,
            FreshnessClassification.AGING,
            FreshnessClassification.STALE
        ):
            return SystemStateEnum.DATA_STALE
        return SystemStateEnum.SERVICE_UNAVAILABLE

    if not is_primary_healthy or not is_secondary_healthy or freshness in (
        FreshnessClassification.AGING,
        FreshnessClassification.STALE
    ):
        return SystemStateEnum.DEGRADED

    return SystemStateEnum.ONLINE


class PhysicalBounds:
    """Earth atmosphere physical boundaries for sanity validation."""
    MIN_LATITUDE: float = -90.0
    MAX_LATITUDE: float = 90.0
    MIN_LONGITUDE: float = -180.0
    MAX_LONGITUDE: float = 180.0

    MIN_TEMPERATURE_C: float = -90.0     # World record low: -89.2°C (Vostok)
    MAX_TEMPERATURE_C: float = 60.0      # World record high: 56.7°C (Furnace Creek)

    MIN_HUMIDITY_PCT: float = 0.0
    MAX_HUMIDITY_PCT: float = 100.0

    MIN_WIND_SPEED_KMH: float = 0.0
    MAX_WIND_SPEED_KMH: float = 400.0    # Gust limit in catastrophic cyclones

    MIN_RAIN_PROB_PCT: float = 0.0
    MAX_RAIN_PROB_PCT: float = 100.0

    MIN_RAINFALL_MM: float = 0.0

    MIN_PRESSURE_HPA: float = 800.0      # Deepest cyclone eye pressure ~870 hPa
    MAX_PRESSURE_HPA: float = 1100.0     # Record high surface pressure ~1085 hPa


class WeatherReliabilityReport(BaseModel):
    """Structured meteorological reliability diagnostic report."""
    source: str
    location_name: str
    latitude: float
    longitude: float
    observed_at: str
    retrieved_at: str
    freshness: FreshnessClassification
    completeness: CompletenessClassification
    provider_status: ProviderStatusEnum
    validation_status: ValidationStatusEnum
    validation_issues: List[str] = Field(default_factory=list)
    is_cached: bool = False
    cache_age_seconds: Optional[int] = None
    observation_age_minutes: int = 0
    is_real_time: bool = True
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


def parse_iso_datetime(dt_val: Union[str, datetime, None]) -> Optional[datetime]:
    """Safely parses ISO timestamp into UTC-aware datetime."""
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(timezone.utc)

    try:
        dt_clean = dt_val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_clean)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def evaluate_weather_freshness(
    observed_at: Union[str, datetime, None],
    retrieved_at: Union[str, datetime, None] = None,
    current_time: Optional[datetime] = None,
    is_cached: bool = False,
    cache_age_seconds: Optional[int] = None
) -> Tuple[FreshnessClassification, int, Dict[str, Any]]:
    """Evaluates data freshness distinguishing observed_at from retrieved_at.
    
    Never classifies cached data as 'real-time'.
    """
    now_utc = current_time or datetime.now(timezone.utc)
    obs_dt = parse_iso_datetime(observed_at)
    ret_dt = parse_iso_datetime(retrieved_at) or now_utc

    if obs_dt is None:
        return (
            FreshnessClassification.UNAVAILABLE,
            -1,
            {
                "reason": "Missing or unparseable observed_at timestamp",
                "is_cached": is_cached,
                "cache_age_seconds": cache_age_seconds,
                "is_real_time": False
            }
        )

    delta_obs = now_utc - obs_dt
    obs_age_minutes = max(0, int(delta_obs.total_seconds() / 60))

    delta_ret = now_utc - ret_dt
    ret_age_minutes = max(0, int(delta_ret.total_seconds() / 60))

    # Classify observation age
    if obs_age_minutes < 60:
        freshness = FreshnessClassification.FRESH
    elif obs_age_minutes <= 180:
        freshness = FreshnessClassification.AGING
    else:
        freshness = FreshnessClassification.STALE

    # Rule: Never label old or cached data as real-time
    is_real_time = (freshness == FreshnessClassification.FRESH and not is_cached and obs_age_minutes < 15)

    meta = {
        "observation_age_minutes": obs_age_minutes,
        "retrieval_age_minutes": ret_age_minutes,
        "is_cached": is_cached,
        "cache_age_seconds": cache_age_seconds,
        "is_real_time": is_real_time
    }

    return freshness, obs_age_minutes, meta


def validate_weather_completeness(
    obs: Dict[str, Any]
) -> Tuple[CompletenessClassification, ValidationStatusEnum, List[str]]:
    """Validates required fields and physical boundaries for a weather observation dictionary.
    
    Detects:
    - missing mandatory identity/timestamps
    - missing core meteorological metrics
    - impossible physical values
    - distinguishes COMPLETE vs PARTIAL vs INVALID vs UNAVAILABLE
    """
    issues: List[str] = []

    if not obs:
        return CompletenessClassification.UNAVAILABLE, ValidationStatusEnum.INVALID, ["Empty observation payload"]

    # 1. Geographic & Provenance Identity
    loc_name = obs.get("location_name")
    if not loc_name or not str(loc_name).strip():
        issues.append("Missing location_name")

    source = obs.get("source")
    if not source or not str(source).strip():
        issues.append("Missing source identity")

    lat = obs.get("latitude")
    lon = obs.get("longitude")

    if lat is None:
        issues.append("Missing latitude")
    elif not isinstance(lat, (int, float)) or lat < PhysicalBounds.MIN_LATITUDE or lat > PhysicalBounds.MAX_LATITUDE:
        issues.append(f"Invalid latitude {lat}: must be between -90 and +90 degrees")

    if lon is None:
        issues.append("Missing longitude")
    elif not isinstance(lon, (int, float)) or lon < PhysicalBounds.MIN_LONGITUDE or lon > PhysicalBounds.MAX_LONGITUDE:
        issues.append(f"Invalid longitude {lon}: must be between -180 and +180 degrees")

    # 2. Timestamps
    obs_at = obs.get("observed_at")
    if not obs_at or parse_iso_datetime(obs_at) is None:
        issues.append("Missing or unparseable observed_at timestamp")

    ret_at = obs.get("retrieved_at")
    if not ret_at or parse_iso_datetime(ret_at) is None:
        issues.append("Missing or unparseable retrieved_at timestamp")

    # 3. Core Meteorological Metrics
    has_temp = ("temperature_c" in obs and obs["temperature_c"] is not None) or ("temperature" in obs and obs["temperature"] is not None)
    has_hum = ("humidity_pct" in obs and obs["humidity_pct"] is not None) or ("humidity" in obs and obs["humidity"] is not None)
    has_wind = ("wind_speed_kmh" in obs and obs["wind_speed_kmh"] is not None) or ("wind_speed" in obs and obs["wind_speed"] is not None)
    has_rain_prob = ("rain_probability_pct" in obs and obs["rain_probability_pct"] is not None) or ("rain_probability" in obs and obs["rain_probability"] is not None)

    temp_val = obs.get("temperature_c") if obs.get("temperature_c") is not None else obs.get("temperature")
    hum_val = obs.get("humidity_pct") if obs.get("humidity_pct") is not None else obs.get("humidity")
    wind_val = obs.get("wind_speed_kmh") if obs.get("wind_speed_kmh") is not None else obs.get("wind_speed")
    rain_prob_val = obs.get("rain_probability_pct") if obs.get("rain_probability_pct") is not None else obs.get("rain_probability")
    rainfall_val = obs.get("rainfall_mm") if obs.get("rainfall_mm") is not None else obs.get("rainfall", 0.0)
    pressure_val = obs.get("pressure_hpa") if obs.get("pressure_hpa") is not None else obs.get("pressure")

    # 4. Physical Boundary Checks (Detect impossible numbers)
    is_physically_invalid = False

    if has_temp:
        try:
            temp_num = float(temp_val)
            if temp_num < PhysicalBounds.MIN_TEMPERATURE_C or temp_num > PhysicalBounds.MAX_TEMPERATURE_C:
                issues.append(f"Temperature {temp_num}°C exceeds physical boundaries ({PhysicalBounds.MIN_TEMPERATURE_C} to {PhysicalBounds.MAX_TEMPERATURE_C}°C)")
                is_physically_invalid = True
        except (ValueError, TypeError):
            issues.append(f"Malformed temperature value: {temp_val}")
            is_physically_invalid = True
    else:
        issues.append("Missing core field: temperature")

    if has_hum:
        try:
            hum_num = float(hum_val)
            if hum_num < PhysicalBounds.MIN_HUMIDITY_PCT or hum_num > PhysicalBounds.MAX_HUMIDITY_PCT:
                issues.append(f"Humidity {hum_num}% exceeds physical boundaries (0-100%)")
                is_physically_invalid = True
        except (ValueError, TypeError):
            issues.append(f"Malformed humidity value: {hum_val}")
            is_physically_invalid = True
    else:
        issues.append("Missing core field: humidity")

    if has_wind:
        try:
            wind_num = float(wind_val)
            if wind_num < PhysicalBounds.MIN_WIND_SPEED_KMH or wind_num > PhysicalBounds.MAX_WIND_SPEED_KMH:
                issues.append(f"Wind speed {wind_num} km/h exceeds physical boundaries (0-400 km/h)")
                is_physically_invalid = True
        except (ValueError, TypeError):
            issues.append(f"Malformed wind speed value: {wind_val}")
            is_physically_invalid = True
    else:
        issues.append("Missing core field: wind_speed")

    if has_rain_prob:
        try:
            prob_num = float(rain_prob_val)
            if prob_num < PhysicalBounds.MIN_RAIN_PROB_PCT or prob_num > PhysicalBounds.MAX_RAIN_PROB_PCT:
                issues.append(f"Rain probability {prob_num}% exceeds physical boundaries (0-100%)")
                is_physically_invalid = True
        except (ValueError, TypeError):
            issues.append(f"Malformed rain probability value: {rain_prob_val}")
            is_physically_invalid = True
    else:
        issues.append("Missing core field: rain_probability")

    if rainfall_val is not None:
        try:
            rf_num = float(rainfall_val)
            if rf_num < PhysicalBounds.MIN_RAINFALL_MM:
                issues.append(f"Rainfall amount cannot be negative: {rf_num} mm")
                is_physically_invalid = True
        except (ValueError, TypeError):
            issues.append(f"Malformed rainfall amount: {rainfall_val}")
            is_physically_invalid = True

    if pressure_val is not None:
        try:
            pres_num = float(pressure_val)
            if pres_num < PhysicalBounds.MIN_PRESSURE_HPA or pres_num > PhysicalBounds.MAX_PRESSURE_HPA:
                issues.append(f"Atmospheric pressure {pres_num} hPa exceeds surface atmospheric limits (800-1100 hPa)")
                is_physically_invalid = True
        except (ValueError, TypeError):
            issues.append(f"Malformed pressure value: {pressure_val}")
            is_physically_invalid = True

    # 5. Classify Completeness & Validation Status
    if is_physically_invalid:
        return CompletenessClassification.INVALID, ValidationStatusEnum.INVALID, issues

    if not has_temp and not has_hum and not has_wind:
        return CompletenessClassification.UNAVAILABLE, ValidationStatusEnum.INVALID, issues

    # If temperature is present but secondary metrics are missing, classify as PARTIAL
    missing_core = not (has_temp and has_hum and has_wind and has_rain_prob)
    missing_identity = (lat is None or lon is None or not loc_name or not source or not obs_at)

    if missing_core or missing_identity:
        return CompletenessClassification.PARTIAL, ValidationStatusEnum.WARNING, issues

    return CompletenessClassification.COMPLETE, ValidationStatusEnum.VALID, []
