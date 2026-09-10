"""Multi-Source Forecast Consistency and Agreement Analyzer.

Implements the Forecast Consistency / Data Confidence Indicator
per docs/03_Gap_And_USP.md, docs/09_AI_Design.md, and SkyZen Phase 9 specifications.
Evaluates:
- rainfall agreement
- temperature agreement
- wind agreement
- timing agreement
- source freshness
- completeness
- contradiction
"""

from typing import List, Optional, Tuple, Dict, Any
from ai.models import (
    ConfidenceLevelEnum,
    ForecastConsistencyFactors,
    ForecastItem,
    FreshnessStatusEnum,
    OfficialAlert,
    SourceAgreementEnum,
    WeatherRecord,
)


def evaluate_source_agreement(
    primary: WeatherRecord,
    secondary: Optional[WeatherRecord] = None,
    primary_forecast: Optional[List[ForecastItem]] = None,
    secondary_forecast: Optional[List[ForecastItem]] = None,
) -> Tuple[SourceAgreementEnum, str]:
    """Compares primary (IMD) and secondary forecast source for agreement across variables."""
    if secondary is None:
        return SourceAgreementEnum.SINGLE_SOURCE, "Single authoritative source (IMD) provided."

    # 1. Compare rain probability, temperature, and wind speed
    rain_diff = abs(primary.rain_probability - secondary.rain_probability)
    temp_diff = abs(primary.temperature - secondary.temperature)
    wind_diff = abs(primary.wind_speed - secondary.wind_speed)

    # 2. Check timing agreement across forecasts if both are provided
    timing_disagreement = False
    if primary_forecast and secondary_forecast:
        min_len = min(len(primary_forecast), len(secondary_forecast), 6)
        for i in range(min_len):
            pf = primary_forecast[i]
            sf = secondary_forecast[i]
            f_rain_diff = abs(pf.rain_probability - sf.rain_probability)
            if f_rain_diff >= 45.0:
                timing_disagreement = True
                break

    if rain_diff <= 20.0 and temp_diff <= 3.0 and wind_diff <= 15.0 and not timing_disagreement:
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
        divergence_details = []
        if rain_diff > 20.0:
            divergence_details.append(f"rain diff: {rain_diff:.0f}%")
        if temp_diff > 3.0:
            divergence_details.append(f"temp diff: {temp_diff:.1f}°C")
        if wind_diff > 15.0:
            divergence_details.append(f"wind diff: {wind_diff:.1f} km/h")
        if timing_disagreement:
            divergence_details.append("timeline divergence in precipitation timing")

        details_str = ", ".join(divergence_details) if divergence_details else "metric variance"
        return (
            SourceAgreementEnum.LOW,
            f"Disagreement between {primary.source} and {secondary.source} ({details_str}). Proceed with caution."
        )


