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
    """Compares primary (IMD) and secondary forecast source for agreement."""
    if secondary is None:
        return SourceAgreementEnum.SINGLE_SOURCE, "Single authoritative source (IMD) provided."

    # Compare rain probability & temperature
    rain_diff = abs(primary.rain_probability - secondary.rain_probability)
    temp_diff = abs(primary.temperature - secondary.temperature)

    if rain_diff <= 20.0 and temp_diff <= 3.0:
        return (
            SourceAgreementEnum.HIGH,
            f"High agreement across sources ({primary.source} & {secondary.source})."
        )
    elif rain_diff <= 40.0 and temp_diff <= 5.0:
        return (
            SourceAgreementEnum.MODERATE,
            f"Moderate agreement across sources ({primary.source} & {secondary.source}). Minor variance in precipitation/temperature."
        )
    else:
        return (
            SourceAgreementEnum.LOW,
            f"Disagreement between {primary.source} and {secondary.source} (rain diff: {rain_diff:.0f}%, temp diff: {temp_diff:.1f}°C). Proceed with caution."
        )


def calculate_consistency_score(
    agreement: SourceAgreementEnum,
    freshness: FreshnessStatusEnum,
    has_active_warning: bool,
    data_complete: bool = True
) -> int:
    """Calculates an application-level Forecast Consistency Score (0-100).

    IMPORTANT: This is a data confidence score, NOT a scientific probability of rain.
    """
    score = 0

    # 1. Source Agreement (Max 40)
    if agreement == SourceAgreementEnum.HIGH:
        score += 40
    elif agreement == SourceAgreementEnum.SINGLE_SOURCE:
        score += 35  # Official single source is still trustworthy
    elif agreement == SourceAgreementEnum.MODERATE:
        score += 25
    elif agreement == SourceAgreementEnum.LOW:
        score += 10

    # 2. Data Freshness (Max 30)
    if freshness == FreshnessStatusEnum.FRESH:
        score += 30
    elif freshness == FreshnessStatusEnum.ACCEPTABLE:
        score += 20
    elif freshness == FreshnessStatusEnum.STALE:
        score += 5

    # 3. Data Completeness (Max 20)
    if data_complete:
        score += 20
    else:
        score += 10

    # 4. Official Warning Clarity (Max 10)
    # Active warning reduces ambiguity because authoritative alert is declared
    score += 10

    return min(100, max(0, score))
