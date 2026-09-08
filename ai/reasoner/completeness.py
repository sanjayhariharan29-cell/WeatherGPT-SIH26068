"""Data Completeness Evaluation Module for WeatherGPT Reasoner.

Inspects meteorological records to verify that essential observational
variables are present without hallucinating missing data.
"""

from typing import List, Optional, Tuple
from ai.models import WeatherRecord


def evaluate_completeness(record: Optional[WeatherRecord]) -> Tuple[bool, List[str]]:
    """Evaluates whether all critical meteorological fields are present and valid."""
    if not record:
        return False, ["all_weather_data"]

    missing: List[str] = []

    if not record.location or not record.location.name:
        missing.append("location")
    if record.temperature is None:
        missing.append("temperature")
    if record.humidity is None:
        missing.append("humidity")
    if record.rain_probability is None:
        missing.append("rain_probability")
    if record.wind_speed is None:
        missing.append("wind_speed")
    if not record.weather_condition:
        missing.append("weather_condition")
    if not record.observed_at:
        missing.append("observed_at")

    is_complete = len(missing) == 0
    return is_complete, missing