def calculate_consistency_score(
    agreement: SourceAgreementEnum,
    freshness: FreshnessStatusEnum,
    has_active_warning: bool,
    data_complete: bool = True,
    contradiction_count: int = 0,
    timing_disagreement: bool = False
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
    elif agreement in (SourceAgreementEnum.MODERATE, SourceAgreementEnum.MEDIUM):
        score += 20
    elif agreement == SourceAgreementEnum.LOW:
        score += 0

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

    # 5. Timing Disagreement Penalty (Phase 9)
    if timing_disagreement:
        score -= 10

    # 6. Contradiction Penalty
    if contradiction_count > 0:
        penalty = min(30, contradiction_count * 10)
        score -= penalty

    return min(100, max(0, score))


def determine_confidence_level(
    score: int,
    agreement: SourceAgreementEnum,
    freshness: FreshnessStatusEnum,
    data_complete: bool = True,
    contradiction_count: int = 0
) -> ConfidenceLevelEnum:
    """Derives HIGH, MEDIUM, or LOW application-level Data Confidence Indicator (Phase 9).

    Levels:
    - HIGH: Sources broadly agree, data is fresh and complete (Score >= 75)
    - MEDIUM: Some disagreement or acceptable age (Score 45-74)
    - LOW: Significant disagreement (e.g. rain 80% vs 20%), stale data, incomplete data, or heavy contradiction (Score < 45)
    """
    if not data_complete or freshness == FreshnessStatusEnum.STALE or agreement == SourceAgreementEnum.LOW or contradiction_count >= 2 or score < 45:
        return ConfidenceLevelEnum.LOW
    elif (agreement == SourceAgreementEnum.HIGH or agreement == SourceAgreementEnum.SINGLE_SOURCE) and freshness == FreshnessStatusEnum.FRESH and score >= 75 and contradiction_count == 0:
        return ConfidenceLevelEnum.HIGH
    else:
        return ConfidenceLevelEnum.MEDIUM


def build_consistency_factors(
    primary: WeatherRecord,
    secondary: Optional[WeatherRecord] = None,
    primary_forecast: Optional[List[ForecastItem]] = None,
    secondary_forecast: Optional[List[ForecastItem]] = None,
    freshness: FreshnessStatusEnum = FreshnessStatusEnum.FRESH,
    data_complete: bool = True,
    contradictions: Optional[List[str]] = None,
    agreement: SourceAgreementEnum = SourceAgreementEnum.HIGH,
    confidence_level: ConfidenceLevelEnum = ConfidenceLevelEnum.HIGH,
) -> ForecastConsistencyFactors:
    """Constructs a deterministic, structured breakdown of the 7 Phase 9 consistency factors."""
    contradictions = contradictions or []

    # Rainfall agreement
    if secondary is not None:
        rain_diff = abs(primary.rain_probability - secondary.rain_probability)
        if rain_diff <= 20.0:
            rain_status = f"High agreement ({primary.source} {primary.rain_probability:.0f}% vs {secondary.source} {secondary.rain_probability:.0f}%, Δ {rain_diff:.0f}%)"
        elif rain_diff <= 40.0:
            rain_status = f"Moderate variance ({primary.source} {primary.rain_probability:.0f}% vs {secondary.source} {secondary.rain_probability:.0f}%, Δ {rain_diff:.0f}%)"
        else:
            rain_status = f"Significant disagreement ({primary.source} {primary.rain_probability:.0f}% vs {secondary.source} {secondary.rain_probability:.0f}%, Δ {rain_diff:.0f}%)"
    else:
        rain_status = f"Single source ({primary.source}): {primary.rain_probability:.0f}% precipitation probability."

    # Temperature agreement
    if secondary is not None:
        temp_diff = abs(primary.temperature - secondary.temperature)
        if temp_diff <= 3.0:
            temp_status = f"Broad agreement ({primary.source} {primary.temperature:.1f}°C vs {secondary.source} {secondary.temperature:.1f}°C, Δ {temp_diff:.1f}°C)"
        else:
            temp_status = f"Variance observed ({primary.source} {primary.temperature:.1f}°C vs {secondary.source} {secondary.temperature:.1f}°C, Δ {temp_diff:.1f}°C)"
    else:
        temp_status = f"Single source ({primary.source}): {primary.temperature:.1f}°C."

    # Wind agreement
    if secondary is not None:
        wind_diff = abs(primary.wind_speed - secondary.wind_speed)
        if wind_diff <= 15.0:
            wind_status = f"Broad agreement ({primary.source} {primary.wind_speed:.1f} km/h vs {secondary.source} {secondary.wind_speed:.1f} km/h)"
        else:
            wind_status = f"Divergence detected ({primary.source} {primary.wind_speed:.1f} km/h vs {secondary.source} {secondary.wind_speed:.1f} km/h)"
    else:
        wind_status = f"Single source ({primary.source}): {primary.wind_speed:.1f} km/h."

    # Timing agreement
    if primary_forecast and secondary_forecast:
        timing_status = "Forecast timeline and precipitation window compared across sources."
    elif primary_forecast:
        timing_status = f"Forecast timeline verified across {len(primary_forecast)} future steps."
    else:
        timing_status = "Hourly forecast timeline not provided."

    # Freshness
    freshness_status = f"Telemetry is {freshness.value.upper()}."

    # Completeness
    completeness_status = "Complete: All primary meteorological parameters populated." if data_complete else "Incomplete: Missing observation parameters."

    # Summary explanation
    if confidence_level == ConfidenceLevelEnum.LOW:
        if secondary and abs(primary.rain_probability - secondary.rain_probability) >= 40.0:
            summary = (
                f"Forecast consistency is low because available sources disagree "
                f"({primary.source} predicts {primary.rain_probability:.0f}% rain while "
                f"{secondary.source} predicts {secondary.rain_probability:.0f}% rain)."
            )
        elif not data_complete:
            summary = "Forecast consistency is low due to incomplete observation telemetry."
        elif freshness == FreshnessStatusEnum.STALE:
            summary = "Forecast consistency is low due to stale observation telemetry."
        else:
            summary = "Forecast consistency is low because available sources show significant divergence."
    elif confidence_level == ConfidenceLevelEnum.MEDIUM:
        summary = "Forecast consistency is medium with some disagreement or minor variance between available sources."
    else:
        summary = "Forecast consistency is high as available forecast sources broadly agree across rainfall, temperature, and wind."

    return ForecastConsistencyFactors(
        rainfall_agreement=rain_status,
        temperature_agreement=temp_status,
        wind_agreement=wind_status,
        timing_agreement=timing_status,
        source_freshness=freshness_status,
        completeness=completeness_status,
        contradictions=contradictions,
        summary=summary,
    )
