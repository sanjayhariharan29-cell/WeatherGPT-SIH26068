"""Weather Reasoner Orchestration Engine.

Analyzes raw weather data, computes freshness, evaluates source agreement,
detects hazards, and produces a structured WeatherReasoningResult.
"""

from datetime import datetime, timezone
from typing import List, Optional
from ai.models import (
    ForecastItem,
    OfficialAlert,
    RiskLevelEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.reasoner.agreement import (
    calculate_consistency_score,
    evaluate_source_agreement,
)
from ai.reasoner.freshness import check_data_freshness
from ai.reasoner.hazard import detect_hazards


class WeatherReasoner:
    """Core Intelligence Reasoner for WeatherGPT."""

    @staticmethod
    def evaluate(
        primary_weather: WeatherRecord,
        secondary_weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        active_alerts: Optional[List[OfficialAlert]] = None,
        current_time: Optional[datetime] = None
    ) -> WeatherReasoningResult:
        """Runs the complete meteorological reasoning pipeline."""
        now = current_time or datetime.now(timezone.utc)
        active_alerts = active_alerts or []
        forecast = forecast or []

        # 1. Freshness Check
        freshness_status, age_mins = check_data_freshness(
            primary_weather.retrieved_at,
            current_time=now
        )

        # 2. Source Agreement
        agreement, agreement_note = evaluate_source_agreement(
            primary_weather,
            secondary_weather
        )

        # 3. Hazard Detection
        hazards = detect_hazards(
            current_weather=primary_weather,
            forecast=forecast,
            active_alerts=active_alerts
        )

        # 4. Determine Overall Risk Level
        overall_risk = RiskLevelEnum.LOW
        for h in hazards:
            if h.severity == RiskLevelEnum.EXTREME:
                overall_risk = RiskLevelEnum.EXTREME
                break
            elif h.severity == RiskLevelEnum.HIGH and overall_risk != RiskLevelEnum.EXTREME:
                overall_risk = RiskLevelEnum.HIGH
            elif h.severity == RiskLevelEnum.MEDIUM and overall_risk == RiskLevelEnum.LOW:
                overall_risk = RiskLevelEnum.MEDIUM

        # 5. Consistency Score
        consistency_score = calculate_consistency_score(
            agreement=agreement,
            freshness=freshness_status,
            has_active_warning=bool(active_alerts),
            data_complete=True
        )

        uncertainty_note = None
        if agreement.value == "low":
            uncertainty_note = f"Warning: Forecast sources show divergence. {agreement_note}"
        elif freshness_status.value == "stale":
            uncertainty_note = f"Data is {age_mins} minutes old. Exercise caution with fast-changing weather."

        sources_used = [primary_weather.source]
        if secondary_weather and secondary_weather.source not in sources_used:
            sources_used.append(secondary_weather.source)

        return WeatherReasoningResult(
            evaluated_at=now,
            location=primary_weather.location.name,
            freshness=freshness_status,
            data_age_minutes=age_mins,
            source_agreement=agreement,
            consistency_score=consistency_score,
            active_warnings=active_alerts,
            detected_hazards=hazards,
            overall_risk=overall_risk,
            uncertainty_note=uncertainty_note,
            sources_used=sources_used
        )
