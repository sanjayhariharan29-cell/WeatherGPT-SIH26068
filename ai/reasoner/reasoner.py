"""Weather Reasoner Orchestration Engine.

Analyzes raw weather data, computes freshness, evaluates data completeness,
evaluates source agreement, detects contradictions and hazards,
and produces a structured WeatherReasoningResult.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from ai.models import (
    ConfidenceLevelEnum,
    ForecastConsistencyFactors,
    ForecastItem,
    FreshnessStatusEnum,
    HazardDetection,
    OfficialAlert,
    RiskLevelEnum,
    SourceAgreementEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from backend.services.nwp_schemas import NormalizedNWPForecastItem, NWPModelComparison
from ai.reasoner.agreement import (
    build_consistency_factors,
    calculate_consistency_score,
    determine_confidence_level,
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
        current_time: Optional[datetime] = None,
        secondary_forecast: Optional[List[ForecastItem]] = None,
        nwp_guidance: Optional[List[Any]] = None,
        nwp_comparison: Optional[Any] = None
    ) -> WeatherReasoningResult:
        """Runs the complete meteorological reasoning pipeline with safety & completeness checks."""
        now = current_time or datetime.now(timezone.utc)
        warnings_unavail = (active_alerts is None)
        alerts_list = active_alerts or []
        forecast = forecast or []

        # Filter active alerts: expired warnings must NEVER be treated as currently active (Phase 14 Step 13)
        valid_active_alerts: List[OfficialAlert] = []
        for alert in alerts_list:
            exp = alert.expires_at
            ref = now
            if exp:
                if exp.tzinfo is not None and ref.tzinfo is None:
                    ref = ref.replace(tzinfo=timezone.utc)
                elif exp.tzinfo is None and ref.tzinfo is not None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp > ref:
                    valid_active_alerts.append(alert)
            else:
                valid_active_alerts.append(alert)

        # 1. Handle Case Where Weather Data is Missing / Null / Degraded
        if not primary_weather or getattr(primary_weather, "source", "") in ("DATA_UNAVAILABLE", "UNAVAILABLE"):
            all_hazards = detect_hazards(
                current_weather=None,
                forecast=forecast,
                active_alerts=valid_active_alerts
            )
            ai_detected_hazards = [
                h for h in all_hazards if not h.is_official_warning and not h.hazard_type.startswith("OFFICIAL_WARNING_")
            ]
            loc_name = "Unknown"
            if primary_weather and getattr(primary_weather, "location", None) and getattr(primary_weather.location, "name", None):
                loc_name = primary_weather.location.name
            elif valid_active_alerts and valid_active_alerts[0].affected_locations:
                loc_name = valid_active_alerts[0].affected_locations[0]

            overall_risk = RiskLevelEnum.LOW
            for alert in valid_active_alerts:
                if alert.severity == RiskLevelEnum.EXTREME:
                    overall_risk = RiskLevelEnum.EXTREME
                    break
                elif alert.severity == RiskLevelEnum.HIGH and overall_risk != RiskLevelEnum.EXTREME:
                    overall_risk = RiskLevelEnum.HIGH
                elif alert.severity == RiskLevelEnum.MEDIUM and overall_risk == RiskLevelEnum.LOW:
                    overall_risk = RiskLevelEnum.MEDIUM

            sources_used = [valid_active_alerts[0].source] if valid_active_alerts else []
            uncert = "Primary weather observation data is unavailable."
            if warnings_unavail:
                uncert += " Official warning information is currently unavailable."

            return WeatherReasoningResult(
                evaluated_at=now,
                location=loc_name,
                freshness=FreshnessStatusEnum.STALE,
                data_age_minutes=999,
                data_complete=False,
                missing_fields=["primary_weather_record"],
                source_agreement=SourceAgreementEnum.SINGLE_SOURCE,
                consistency_score=0,
                confidence_level=ConfidenceLevelEnum.LOW,
                confidence_indicator="Low",
                consistency_factors={
                    "rainfall_agreement": "Primary weather observation data is unavailable.",
                    "temperature_agreement": "Primary weather observation data is unavailable.",
                    "wind_agreement": "Primary weather observation data is unavailable.",
                    "timing_agreement": "No timeline data.",
                    "source_freshness": "STALE",
                    "completeness": "Incomplete: primary_weather_record missing.",
                    "contradictions": [],
                    "summary": "Forecast consistency is low due to missing observation telemetry.",
                },
                contradictions=[],
                active_warnings=valid_active_alerts,
                detected_hazards=all_hazards,
                ai_detected_hazards=ai_detected_hazards,
                overall_risk=overall_risk,
                uncertainty_note=uncert,
                sources_used=sources_used,
                warnings_available=not warnings_unavail
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
            primary=primary_weather,
            secondary=secondary_weather,
            primary_forecast=forecast,
            secondary_forecast=secondary_forecast
        )

        # 5. Contradiction Detection
        contradictions = detect_contradictions(
            primary=primary_weather,
            secondary=secondary_weather,
            forecast=forecast,
            active_alerts=valid_active_alerts
        )

        # 6. Hazard Detection
        all_hazards = detect_hazards(
            current_weather=primary_weather,
            forecast=forecast,
            active_alerts=valid_active_alerts
        )

        # Separate AI-detected hazards from official authoritative warnings
        ai_detected_hazards = [
            h for h in all_hazards if not h.is_official_warning and not h.hazard_type.startswith("OFFICIAL_WARNING_")
        ]

        # 6b. Integrate NWP Guidance Hazards (Advisory Only - Never Overrides Official Warnings)
        nwp_items: List[NormalizedNWPForecastItem] = []
        if nwp_guidance is not None:
            if isinstance(nwp_guidance, list):
                nwp_items = [item for item in nwp_guidance if isinstance(item, NormalizedNWPForecastItem)]
            elif isinstance(nwp_guidance, NormalizedNWPForecastItem):
                nwp_items = [nwp_guidance]

        for item in nwp_items:
            m_name = item.model_name.value.upper() if hasattr(item.model_name, "value") else str(item.model_name)
            vars = item.variables
            # Heavy precipitation signal from numerical model
            precip = vars.precipitation_mm or vars.precip_total_mm or vars.precip_1h_mm or 0.0
            if precip >= 50.0:
                desc = (
                    f"Numerical model simulation from {m_name} (run {item.model_run or 'current'}) "
                    f"indicates intense localized precipitation of {precip:.1f} mm."
                )
                h = HazardDetection(
                    hazard_type=f"NWP_{m_name}_HEAVY_RAINFALL",
                    severity=RiskLevelEnum.HIGH,
                    details=desc,
                    evidence=[desc],
                    source=item.source,
                    is_official_warning=False,
                )
                ai_detected_hazards.append(h)
                all_hazards.append(h)
            elif precip >= 25.0:
                desc = f"Numerical model simulation from {m_name} indicates accumulation of {precip:.1f} mm."
                h = HazardDetection(
                    hazard_type=f"NWP_{m_name}_MODERATE_RAINFALL",
                    severity=RiskLevelEnum.MEDIUM,
                    details=desc,
                    evidence=[desc],
                    source=item.source,
                    is_official_warning=False,
                )
                ai_detected_hazards.append(h)
                all_hazards.append(h)

            # Severe wind / gale signal from numerical model
            wind = vars.wind_gust_kmh or vars.wind_speed_kmh or 0.0
            if wind >= 75.0:
                desc = f"Numerical model {m_name} projects strong wind gusts of {wind:.1f} km/h."
                h = HazardDetection(
                    hazard_type=f"NWP_{m_name}_GALE_WINDS",
                    severity=RiskLevelEnum.HIGH,
                    details=desc,
                    evidence=[desc],
                    source=item.source,
                    is_official_warning=False,
                )
                ai_detected_hazards.append(h)
                all_hazards.append(h)

            # Atmospheric instability (CAPE)
            if vars.cape_jkg and vars.cape_jkg >= 2500.0:
                desc = f"Atmospheric instability detected by {m_name} indicating severe convection potential ({vars.cape_jkg:.0f} J/kg)."
                h = HazardDetection(
                    hazard_type=f"NWP_{m_name}_SEVERE_CONVECTION",
                    severity=RiskLevelEnum.MEDIUM,
                    details=desc,
                    evidence=[desc],
                    source=item.source,
                    is_official_warning=False,
                )
                ai_detected_hazards.append(h)
                all_hazards.append(h)

        # 7. Determine Overall Risk Level
        # Official warnings take unconditional priority in determining risk severity
        overall_risk = RiskLevelEnum.LOW
        for alert in valid_active_alerts:
            if alert.severity == RiskLevelEnum.EXTREME:
                overall_risk = RiskLevelEnum.EXTREME
                break
            elif alert.severity == RiskLevelEnum.HIGH and overall_risk != RiskLevelEnum.EXTREME:
                overall_risk = RiskLevelEnum.HIGH
            elif alert.severity == RiskLevelEnum.MEDIUM and overall_risk == RiskLevelEnum.LOW:
                overall_risk = RiskLevelEnum.MEDIUM

        # If no official warning, derive from AI-detected hazards (including NWP advisories)
        if not valid_active_alerts:
            for h in ai_detected_hazards:
                if h.severity == RiskLevelEnum.EXTREME:
                    overall_risk = RiskLevelEnum.EXTREME
                    break
                elif h.severity == RiskLevelEnum.HIGH and overall_risk != RiskLevelEnum.EXTREME:
                    overall_risk = RiskLevelEnum.HIGH
                elif h.severity == RiskLevelEnum.MEDIUM and overall_risk == RiskLevelEnum.LOW:
                    overall_risk = RiskLevelEnum.MEDIUM

        # 8. Forecast Consistency Score & Confidence Calculation (Phase 9)
        timing_disagreement = any("timeline divergence" in agreement_note or "timing" in c.lower() for c in contradictions)
        consistency_score = calculate_consistency_score(
            agreement=agreement,
            freshness=freshness_status,
            has_active_warning=bool(valid_active_alerts),
            data_complete=is_complete,
            contradiction_count=len(contradictions),
            timing_disagreement=timing_disagreement
        )

        confidence_level = determine_confidence_level(
            score=consistency_score,
            agreement=agreement,
            freshness=freshness_status,
            data_complete=is_complete,
            contradiction_count=len(contradictions)
        )
        confidence_indicator = confidence_level.value.capitalize()

        consistency_factors = build_consistency_factors(
            primary=primary_weather,
            secondary=secondary_weather,
            primary_forecast=forecast,
            secondary_forecast=secondary_forecast,
            freshness=freshness_status,
            data_complete=is_complete,
            contradictions=contradictions,
            agreement=agreement,
            confidence_level=confidence_level
        )

        # 9. Uncertainty Formulation
        uncertainty_elements = []
        if confidence_level == ConfidenceLevelEnum.LOW:
            uncertainty_elements.append(consistency_factors.summary or f"Forecast sources show divergence: {agreement_note}")
        elif agreement == SourceAgreementEnum.LOW:
            uncertainty_elements.append(f"Forecast sources show divergence: {agreement_note}")
        if freshness_status == FreshnessStatusEnum.STALE:
            uncertainty_elements.append(f"Observation data is {age_mins} minutes old.")
        if contradictions:
            uncertainty_elements.extend(contradictions)
        if warnings_unavail:
            uncertainty_elements.append("Official warning information is currently unavailable.")
        if nwp_comparison and getattr(nwp_comparison, "high_spread", False):
            spread_sum = getattr(nwp_comparison, "spread_summary", "High spread among numerical models")
            uncertainty_elements.append(f"NWP divergence: {spread_sum}")

        uncertainty_note = " | ".join(uncertainty_elements) if uncertainty_elements else None

        sources_used = [primary_weather.source]
        if secondary_weather and secondary_weather.source not in sources_used:
            sources_used.append(secondary_weather.source)
        for item in nwp_items:
            m_val = item.model_name.value if hasattr(item.model_name, "value") else str(item.model_name)
            nwp_src = f"{item.source}:{m_val}"
            if nwp_src not in sources_used:
                sources_used.append(nwp_src)
        if nwp_comparison and hasattr(nwp_comparison, "source"):
            if nwp_comparison.source not in sources_used:
                sources_used.append(nwp_comparison.source)

        nwp_guidance_dict = None
        if nwp_items:
            nwp_guidance_dict = {
                "count": len(nwp_items),
                "models": [it.model_dump() if hasattr(it, "model_dump") else dict(it) for it in nwp_items],
            }
            if len(nwp_items) == 1:
                nwp_guidance_dict.update(nwp_items[0].model_dump() if hasattr(nwp_items[0], "model_dump") else dict(nwp_items[0]))
        elif nwp_guidance and isinstance(nwp_guidance, dict):
            nwp_guidance_dict = nwp_guidance

        nwp_comp_dict = None
        if nwp_comparison:
            nwp_comp_dict = nwp_comparison.model_dump() if hasattr(nwp_comparison, "model_dump") else (dict(nwp_comparison) if isinstance(nwp_comparison, dict) else None)

        return WeatherReasoningResult(
            evaluated_at=now,
            location=primary_weather.location.name,
            freshness=freshness_status,
            data_age_minutes=age_mins,
            data_complete=is_complete,
            missing_fields=missing_fields,
            source_agreement=agreement,
            consistency_score=consistency_score,
            confidence_level=confidence_level,
            confidence_indicator=confidence_indicator,
            consistency_factors=consistency_factors.model_dump(),
            contradictions=contradictions,
            active_warnings=valid_active_alerts,
            detected_hazards=all_hazards,
            ai_detected_hazards=ai_detected_hazards,
            overall_risk=overall_risk,
            uncertainty_note=uncertainty_note,
            sources_used=sources_used,
            warnings_available=not warnings_unavail,
            nwp_guidance=nwp_guidance_dict,
            nwp_comparison=nwp_comp_dict,
        )
