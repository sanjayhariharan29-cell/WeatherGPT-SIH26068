"""Weather Reasoner Orchestration Engine.

Analyzes raw weather data, computes freshness, evaluates data completeness,
evaluates source agreement, detects contradictions and hazards,
and produces a structured WeatherReasoningResult.
"""

from datetime import datetime, timezone
from typing import List, Optional
from ai.models import (
    ForecastItem,
    FreshnessStatusEnum,
    HazardDetection,
    OfficialAlert,
    RiskLevelEnum,
    SourceAgreementEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.reasoner.agreement import (
    calculate_consistency_score,
    evaluate_source_agreement,
)
from ai.reasoner.completeness import evaluate_completeness
from ai.reasoner.contradiction import detect_contradictions
from ai.reasoner.freshness import check_data_freshness
from ai.reasoner.hazard import detect_hazards


class WeatherReasoner:
    """Core Intelligence Reasoner for WeatherGPT."""

    @staticmethod
    def evaluate(
        primary_weather: Optional[WeatherRecord],
        secondary_weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        active_alerts: Optional[List[OfficialAlert]] = None,
        current_time: Optional[datetime] = None
    ) -> WeatherReasoningResult:
        """Runs the complete meteorological reasoning pipeline with safety & completeness checks."""
        now = current_time or datetime.now(timezone.utc)
        active_alerts = active_alerts or []
        forecast = forecast or []

        # 1. Handle Case Where Weather Data is Missing / Null
        if not primary_weather:
            return WeatherReasoningResult(
                evaluated_at=now,
                location="Unknown",
                freshness=FreshnessStatusEnum.STALE,
                data_age_minutes=999,
                data_complete=False,
                missing_fields=["primary_weather_record"],
                source_agreement=SourceAgreementEnum.SINGLE_SOURCE,
                consistency_score=0,
                contradictions=[],
                active_warnings=active_alerts,
                detected_hazards=[],
                ai_detected_hazards=[],
                overall_risk=RiskLevelEnum.LOW if not active_alerts else active_alerts[0].severity,
                uncertainty_note="Primary weather observation data is unavailable.",
                sources_used=[]
            )

        # 2. Freshness Check
        freshness_status, age_mins = check_data_freshness(
            primary_weather.retrieved_at,
            current_time=now
        )

        # 3. Completeness Check
        is_complete, missing_fields = evaluate_completeness(primary_weather)

        # 4. Source Agreement
        agreement, agreement_note = evaluate_source_agreement(
            primary_weather,
            secondary_weather
        )

        # 5. Contradiction Detection
        contradictions = detect_contradictions(
            primary=primary_weather,
            secondary=secondary_weather,
            forecast=forecast,
            active_alerts=active_alerts
        )

        # 6. Hazard Detection
        all_hazards = detect_hazards(
            current_weather=primary_weather,
            forecast=forecast,
            active_alerts=active_alerts
        )

        # Separate AI-detected hazards from official authoritative warnings
        ai_detected_hazards = [
            h for h in all_hazards if not h.hazard_type.startswith("OFFICIAL_WARNING_")
        ]

        # 7. Determine Overall Risk Level
        # Official warnings take unconditional priority in determining risk severity
        overall_risk = RiskLevelEnum.LOW
        for alert in active_alerts:
            if alert.severity == RiskLevelEnum.EXTREME:
                overall_risk = RiskLevelEnum.EXTREME
                break
            elif alert.severity == RiskLevelEnum.HIGH and overall_risk != RiskLevelEnum.EXTREME:
                overall_risk = RiskLevelEnum.HIGH
            elif alert.severity == RiskLevelEnum.MEDIUM and overall_risk == RiskLevelEnum.LOW:
                overall_risk = RiskLevelEnum.MEDIUM

        # If no official warning, derive from AI-detected hazards
        if not active_alerts:
            for h in ai_detected_hazards:
                if h.severity == RiskLevelEnum.EXTREME:
                    overall_risk = RiskLevelEnum.EXTREME
                    break
                elif h.severity == RiskLevelEnum.HIGH and overall_risk != RiskLevelEnum.EXTREME:
                    overall_risk = RiskLevelEnum.HIGH
                elif h.severity == RiskLevelEnum.MEDIUM and overall_risk == RiskLevelEnum.LOW:
                    overall_risk = RiskLevelEnum.MEDIUM

        # 8. Forecast Consistency Score Calculation
        consistency_score = calculate_consistency_score(
            agreement=agreement,
            freshness=freshness_status,
            has_active_warning=bool(active_alerts),
            data_complete=is_complete,
            contradiction_count=len(contradictions)
        )

        # 9. Uncertainty Formulation
        uncertainty_elements = []
        if agreement == SourceAgreementEnum.LOW:
            uncertainty_elements.append(f"Forecast sources show divergence: {agreement_note}")
        if freshness_status == FreshnessStatusEnum.STALE:
            uncertainty_elements.append(f"Observation data is {age_mins} minutes old.")
        if contradictions:
            uncertainty_elements.extend(contradictions)

        uncertainty_note = " | ".join(uncertainty_elements) if uncertainty_elements else None

        sources_used = [primary_weather.source]
        if secondary_weather and secondary_weather.source not in sources_used:
            sources_used.append(secondary_weather.source)

        return WeatherReasoningResult(
            evaluated_at=now,
            location=primary_weather.location.name,
            freshness=freshness_status,
            data_age_minutes=age_mins,
            data_complete=is_complete,
            missing_fields=missing_fields,
            source_agreement=agreement,
            consistency_score=consistency_score,
            contradictions=contradictions,
            active_warnings=active_alerts,
            detected_hazards=all_hazards,
            ai_detected_hazards=ai_detected_hazards,
            overall_risk=overall_risk,
            uncertainty_note=uncertainty_note,
            sources_used=sources_used
        )
