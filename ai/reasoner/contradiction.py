"""Contradiction Detection Module for WeatherGPT Reasoner.

Detects meteorological discrepancies across multi-source observations,
forecast timelines, and official warning conflicts per docs/09_AI_Design.md.
"""

from typing import List, Optional
from ai.models import ForecastItem, OfficialAlert, WeatherRecord


def detect_contradictions(
    primary: Optional[WeatherRecord],
    secondary: Optional[WeatherRecord] = None,
    forecast: Optional[List[ForecastItem]] = None,
    active_alerts: Optional[List[OfficialAlert]] = None
) -> List[str]:
    """Evaluates weather data for meaningful contradictions and conflicts."""
    contradictions: List[str] = []
    active_alerts = active_alerts or []
    forecast = forecast or []

    if not primary:
        return contradictions

    # 1. Multi-source Discrepancies
    if secondary:
        rain_diff = abs(primary.rain_probability - secondary.rain_probability)
        if rain_diff >= 50.0:
            contradictions.append(
                f"Severe precipitation conflict: {primary.source} reports {primary.rain_probability:.0f}% rain prob while {secondary.source} reports {secondary.rain_probability:.0f}%."
            )
        elif rain_diff >= 35.0:
            contradictions.append(
                f"Moderate precipitation divergence: {primary.source} ({primary.rain_probability:.0f}%) vs {secondary.source} ({secondary.rain_probability:.0f}%)."
            )

        temp_diff = abs(primary.temperature - secondary.temperature)
        if temp_diff >= 6.0:
            contradictions.append(
                f"Significant temperature divergence: {primary.source} reports {primary.temperature:.1f}°C vs {secondary.source} reports {secondary.temperature:.1f}°C."
            )

        wind_diff = abs(primary.wind_speed - secondary.wind_speed)
        if wind_diff >= 35.0:
            contradictions.append(
                f"Wind speed discrepancy: {primary.source} reports {primary.wind_speed:.1f} km/h vs {secondary.source} reports {secondary.wind_speed:.1f} km/h."
            )

    # 2. Condition vs Official Warning Conflict
    # When generic sky condition says "Sunny/Clear", but an official IMD warning is active
    if active_alerts:
        condition_lower = primary.weather_condition.lower()
        if any(c in condition_lower for c in ["sunny", "clear", "fair", "mostly sunny"]):
            alert_titles = ", ".join(a.title for a in active_alerts)
            contradictions.append(
                f"Authoritative Warning Override: Local condition is reported as '{primary.weather_condition}', but official IMD alert is active ({alert_titles}). Official warning takes precedence."
            )

    # 3. Forecast Internal Coherency Check
    if len(forecast) >= 2:
        for i in range(len(forecast) - 1):
            curr_f = forecast[i]
            next_f = forecast[i + 1]
            temp_jump = abs(curr_f.temperature - next_f.temperature)
            if temp_jump >= 15.0:
                contradictions.append(
                    f"Unphysical forecast swing: Temperature changes by {temp_jump:.1f}°C between {curr_f.time} and {next_f.time}."
                )

    return contradictions
