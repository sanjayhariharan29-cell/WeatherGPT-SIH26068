"""Hazard Detection & Calibration Module for WeatherGPT.

Detects meteorological hazards based on official IMD thresholds, application thresholds,
and active official warnings. Provides deterministic calibration, multi-signal evidence,
temporal hazard scoping (current vs. forecast), and numeric sanitization.
"""

import math
from typing import List, Optional
from ai.config import get_ai_config
from ai.models import (
    ForecastItem,
    HazardDetection,
    OfficialAlert,
    RiskLevelEnum,
    WeatherRecord,
)


def _is_valid_num(val: Optional[float], min_val: float = -float("inf"), max_val: float = float("inf")) -> bool:
    """Validates that a numeric value is non-null, finite, not NaN, and within physical bounds."""
    if val is None:
        return False
    if not isinstance(val, (int, float)):
        return False
    if math.isnan(val) or math.isinf(val):
        return False
    return min_val <= val <= max_val


def detect_hazards(
    current_weather: Optional[WeatherRecord],
    forecast: Optional[List[ForecastItem]] = None,
    active_alerts: Optional[List[OfficialAlert]] = None
) -> List[HazardDetection]:
    """Evaluates observations, forecasts, and alerts to identify meteorological hazards."""
    hazards: List[HazardDetection] = []
    active_alerts = active_alerts or []
    forecast = forecast or []

    cfg = get_ai_config()
    thresholds = cfg.thresholds

    # -------------------------------------------------------------
    # 1. Official Alerts First (Authoritative Priority Hierarchy)
    # -------------------------------------------------------------
    for alert in active_alerts:
        alert_evidence = [
            f"Official {alert.source} {alert.severity.value.upper()} alert: '{alert.title}'",
            f"Valid from {alert.issued_at.isoformat()} to {alert.expires_at.isoformat()}"
        ]
        if alert.affected_locations:
            alert_evidence.append(f"Affected locations: {', '.join(alert.affected_locations)}")

        hazards.append(HazardDetection(
            hazard_type=f"OFFICIAL_WARNING_{alert.type.upper()}",
            detected=True,
            severity=alert.severity,
            details=f"Official IMD warning active: {alert.title}. {alert.description}",
            evidence=alert_evidence,
            source=alert.source,
            is_official_warning=True,
            current_or_forecast="current",
            effective_from=alert.issued_at,
            effective_until=alert.expires_at
        ))

    # -------------------------------------------------------------
    # 2. Extract Validated Signals from Current Weather and Forecast
    # -------------------------------------------------------------
    curr_rain_prob = current_weather.rain_probability if (current_weather and _is_valid_num(current_weather.rain_probability, 0.0, 100.0)) else None
    curr_rain_mm = current_weather.rainfall_amount_mm if (current_weather and _is_valid_num(current_weather.rainfall_amount_mm, 0.0, 2000.0)) else None
    curr_wind_speed = current_weather.wind_speed if (current_weather and _is_valid_num(current_weather.wind_speed, 0.0, 350.0)) else None
    curr_temp = current_weather.temperature if (current_weather and _is_valid_num(current_weather.temperature, -50.0, 60.0)) else None
    curr_cond = current_weather.weather_condition.lower() if (current_weather and current_weather.weather_condition) else ""
    curr_source = current_weather.source if current_weather else "Observation"

    # Peak and temporal tracking across forecast
    fc_max_rain_prob: Optional[float] = None
    fc_max_rain_prob_time: str = ""
    fc_max_rain_mm: Optional[float] = None
    fc_max_rain_mm_time: str = ""
    fc_max_wind: Optional[float] = None
    fc_max_wind_time: str = ""
    fc_max_temp: Optional[float] = None
    fc_max_temp_time: str = ""
    fc_min_temp: Optional[float] = None
    fc_min_temp_time: str = ""
    fc_thunderstorms: List[str] = []
    fc_fogs: List[str] = []

    for f in forecast:
        if _is_valid_num(f.rain_probability, 0.0, 100.0):
            if fc_max_rain_prob is None or f.rain_probability > fc_max_rain_prob:
                fc_max_rain_prob = f.rain_probability
                fc_max_rain_prob_time = f.time
        if _is_valid_num(f.rainfall_amount_mm, 0.0, 2000.0):
            if fc_max_rain_mm is None or f.rainfall_amount_mm > fc_max_rain_mm:
                fc_max_rain_mm = f.rainfall_amount_mm
                fc_max_rain_mm_time = f.time
        if _is_valid_num(f.wind_speed, 0.0, 350.0):
            if fc_max_wind is None or f.wind_speed > fc_max_wind:
                fc_max_wind = f.wind_speed
                fc_max_wind_time = f.time
        if _is_valid_num(f.temperature, -50.0, 60.0):
            if fc_max_temp is None or f.temperature > fc_max_temp:
                fc_max_temp = f.temperature
                fc_max_temp_time = f.time
            if fc_min_temp is None or f.temperature < fc_min_temp:
                fc_min_temp = f.temperature
                fc_min_temp_time = f.time
        f_cond = f.condition.lower() if f.condition else ""
        if any(term in f_cond for term in ("thunder", "lightning", "squall")):
            fc_thunderstorms.append(f.time)
        if any(term in f_cond for term in ("dense fog", "fog", "smog")):
            fc_fogs.append(f.time)

    # -------------------------------------------------------------
    # 3. Precipitation Hazards (Rainfall Amount & Probability)
    # -------------------------------------------------------------
    peak_rain_mm = max(
        [v for v in (curr_rain_mm, fc_max_rain_mm) if v is not None],
        default=None
    )
    peak_rain_prob = max(
        [v for v in (curr_rain_prob, fc_max_rain_prob) if v is not None],
        default=0.0
    )

    rain_evidence: List[str] = []
    rain_current = False
    rain_forecast = False

    if curr_rain_mm is not None and curr_rain_mm >= thresholds.moderate_rain_mm_threshold:
        rain_current = True
        rain_evidence.append(f"Current observed rainfall {curr_rain_mm:.1f} mm")
    elif curr_rain_prob is not None and curr_rain_prob >= thresholds.moderate_rain_prob_threshold:
        rain_current = True
        rain_evidence.append(f"Current precipitation probability {curr_rain_prob:.0f}%")

    if fc_max_rain_mm is not None and fc_max_rain_mm >= thresholds.moderate_rain_mm_threshold:
        rain_forecast = True
        rain_evidence.append(f"Forecast peak rainfall {fc_max_rain_mm:.1f} mm at {fc_max_rain_mm_time}")
    elif fc_max_rain_prob is not None and fc_max_rain_prob >= thresholds.moderate_rain_prob_threshold:
        rain_forecast = True
        rain_evidence.append(f"Forecast peak rain probability {fc_max_rain_prob:.0f}% at {fc_max_rain_prob_time}")

    rain_temporal = "both" if (rain_current and rain_forecast) else ("current" if rain_current else "forecast")

    # 3.1 Extreme Rainfall (>= 204.5 mm per IMD criteria)
    if peak_rain_mm is not None and peak_rain_mm >= thresholds.extreme_rain_mm_threshold:
        hazards.append(HazardDetection(
            hazard_type="EXTREME_RAINFALL",
            detected=True,
            severity=RiskLevelEnum.EXTREME,
            details=f"Extremely heavy rainfall detected ({peak_rain_mm:.1f} mm) meeting IMD extreme disaster criteria. Severe flash flood danger.",
            evidence=rain_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=rain_temporal
        ))
    # 3.2 Very Heavy Rainfall (115.6 - 204.4 mm per IMD criteria)
    elif peak_rain_mm is not None and peak_rain_mm >= thresholds.very_heavy_rain_mm_threshold:
        hazards.append(HazardDetection(
            hazard_type="VERY_HEAVY_RAINFALL",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details=f"Very heavy rainfall detected ({peak_rain_mm:.1f} mm) per IMD criteria. Significant waterlogging danger.",
            evidence=rain_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=rain_temporal
        ))
    # 3.3 Heavy Rainfall (>= 64.5 mm or rain prob >= 80%)
    elif (peak_rain_mm is not None and peak_rain_mm >= thresholds.heavy_rain_mm_threshold) or peak_rain_prob >= thresholds.heavy_rain_prob_threshold:
        hazards.append(HazardDetection(
            hazard_type="HEAVY_RAINFALL",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details=f"High probability of heavy precipitation ({peak_rain_prob:.0f}%" + (f", {peak_rain_mm:.1f} mm" if peak_rain_mm else "") + ").",
            evidence=rain_evidence or [f"Precipitation probability {peak_rain_prob:.0f}% exceeds threshold 80%"],
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=rain_temporal
        ))
    # 3.4 Moderate Rainfall (>= 15.6 mm or rain prob >= 60%)
    elif (peak_rain_mm is not None and peak_rain_mm >= thresholds.moderate_rain_mm_threshold) or peak_rain_prob >= thresholds.moderate_rain_prob_threshold:
        hazards.append(HazardDetection(
            hazard_type="MODERATE_RAINFALL",
            detected=True,
            severity=RiskLevelEnum.MEDIUM,
            details=f"Moderate rain probability detected ({peak_rain_prob:.0f}%" + (f", {peak_rain_mm:.1f} mm" if peak_rain_mm else "") + ").",
            evidence=rain_evidence or [f"Precipitation probability {peak_rain_prob:.0f}% exceeds threshold 60%"],
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=rain_temporal
        ))

    # -------------------------------------------------------------
    # 4. Wind / Gale / Cyclonic Wind Hazards
    # -------------------------------------------------------------
    peak_wind_val = max(
        [v for v in (curr_wind_speed, fc_max_wind) if v is not None],
        default=0.0
    )
    wind_current = bool(curr_wind_speed and curr_wind_speed >= thresholds.strong_wind_threshold)
    wind_forecast = bool(fc_max_wind and fc_max_wind >= thresholds.strong_wind_threshold)
    wind_temporal = "both" if (wind_current and wind_forecast) else ("current" if wind_current else "forecast")
    wind_evidence: List[str] = []
    if wind_current:
        wind_evidence.append(f"Current observed wind speed {curr_wind_speed:.0f} km/h")
    if wind_forecast:
        wind_evidence.append(f"Forecast peak wind speed {fc_max_wind:.0f} km/h at {fc_max_wind_time}")

    if peak_wind_val >= thresholds.severe_gale_wind_threshold:
        hazards.append(HazardDetection(
            hazard_type="GALE_CYCLONIC_WINDS",
            detected=True,
            severity=RiskLevelEnum.EXTREME,
            details=f"Violent cyclonic / storm-force winds detected ({peak_wind_val:.0f} km/h >= 88 km/h). Extreme structural and marine peril.",
            evidence=wind_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=wind_temporal
        ))
    elif peak_wind_val >= thresholds.gale_wind_threshold:
        hazards.append(HazardDetection(
            hazard_type="GALE_CYCLONIC_WINDS",
            detected=True,
            severity=RiskLevelEnum.EXTREME,
            details=f"Dangerous gale wind speeds detected ({peak_wind_val:.0f} km/h). Extreme hazard to marine and outdoor activities.",
            evidence=wind_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=wind_temporal
        ))
    elif peak_wind_val >= thresholds.strong_wind_threshold:
        hazards.append(HazardDetection(
            hazard_type="STRONG_WINDS",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details=f"Strong wind gusts ({peak_wind_val:.0f} km/h) can cause localized disruptions.",
            evidence=wind_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=wind_temporal
        ))

    # -------------------------------------------------------------
    # 5. Temperature Hazards (Heatwave & Coldwave)
    # -------------------------------------------------------------
    peak_temp_val = max(
        [v for v in (curr_temp, fc_max_temp) if v is not None],
        default=0.0
    )
    temp_current = bool(curr_temp and curr_temp >= thresholds.heatwave_temp_threshold)
    temp_forecast = bool(fc_max_temp and fc_max_temp >= thresholds.heatwave_temp_threshold)
    temp_temporal = "both" if (temp_current and temp_forecast) else ("current" if temp_current else "forecast")
    temp_evidence: List[str] = []
    if temp_current:
        temp_evidence.append(f"Current observed temperature {curr_temp:.1f}°C")
    if temp_forecast:
        temp_evidence.append(f"Forecast peak temperature {fc_max_temp:.1f}°C at {fc_max_temp_time}")

    if peak_temp_val >= thresholds.severe_heatwave_temp_threshold:
        hazards.append(HazardDetection(
            hazard_type="HEATWAVE",
            detected=True,
            severity=RiskLevelEnum.EXTREME,
            details=f"Severe heatwave conditions detected ({peak_temp_val:.1f}°C >= 45°C). High risk of heat stroke and severe thermal stress.",
            evidence=temp_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=temp_temporal
        ))
    elif peak_temp_val >= thresholds.heatwave_temp_threshold:
        hazards.append(HazardDetection(
            hazard_type="HEATWAVE",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details=f"Extreme temperature ({peak_temp_val:.1f}°C) approaching heatwave threshold.",
            evidence=temp_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=temp_temporal
        ))

    # Coldwave checks
    valid_temps = [v for v in (curr_temp, fc_min_temp) if v is not None]
    if valid_temps:
        min_temp_val = min(valid_temps)
        if min_temp_val <= thresholds.severe_coldwave_temp_threshold:
            cold_evidence = []
            if curr_temp is not None and curr_temp <= thresholds.severe_coldwave_temp_threshold:
                cold_evidence.append(f"Current observed temperature {curr_temp:.1f}°C")
            if fc_min_temp is not None and fc_min_temp <= thresholds.severe_coldwave_temp_threshold:
                cold_evidence.append(f"Forecast minimum temperature {fc_min_temp:.1f}°C at {fc_min_temp_time}")
            hazards.append(HazardDetection(
                hazard_type="COLDWAVE",
                detected=True,
                severity=RiskLevelEnum.HIGH,
                details=f"Severe coldwave conditions detected ({min_temp_val:.1f}°C <= 4°C). Hypothermia and frost risk.",
                evidence=cold_evidence,
                source=curr_source,
                is_official_warning=False,
                current_or_forecast="both" if len(cold_evidence) > 1 else ("current" if (curr_temp and curr_temp <= thresholds.severe_coldwave_temp_threshold) else "forecast")
            ))
        elif min_temp_val <= thresholds.coldwave_temp_threshold:
            cold_evidence = []
            if curr_temp is not None and curr_temp <= thresholds.coldwave_temp_threshold:
                cold_evidence.append(f"Current observed temperature {curr_temp:.1f}°C")
            if fc_min_temp is not None and fc_min_temp <= thresholds.coldwave_temp_threshold:
                cold_evidence.append(f"Forecast minimum temperature {fc_min_temp:.1f}°C at {fc_min_temp_time}")
            hazards.append(HazardDetection(
                hazard_type="COLDWAVE",
                detected=True,
                severity=RiskLevelEnum.MEDIUM,
                details=f"Coldwave conditions detected ({min_temp_val:.1f}°C <= 10°C).",
                evidence=cold_evidence,
                source=curr_source,
                is_official_warning=False,
                current_or_forecast="both" if len(cold_evidence) > 1 else ("current" if (curr_temp and curr_temp <= thresholds.coldwave_temp_threshold) else "forecast")
            ))

    # -------------------------------------------------------------
    # 6. Thunderstorm & Lightning Hazards
    # -------------------------------------------------------------
    curr_thunder = any(term in curr_cond for term in ("thunder", "lightning", "squall"))
    fc_thunder = bool(fc_thunderstorms)
    if curr_thunder or fc_thunder:
        t_evidence = []
        if curr_thunder and current_weather:
            t_evidence.append(f"Current atmospheric condition: '{current_weather.weather_condition}'")
        if fc_thunder:
            t_evidence.append(f"Thunderstorm forecast periods: {', '.join(fc_thunderstorms[:3])}")
        hazards.append(HazardDetection(
            hazard_type="THUNDERSTORM_LIGHTNING",
            detected=True,
            severity=RiskLevelEnum.HIGH,
            details="Thunderstorm with potential lightning strikes indicated. Seek safe indoor shelter.",
            evidence=t_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast="both" if (curr_thunder and fc_thunder) else ("current" if curr_thunder else "forecast")
        ))

    # -------------------------------------------------------------
    # 7. Low Visibility / Dense Fog Hazards
    # -------------------------------------------------------------
    curr_fog = any(term in curr_cond for term in ("dense fog", "fog", "smog"))
    curr_dense_fog = "dense fog" in curr_cond
    fc_fog = bool(fc_fogs)
    if curr_fog or fc_fog:
        fog_evidence = []
        if curr_fog and current_weather:
            fog_evidence.append(f"Current atmospheric condition: '{current_weather.weather_condition}'")
        if fc_fog:
            fog_evidence.append(f"Fog forecast periods: {', '.join(fc_fogs[:3])}")
        is_dense = curr_dense_fog or any("dense fog" in f.lower() for f in fc_fogs)
        hazards.append(HazardDetection(
            hazard_type="LOW_VISIBILITY",
            detected=True,
            severity=RiskLevelEnum.HIGH if is_dense else RiskLevelEnum.MEDIUM,
            details="Dense fog with severely restricted visibility (<200m)." if is_dense else "Reduced visibility due to fog/smog. Exercise caution during transit.",
            evidence=fog_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast="both" if (curr_fog and fc_fog) else ("current" if curr_fog else "forecast")
        ))

    # -------------------------------------------------------------
    # 8. Flash Flood / Waterlogging Risk
    # -------------------------------------------------------------
    flood_triggered = False
    flood_evidence: List[str] = []
    if peak_rain_mm is not None and peak_rain_mm >= thresholds.very_heavy_rain_mm_threshold:
        flood_triggered = True
        flood_evidence.append(f"Precipitation accumulation ({peak_rain_mm:.1f} mm) exceeds very heavy threshold (115.6 mm)")
    if any(term in curr_cond for term in ("flood", "waterlogging", "inundation")):
        flood_triggered = True
        if current_weather:
            flood_evidence.append(f"Observation condition reports '{current_weather.weather_condition}'")

    if flood_triggered:
        flood_severity = RiskLevelEnum.EXTREME if (peak_rain_mm and peak_rain_mm >= thresholds.extreme_rain_mm_threshold) else RiskLevelEnum.HIGH
        hazards.append(HazardDetection(
            hazard_type="FLOOD_RISK",
            detected=True,
            severity=flood_severity,
            details="Significant risk of localized flooding, urban waterlogging, and flash inundation.",
            evidence=flood_evidence,
            source=curr_source,
            is_official_warning=False,
            current_or_forecast=rain_temporal
        ))

    return hazards
