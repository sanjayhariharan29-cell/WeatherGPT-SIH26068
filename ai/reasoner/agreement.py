"""Multi-Source Forecast Consistency and Agreement Analyzer.

Implements the Forecast Consistency / Data Confidence Indicator
per docs/03_Gap_And_USP.md and docs/09_AI_Design.md.
"""

from typing import List, Optional, Tuple
from ai.models import (
    FreshnessStatusEnum,
    OfficialAlert,
    SourceAgreementEnum,
    WeatherRecord,
)


def evaluate_source_agreement(
    primary: WeatherRecord,
    secondary: Optional[WeatherRecord] = None
) -> Tuple[SourceAgreementEnum, str]:
    """Compares primary (IMD) and secondary forecast source for agreement across variables."""
    if secondary is None:
        return SourceAgreementEnum.SINGLE_SOURCE, "Single authoritative source (IMD) provided."

    # Compare rain probability, temperature, and wind speed
    rain_diff = abs(primary.rain_probability - secondary.rain_probability)
    temp_diff = abs(primary.temperature - secondary.temperature)
    wind_diff = abs(primary.wind_speed - secondary.wind_speed)

    if rain_diff <= 20.0 and temp_diff <= 3.0 and wind_diff <= 15.0:
        return (
            SourceAgreementEnum.HIGH,
            f"High agreement across sources ({primary.source} & {secondary.source})."
        )
    elif rain_diff <= 40.0 and temp_diff <= 5.0 and wind_diff <= 30.0:
        return (
            SourceAgreementEnum.MODERATE,
            f"Moderate agreement across sources ({primary.source} & {secondary.source}). Minor variance in metrics."
        )
    else:
        return (
            SourceAgreementEnum.LOW,
            f"Disagreement between {primary.source} and {secondary.source} (rain diff: {rain_diff:.0f}%, temp diff: {temp_diff:.1f}°C, wind diff: {wind_diff:.1f} km/h). Proceed with caution."
        )


def calculate_consistency_score(
    agreement: SourceAgreementEnum,
    freshness: FreshnessStatusEnum,
    has_active_warning: bool,
    data_complete: bool = True,
    contradiction_count: int = 0
) -> int:
    """Calculates an application-level Forecast Consistency Score (0-100).

    IMPORTANT: This represents data consistency and reliability, NOT scientific probability of rain.
    """
    score = 0

    # 1. Source Agreement (Max 35)
    if agreement == SourceAgreementEnum.HIGH:
        score += 35
    elif agreement == SourceAgreementEnum.SINGLE_SOURCE:
        score += 30  # Single authoritative IMD source is reliable
    elif agreement == SourceAgreementEnum.MODERATE:
        score += 20
    elif agreement == SourceAgreementEnum.LOW:
        score += 5

    # 2. Data Freshness (Max 25)
    if freshness == FreshnessStatusEnum.FRESH:
        score += 25
    elif freshness == FreshnessStatusEnum.ACCEPTABLE:
        score += 18
    elif freshness == FreshnessStatusEnum.STALE:
        score += 5

    # 3. Data Completeness (Max 25)
    if data_complete:
        score += 25
    else:
        score += 10

    # 4. Authoritative Warning Clarity (Max 15)
    # Active IMD warning removes ambiguity by clearly declaring hazards
    if has_active_warning:
        score += 15
    else:
        score += 10

    # 5. Contradiction Penalty
    if contradiction_count > 0:
        penalty = min(25, contradiction_count * 10)
        score -= penalty

    return min(100, max(0, score))
