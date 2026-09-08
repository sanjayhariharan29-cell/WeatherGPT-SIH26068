"""Hazard Detection Module for WeatherGPT.

Detects meteorological hazards based on official IMD thresholds and active warnings.
"""

from typing import List, Optional
from ai.models import (
    ForecastItem,
    HazardDetection,
    OfficialAlert,
    RiskLevelEnum,
    WeatherRecord,
)


def detect_hazards(
    current_weather: Optional[WeatherRecord],
    forecast: Optional[List[ForecastItem]] = None,
    active_alerts: Optional[List[OfficialAlert]] = None
) -> List[HazardDetection]:
    """Evaluates observations, forecasts, and alerts to identify meteorological hazards."""
    hazards: List[HazardDetection] = []
    active_alerts = active_alerts or []
    forecast = forecast or []

    # 1. Check Official Alerts First (Priority Hierarchy per docs/09_AI_Design.md)
    for alert in active_alerts:
        hazards.append(HazardDetection(
            hazard_type=f"OFFICIAL_WARNING_{alert.type.upper()}",
            detected=True,
            severity=alert.severity,
            details=f"Official IMD warning active: {alert.title}. {alert.description}"
        ))

    # Determine peak values from current weather and forecast
    peak_rain_prob = current_weather.rain_probability if current_weather else 0.0
    peak_wind_speed = current_weather.wind_speed if current_weather else 0.0
    peak_temp = current_weather.temperature if current_weather else 0.0
    has_thunderstorm = bool(current_weather and "thunder" in current_weather.weather_condition.lower())

    for f in forecast:
        if f.rain_probability > peak_rain_prob:
            peak_rain_prob = f.rain_probability
        if f.wind_speed > peak_wind_speed:
            peak_wind_speed = f.wind_speed
        if f.temperature > peak_temp:
            peak_temp = f.temperature
        if "thunder" in f.condition.lower():
            has_thunderstorm = True

    # 2. Heavy Rain Hazard (IMD standard: Heavy rain >= 64.5mm or rain prob >= 70%)
    if peak_rain_prob >= 80.0:
        hazards.append(HazardDetection(
            hazard_type="HEAVY_RAINFALL",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details=f"High probability of heavy precipitation ({peak_rain_prob:.0f}%)."
        ))
    elif peak_rain_prob >= 60.0:
        hazards.append(HazardDetection(
            hazard_type="MODERATE_RAINFALL",
            detected=True,
            severity=RiskLevelEnum.MEDIUM,
            details=f"Moderate rain probability detected ({peak_rain_prob:.0f}%)."
        ))

    # 3. Wind / Gale / Cyclonic Wind Hazard
    if peak_wind_speed >= 62.0:
        hazards.append(HazardDetection(
            hazard_type="GALE_CYCLONIC_WINDS",
            detected=True,
            severity=RiskLevelEnum.EXTREME,
            details=f"Dangerous gale wind speeds detected ({peak_wind_speed:.0f} km/h). Extreme hazard to marine and outdoor activities."
        ))
    elif peak_wind_speed >= 40.0:
        hazards.append(HazardDetection(
            hazard_type="STRONG_WINDS",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details=f"Strong wind gusts ({peak_wind_speed:.0f} km/h) can cause localized disruptions."
        ))

    # 4. Extreme Heat / Heatwave
    if peak_temp >= 40.0:
        hazards.append(HazardDetection(
            hazard_type="HEATWAVE",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details=f"Extreme temperature ({peak_temp:.1f}°C) approaching heatwave threshold."
        ))

    # 5. Thunderstorm / Lightning
    if has_thunderstorm:
        hazards.append(HazardDetection(
            hazard_type="THUNDERSTORM_LIGHTNING",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details="Thunderstorm with potential lightning strikes indicated. Seek safe indoor shelter."
        ))

    return hazards
