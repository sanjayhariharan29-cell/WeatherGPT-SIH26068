"""Specialized Weather Advisory Modes for SkyZen.

Implements persona-aware, domain-specific advisory interfaces:
1. Farmer Mode: Rainfall, irrigation timing, heat/stress awareness, activity planning.
2. Fisherman / Marine Mode: Wind, wave telemetry (where verified), precipitation, marine alerts, departure verdict.
3. Aviation Mode: Airport/location, wind, visibility (where verified), precipitation, convective storms, hazards.
4. Commuter / Student Mode: Departure/return times, rain risk, heat, wind, umbrella/clothing/travel guidance.
5. Disaster Mode: Active warning summary, affected location, severity, action guidance, notification status.
6. Smart City Mode: Location-based rainfall, heat, AQI (where verified), severe weather, civic alert overview.

Strict Principles:
- Safety Hierarchy: Official IMD warnings take unconditional precedence over telemetry and models.
- Grounding: Missing domain measurements (e.g., wave height, visibility, AQI) are NEVER fabricated.
- Disclaimers: Explicitly defined as advisory interfaces, NOT certified agronomic, marine, or aviation decision systems.
- Multilingual: Deterministic localized guidance across English, Tamil, Hindi, Marathi, and Telugu.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from ai.models import (
    AdvisoryModeEnum,
    AdvisoryPriorityEnum,
    AdvisoryTypeEnum,
    DecisionAdvisory,
    ForecastItem,
    HazardDetection,
    LanguageEnum,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    TimeContextEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.llm.multilingual import resolve_target_language


# ==============================================================================
# 1. Specialized Mode Output Schemas
# ==============================================================================

class FarmerAdvisoryResult(BaseModel):
    """Domain-specific advisory for farmers and agricultural planners."""
    mode: str = "farmer"
    rainfall_advisory: str
    rain_probability_pct: float = 0.0
    expected_rainfall_mm: float = 0.0
    irrigation_timing: str
    irrigation_guidance: str
    heat_stress_awareness: str
    heat_stress_level: str  # "normal", "moderate_heat", "severe_heatwave", "cold_stress"
    temperature_c: Optional[float] = None
    weather_sensitive_planning: List[str] = Field(default_factory=list)
    spraying_viable: bool = True
    spraying_guidance: str = ""
    harvest_protection_needed: bool = False
    disclaimer: str = (
        "Advisory interface based strictly on verified atmospheric observations. "
        "Does not provide certified agronomic prescriptions or crop-specific treatment guarantees."
    )


class MarineAdvisoryResult(BaseModel):
    """Domain-specific advisory for coastal fishermen and small craft operators."""
    mode: str = "fisherman"
    wind_conditions: Dict[str, Any]
    wave_information: Dict[str, Any]
    precipitation: Dict[str, Any]
    official_marine_warnings: List[str] = Field(default_factory=list)
    has_official_warning: bool = False
    departure_verdict: str  # "GO", "CAUTION", "NO_GO"
    departure_advisory: str
    coastal_location: str
    disclaimer: str = (
        "Advisory interface only. Official IMD marine warnings take unconditional legal "
        "and operational precedence. Not a certified Coast Guard or port clearance."
    )


class AviationAdvisoryResult(BaseModel):
    """Domain-specific advisory framework for general aviation and aerodrome weather awareness."""
    mode: str = "aviation"
    airport_or_location: str
    wind_conditions: Dict[str, Any]
    visibility: Dict[str, Any]
    precipitation: Dict[str, Any]
    thunderstorms: Dict[str, Any]
    weather_hazards: List[str] = Field(default_factory=list)
    advisory_summary: str
    flight_category_indicator: str  # "VFR_FAVORABLE", "MARGINAL_VFR", "INSTRUMENT_ADVISORY", "HAZARDOUS"
    disclaimer: str = (
        "Advisory interface based on surface meteorological telemetry. NOT a certified "
        "aviation meteorological briefing (METAR/TAF/SIGMET) and cannot be used for regulatory flight planning."
    )


class CommuterStudentAdvisoryResult(BaseModel):
    """Domain-specific transit and commute guidance for students and daily commuters."""
    mode: str = "commuter"
    departure_time: str
    return_time: str
    rain_risk: Dict[str, Any]
    heat_conditions: Dict[str, Any]
    wind_conditions: Dict[str, Any]
    umbrella_recommendation: bool
    umbrella_rationale: str
    clothing_advisory: str
    travel_advisory: str
    delay_buffer_minutes: int = 0
    route_safety_summary: str


class DisasterAdvisoryResult(BaseModel):
    """Domain-specific emergency management advisory for disaster response and public safety."""
    mode: str = "disaster"
    active_warning_summary: List[Dict[str, Any]] = Field(default_factory=list)
    affected_location: str
    severity: str  # "extreme", "high", "medium", "low"
    action_guidance: List[str] = Field(default_factory=list)
    notification_status: Dict[str, Any] = Field(default_factory=dict)
    official_priority_preserved: bool = True
    coordination_notice: str = (
        "Emergency advisory synthesized from authoritative IMD bulletins and validated hazard telemetry."
    )


class SmartCityAdvisoryResult(BaseModel):
    """Domain-specific civic resilience advisory for urban planners, municipal services, and citizens."""
    mode: str = "smart_city"
    location_name: str
    rainfall_summary: Dict[str, Any]
    heat_summary: Dict[str, Any]
    aqi_summary: Dict[str, Any]
    severe_weather: Dict[str, Any]
    alert_overview: List[str] = Field(default_factory=list)
    civic_action_items: List[str] = Field(default_factory=list)
    drainage_watch_status: str  # "NORMAL", "WATCH", "WARNING", "ALERT"


class SpecializedModeResponse(BaseModel):
    """Unified container for specialized domain weather advisories."""
    mode: str
    location: str
    risk_level: RiskLevelEnum
    priority: AdvisoryPriorityEnum
    headline: str
    concise_answer: str
    localized_answers: Dict[str, str] = Field(default_factory=dict)
    key_precautions: List[str] = Field(default_factory=list)
    official_warning_present: bool
    official_warning_title: Optional[str] = None
    source_attribution: str
    timestamp_info: str
    details: Dict[str, Any] = Field(default_factory=dict)
    disclaimer: str


# ==============================================================================
# 2. Specialized Advisory Engine
# ==============================================================================

class SpecializedAdvisoryEngine:
    """Evaluates verified meteorological evidence into specialized domain advisory modes."""

    # --------------------------------------------------------------------------
    # A. FARMER MODE
    # --------------------------------------------------------------------------
    @classmethod
    def evaluate_farmer_mode(
        cls,
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        target_language: LanguageEnum = LanguageEnum.EN
    ) -> FarmerAdvisoryResult:
        """Evaluates verified telemetry for agriculture, irrigation timing, and crop stress."""
        active_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_present = active_warning is not None

        # Extract verified meteorological metrics
        temp_c = weather.temperature if weather else None
        humidity_pct = weather.humidity if weather else None
        rain_prob = float(weather.rain_probability or 0.0) if weather else 0.0
        rain_mm = float(weather.rainfall_amount_mm or 0.0) if weather else 0.0
        wind_spd = float(weather.wind_speed or 0.0) if weather else 0.0

        if forecast:
            fc_max_prob = max((float(fc.rain_probability or 0.0) for fc in forecast), default=0.0)
            fc_max_mm = max((float(fc.rainfall_amount_mm or 0.0) for fc in forecast), default=0.0)
            rain_prob = max(rain_prob, fc_max_prob)
            rain_mm = max(rain_mm, fc_max_mm)

        all_hazards = reasoning.detected_hazards or []
        has_rain_hazard = any("rain" in h.hazard_type.lower() for h in all_hazards)

        # 1. Rainfall Advisory
        if warning_present and "rain" in active_warning.title.lower():
            rainfall_adv = f"Official Heavy Rain Warning Active ({active_warning.title}). Substantial field precipitation expected."
        elif rain_prob >= 70.0 or rain_mm >= 15.0 or has_rain_hazard:
            rainfall_adv = f"High precipitation likelihood ({rain_prob:.0f}%, {rain_mm:.1f} mm). Heavy showers anticipated."
        elif rain_prob >= 40.0 or rain_mm > 2.0:
            rainfall_adv = f"Moderate rain chance ({rain_prob:.0f}%, {rain_mm:.1f} mm). Intermittent field precipitation likely."
        elif rain_prob >= 20.0:
            rainfall_adv = f"Low precipitation risk ({rain_prob:.0f}%). Isolated drizzle or passing light showers possible."
        else:
            rainfall_adv = "Dry conditions prevail. No significant precipitation expected across crop acreage."

        # 2. Irrigation Timing Guidance
        if warning_present or rain_prob >= 50.0 or rain_mm >= 10.0:
            irr_timing = "suspend_immediately"
            irr_guidance = (
                "Suspend all irrigation immediately. Natural precipitation is adequate to prevent soil moisture deficit. "
                "Prolonged artificial watering risks root-zone waterlogging, soil aeration loss, and nutrient leaching."
            )
        elif rain_prob >= 30.0:
            irr_timing = "defer_and_monitor"
            irr_guidance = (
                "Defer scheduled watering cycle. Monitor topsoil moisture depth; withhold water until expected "
                "precipitation window resolves to conserve energy and water table."
            )
        elif temp_c is not None and temp_c >= 35.0:
            irr_timing = "morning_or_evening_only"
            irr_guidance = (
                "Provide light, frequent irrigation strictly during early morning (before 08:00) or late evening (after 18:00). "
                "Midday irrigation causes rapid evaporation loss and thermal shock to sensitive root zones."
            )
        else:
            irr_timing = "standard_schedule"
            irr_guidance = "Proceed with routine crop-specific irrigation schedule. Soil moisture evaporation rates are normal."

        # 3. Heat & Stress Awareness
        if temp_c is not None and temp_c >= 40.0:
            heat_level = "severe_heatwave"
            heat_adv = (
                f"Severe Heat Stress Alert ({temp_c:.1f}°C). Elevated risk of floral sterility, blossom drop, "
                "and accelerated vegetative transpiration. Apply organic mulching to conserve root moisture."
            )
        elif temp_c is not None and temp_c >= 35.0:
            heat_level = "moderate_heat"
            heat_adv = (
                f"Moderate Thermal Stress ({temp_c:.1f}°C). High evapotranspiration rates. "
                "Ensure standing crops have adequate soil moisture buffer."
            )
        elif temp_c is not None and temp_c < 12.0:
            heat_level = "cold_stress"
            heat_adv = (
                f"Cold Temperature Notice ({temp_c:.1f}°C). Slowed crop metabolism and potential chilling delay for tropical varieties."
            )
        else:
            heat_level = "normal"
            temp_str = f"{temp_c:.1f}°C" if temp_c is not None else "optimal"
            heat_adv = (
                f"Thermal conditions ({temp_str}) are within standard physiological growth range."
            )

        # 4. Weather-Sensitive Activity Planning
        planning: List[str] = []
        spraying_viable = True
        spraying_notes = ""

        # Spraying (chemical / foliar)
        if wind_spd > 20.0:
            spraying_viable = False
            spraying_notes = f"Postpone chemical and foliar spraying due to elevated wind speeds ({wind_spd:.0f} km/h); high risk of chemical drift loss."
            planning.append(spraying_notes)
        elif rain_prob >= 40.0:
            spraying_viable = False
            spraying_notes = f"Withhold spraying applications; rain probability ({rain_prob:.0f}%) risks chemical wash-off and environmental runoff."
            planning.append(spraying_notes)
        else:
            spraying_notes = "Calm winds and low rain probability provide favorable atmospheric window for field spraying."
            planning.append(spraying_notes)

        # Harvest protection
        harvest_needed = (rain_prob >= 40.0 or rain_mm >= 5.0 or warning_present)
        if harvest_needed:
            planning.append("Cover harvested produce and threshing floors with waterproof tarpaulins to prevent fungal spoilage.")
        else:
            planning.append("Favorable conditions for routine harvesting, threshing, and sun-drying of grains.")

        # Staking / Crop lodging
        if wind_spd >= 25.0:
            planning.append(f"Strong gusts ({wind_spd:.0f} km/h) detected. Provide mechanical staking or earthing-up for tall standing crops (banana, sugarcane, maize).")

        # Field drainage
        if rain_mm >= 25.0 or warning_present:
            planning.append("Inspect and clear field perimeter drainage furrows to prevent inundation in low-lying crop patches.")

        return FarmerAdvisoryResult(
            rainfall_advisory=rainfall_adv,
            rain_probability_pct=round(rain_prob, 1),
            expected_rainfall_mm=round(rain_mm, 1),
            irrigation_timing=irr_timing,
            irrigation_guidance=irr_guidance,
            heat_stress_awareness=heat_adv,
            heat_stress_level=heat_level,
            temperature_c=temp_c,
            weather_sensitive_planning=planning,
            spraying_viable=spraying_viable,
            spraying_guidance=spraying_notes,
            harvest_protection_needed=harvest_needed,
        )

    # --------------------------------------------------------------------------
    # B. FISHERMAN / MARINE MODE
    # --------------------------------------------------------------------------
    @classmethod
    def evaluate_marine_mode(
        cls,
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        target_language: LanguageEnum = LanguageEnum.EN
    ) -> MarineAdvisoryResult:
        """Evaluates coastal and marine weather risks with absolute IMD warning priority."""
        active_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_present = active_warning is not None

        loc_name = "Coastal Waters"
        if weather and getattr(weather, "location", None) and getattr(weather.location, "name", None):
            loc_name = weather.location.name
        elif active_warning and active_warning.affected_locations:
            loc_name = active_warning.affected_locations[0]

        # Extract verified wind & rain
        wind_spd = float(weather.wind_speed or 0.0) if weather else 0.0
        wind_dir = getattr(weather, "wind_direction", None) if weather else None
        rain_prob = float(weather.rain_probability or 0.0) if weather else 0.0
        rain_mm = float(weather.rainfall_amount_mm or 0.0) if weather else 0.0
        knots = round(wind_spd / 1.852, 1)

        # Wind classification
        if wind_spd >= 45.0:
            wind_class = "Gale / Storm Winds"
        elif wind_spd >= 30.0:
            wind_class = "Squally / Rough"
        elif wind_spd >= 18.0:
            wind_class = "Moderate Breeze"
        else:
            wind_class = "Calm / Light Breeze"

        wind_data = {
            "speed_kmh": round(wind_spd, 1),
            "speed_knots": knots,
            "direction_deg": wind_dir,
            "classification": wind_class,
            "is_hazardous": (wind_spd >= 35.0)
        }

        # Wave telemetry check: NEVER FABRICATE
        # Check if wave height is present in weather metadata or raw payload
        wave_height = getattr(weather, "wave_height_m", None) if weather else None
        wave_period = getattr(weather, "wave_period_s", None) if weather else None
        if wave_height is not None:
            wave_data = {
                "is_available": True,
                "wave_height_m": float(wave_height),
                "wave_period_s": float(wave_period) if wave_period is not None else None,
                "source": getattr(weather, "source", "Buoy Telemetry"),
                "summary": f"Observed wave height: {wave_height:.1f} m."
            }
        else:
            wave_data = {
                "is_available": False,
                "wave_height_m": None,
                "wave_period_s": None,
                "source": "None",
                "summary": "Direct wave telemetry unavailable for this coastal station. Refer to official INCOIS/IMD sea state bulletins."
            }

        all_hazards = reasoning.detected_hazards or []
        has_tstorm = any("thunder" in h.hazard_type.lower() or "cyclone" in h.hazard_type.lower() for h in all_hazards)
        precip_data = {
            "rain_probability": round(rain_prob, 1),
            "rainfall_mm": round(rain_mm, 1),
            "thunderstorm_risk": has_tstorm,
            "squall_expected": (wind_spd >= 35.0 or has_tstorm)
        }

        official_warnings: List[str] = []
        if warning_present:
            official_warnings.append(f"IMD Official Alert: {active_warning.title} ({active_warning.severity.value.upper()})")

        # SAFETY PRECEDENCE: Official warning ALWAYS forces NO_GO
        if warning_present:
            departure_verdict = "NO_GO"
            departure_advisory = (
                f"STRICT PROHIBITION: Official IMD marine warning active ({active_warning.title}). "
                f"Fishermen are strictly advised NOT to venture into the sea off {loc_name}. "
                "Secure all small craft, motorized catamarans, and trawlers at designated harbor moorings."
            )
        elif wind_spd >= 40.0 or has_tstorm or reasoning.overall_risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
            departure_verdict = "NO_GO"
            departure_advisory = (
                f"Squally weather with hazardous wind gusts ({wind_spd:.0f} km/h / {knots} knots) and rough seas. "
                "Sea venturing is strictly discouraged. Small craft should remain ashore."
            )
        elif wind_spd >= 25.0:
            departure_verdict = "CAUTION"
            departure_advisory = (
                f"Moderate to rough coastal conditions with winds up to {wind_spd:.0f} km/h ({knots} knots). "
                "Deep-sea venturing not recommended. Coastal fishing permitted only with mandatory life jackets and verified VHF communication equipment."
            )
        else:
            departure_verdict = "GO"
            departure_advisory = (
                f"Sea conditions off {loc_name} are currently favorable ({wind_spd:.0f} km/h / {knots} knots). "
                "Safe for routine coastal fishing operations. Maintain standard maritime life safety gear on board."
            )

        return MarineAdvisoryResult(
            wind_conditions=wind_data,
            wave_information=wave_data,
            precipitation=precip_data,
            official_marine_warnings=official_warnings,
            has_official_warning=warning_present,
            departure_verdict=departure_verdict,
            departure_advisory=departure_advisory,
            coastal_location=loc_name,
        )

    # --------------------------------------------------------------------------
    # C. AVIATION MODE
    # --------------------------------------------------------------------------
    @classmethod
    def evaluate_aviation_mode(
        cls,
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        airport_code: Optional[str] = None,
        target_language: LanguageEnum = LanguageEnum.EN
    ) -> AviationAdvisoryResult:
        """Evaluates surface weather indicators for aerodrome and general aviation awareness."""
        active_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_present = active_warning is not None

        apt_name = airport_code or (
            weather.location.name if weather and getattr(weather, "location", None) and getattr(weather.location, "name", None) else "Aerodrome Vicinity"
        )

        wind_spd = float(weather.wind_speed or 0.0) if weather else 0.0
        wind_dir = getattr(weather, "wind_direction", None) if weather else None
        knots = round(wind_spd / 1.852, 1)

        wind_info = {
            "speed_kmh": round(wind_spd, 1),
            "speed_knots": knots,
            "direction_deg": wind_dir,
            "crosswind_hazard": (wind_spd >= 28.0),
            "gust_potential": (wind_spd >= 35.0)
        }

        # Visibility telemetry: NEVER FABRICATE
        vis_km = getattr(weather, "visibility", None) if weather else None
        if vis_km is not None:
            vis_info = {
                "is_available": True,
                "visibility_km": round(float(vis_km), 2),
                "visibility_meters": int(float(vis_km) * 1000),
                "is_low_visibility": (float(vis_km) < 5.0)
            }
        else:
            vis_info = {
                "is_available": False,
                "visibility_km": None,
                "visibility_meters": None,
                "is_low_visibility": False,
                "note": "Direct runway visibility / transmissometer telemetry unavailable. Refer to official aerodrome METAR/ATIS."
            }

        rain_prob = float(weather.rain_probability or 0.0) if weather else 0.0
        rain_mm = float(weather.rainfall_amount_mm or 0.0) if weather else 0.0
        precip_info = {
            "probability": round(rain_prob, 1),
            "rainfall_mm": round(rain_mm, 1),
            "intensity": "Heavy" if rain_mm >= 15.0 else ("Moderate" if rain_mm >= 3.0 else ("Light" if rain_mm > 0.0 else "None"))
        }

        all_hazards = reasoning.detected_hazards or []
        has_tstorm = any("thunder" in h.hazard_type.lower() for h in all_hazards)
        has_fog = any("fog" in h.hazard_type.lower() or "visibility" in h.hazard_type.lower() for h in all_hazards)
        has_wind_hazard = any("wind" in h.hazard_type.lower() or "cyclone" in h.hazard_type.lower() for h in all_hazards)

        tstorm_info = {
            "detected": has_tstorm,
            "lightning_risk": has_tstorm,
            "convective_cloud_alert": has_tstorm
        }

        hazard_list: List[str] = []
        if warning_present:
            hazard_list.append(f"Official Warning: {active_warning.title}")
        if has_tstorm:
            hazard_list.append("Convective Thunderstorm / Lightning Hazard")
        if wind_spd >= 35.0 or has_wind_hazard:
            hazard_list.append(f"High Surface Winds / Gust Fronts ({wind_spd:.0f} km/h)")
        if vis_info["is_available"] and vis_info["is_low_visibility"]:
            hazard_list.append(f"Reduced Surface Visibility ({vis_km:.1f} km)")
        elif has_fog:
            hazard_list.append("Mist / Fog / Reduced Aerodrome Slant Visibility")

        # Flight category indication
        if warning_present or has_tstorm or wind_spd >= 45.0:
            flight_category = "HAZARDOUS"
            summary = (
                f"Hazardous terminal conditions at {apt_name}. Active thunderstorm or official weather warning. "
                "Severe turbulence and wind shear potential in terminal airspace."
            )
        elif (vis_info["is_available"] and vis_km < 5.0) or has_fog or wind_spd >= 30.0:
            flight_category = "MARGINAL_VFR"
            summary = (
                f"Marginal conditions at {apt_name}. Elevated surface wind ({knots} knots) or reduced visibility. "
                "Heightened surveillance for crosswind limits and approach minimums required."
            )
        else:
            flight_category = "VFR_FAVORABLE"
            summary = (
                f"Atmospheric indicators at {apt_name} are generally favorable for standard visual operations. "
                f"Surface winds {knots} knots, clear convective profile."
            )

        return AviationAdvisoryResult(
            airport_or_location=apt_name,
            wind_conditions=wind_info,
            visibility=vis_info,
            precipitation=precip_info,
            thunderstorms=tstorm_info,
            weather_hazards=hazard_list,
            advisory_summary=summary,
            flight_category_indicator=flight_category,
        )

    # --------------------------------------------------------------------------
    # D. COMMUTER / STUDENT MODE
    # --------------------------------------------------------------------------
    @classmethod
    def evaluate_commuter_student_mode(
        cls,
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        departure_time: Optional[str] = None,
        return_time: Optional[str] = None,
        target_language: LanguageEnum = LanguageEnum.EN
    ) -> CommuterStudentAdvisoryResult:
        """Evaluates transit corridors, schedule windows, umbrella necessity, and delay buffers."""
        active_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_present = active_warning is not None

        dep_t = departure_time or "08:00 AM"
        ret_t = return_time or "05:00 PM"

        temp_c = float(weather.temperature or 26.0) if weather else 26.0
        wind_spd = float(weather.wind_speed or 0.0) if weather else 0.0
        rain_prob = float(weather.rain_probability or 0.0) if weather else 0.0

        # Forecast evaluation for departure vs return
        dep_prob = rain_prob
        ret_prob = rain_prob
        if forecast and len(forecast) >= 2:
            dep_prob = float(forecast[0].rain_probability or rain_prob)
            ret_prob = float(forecast[-1].rain_probability or rain_prob)

        peak_prob = max(dep_prob, ret_prob, rain_prob)

        all_hazards = reasoning.detected_hazards or []
        has_rain = peak_prob >= 35.0 or any("rain" in h.hazard_type.lower() for h in all_hazards)
        has_heat = temp_c >= 35.0 or any("heat" in h.hazard_type.lower() for h in all_hazards)

        # Umbrella decision
        umbrella_rec = has_rain or warning_present or peak_prob >= 35.0
        if umbrella_rec:
            if warning_present:
                umbrella_rationale = f"Official rain warning active ({active_warning.title}). Carrying an umbrella or heavy raincoat is essential."
            elif peak_prob >= 60.0:
                umbrella_rationale = f"High precipitation probability during transit ({peak_prob:.0f}%). Rain gear strongly recommended."
            else:
                umbrella_rationale = f"Moderate rain chance ({peak_prob:.0f}%). Keep a compact umbrella in your commute bag."
        else:
            umbrella_rationale = "Precipitation probability is low across your commute windows. Rain protection not strictly necessary."

        # Clothing advisory
        if temp_c >= 37.0:
            clothing_adv = "Wear lightweight, loose-fitting, breathable cotton fabrics. Protect head/eyes with cap or sunglasses."
        elif temp_c < 18.0:
            clothing_adv = "Carry a light sweater or windbreaker jacket for cooler morning/evening transit."
        elif umbrella_rec:
            clothing_adv = "Water-resistant footwear and waterproof commuter bag cover recommended."
        else:
            clothing_adv = "Standard comfortable daily attire suitable for ambient conditions."

        # Travel buffer & delay calculation
        if warning_present:
            delay_buffer = 30
            travel_adv = (
                f"Severe Transit Advisory: Official warning active ({active_warning.title}). "
                "Expect major road waterlogging and metro/bus delays. Allow 30 minutes extra travel time. Avoid flooded underpasses."
            )
        elif peak_prob >= 60.0 or reasoning.overall_risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
            delay_buffer = 20
            travel_adv = (
                "Waterlogging Advisory: Heavy showers expected. Commuter bottlenecks likely at railway underpasses and low-lying intersections. "
                "Allow 20 minutes buffer time."
            )
        elif peak_prob >= 35.0 or wind_spd >= 30.0:
            delay_buffer = 15
            travel_adv = "Minor Transit Delay: Wet roadways and traffic slowdowns expected. Allow 10-15 minutes extra travel buffer."
        else:
            delay_buffer = 0
            travel_adv = "Normal Commute: Transit corridors and highway speeds operate under clear, routine conditions."

        # Two-wheeler caution for crosswinds
        two_wheeler_caution = (wind_spd >= 25.0)

        rain_risk_info = {
            "departure_probability": round(dep_prob, 1),
            "return_probability": round(ret_prob, 1),
            "peak_probability": round(peak_prob, 1),
            "peak_window": "Evening Return Window" if ret_prob > dep_prob else "Morning Departure Window"
        }

        heat_info = {
            "temperature_c": round(temp_c, 1),
            "heat_stress_level": "extreme" if temp_c >= 40.0 else ("high_heat" if temp_c >= 35.0 else "comfortable"),
            "hydration_advisory": "Carry oral rehydration and drink water frequently during daytime commute." if temp_c >= 34.0 else "Standard hydration."
        }

        wind_info = {
            "speed_kmh": round(wind_spd, 1),
            "two_wheeler_caution": two_wheeler_caution,
            "note": "Exercise caution on flyovers and bridges against crosswind gusts." if two_wheeler_caution else "Winds within comfortable transit limits."
        }

        return CommuterStudentAdvisoryResult(
            departure_time=dep_t,
            return_time=ret_t,
            rain_risk=rain_risk_info,
            heat_conditions=heat_info,
            wind_conditions=wind_info,
            umbrella_recommendation=umbrella_rec,
            umbrella_rationale=umbrella_rationale,
            clothing_advisory=clothing_adv,
            travel_advisory=travel_adv,
            delay_buffer_minutes=delay_buffer,
            route_safety_summary=travel_adv,
        )

    # --------------------------------------------------------------------------
    # E. DISASTER MODE
    # --------------------------------------------------------------------------
    @classmethod
    def evaluate_disaster_mode(
        cls,
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        target_language: LanguageEnum = LanguageEnum.EN
    ) -> DisasterAdvisoryResult:
        """Evaluates emergency disaster preparedness and institutional response status."""
        active_warnings = reasoning.active_warnings or []
        warning_present = len(active_warnings) > 0

        loc_name = "Designated Area"
        if weather and getattr(weather, "location", None) and getattr(weather.location, "name", None):
            loc_name = weather.location.name
        elif active_warnings and active_warnings[0].affected_locations:
            loc_name = active_warnings[0].affected_locations[0]

        severity_str = reasoning.overall_risk.value.lower()
        if warning_present:
            # Map warning severity directly
            top_warn = active_warnings[0]
            severity_str = top_warn.severity.value.lower()

        # Warning summary list
        warn_summaries: List[Dict[str, Any]] = []
        for w in active_warnings:
            warn_summaries.append({
                "title": w.title,
                "severity": w.severity.value,
                "category": w.type,
                "source": w.source,
                "issued_at": w.issued_at.isoformat() if w.issued_at else None,
                "expires_at": w.expires_at.isoformat() if w.expires_at else None,
                "description": w.description,
                "affected_locations": w.affected_locations
            })

        # Action guidance
        action_guidance: List[str] = []
        if severity_str in ("extreme", "high") or warning_present:
            action_guidance.append("Activate standby emergency response protocols across municipal disaster command centers.")
            action_guidance.append("Pre-position heavy dewatering diesel pumps and rescue inflatable boats near recognized flood points.")
            action_guidance.append("Identify safe elevated relief shelters and prepare essential dry rations and drinking water packets.")
            action_guidance.append("Ensure backup emergency power generators at hospitals, water treatment plants, and telecom towers.")
            action_guidance.append("Advise vulnerable populations in kutcha houses or near riverbanks to relocate to storm-resistant community structures.")
        elif severity_str == "medium":
            action_guidance.append("Place civic maintenance teams and water-drain clearing crews on heightened standby.")
            action_guidance.append("Inspect major stormwater outfalls, trash racks, and pumping stations for debris blockage.")
            action_guidance.append("Broadcast public advisory: Avoid walking or driving through moving surface runoff.")
        else:
            action_guidance.append("Maintain routine situational awareness and meteorological telemetry monitoring.")
            action_guidance.append("No active emergency mobilization required for current baseline weather conditions.")

        # Notification status
        push_dispatched = (severity_str in ("extreme", "high") or warning_present)
        notif_status = {
            "push_notification_dispatched": push_dispatched,
            "urgency_level": "CRITICAL" if severity_str == "extreme" else ("HIGH" if severity_str == "high" else "STANDARD"),
            "channels_active": ["FCM_EMERGENCY_BROADCAST", "CIVIC_DASHBOARD_BANNER"] if push_dispatched else ["ROUTINE_POLL"],
            "dispatched_at": datetime.now(timezone.utc).isoformat() if push_dispatched else None
        }

        return DisasterAdvisoryResult(
            active_warning_summary=warn_summaries,
            affected_location=loc_name,
            severity=severity_str,
            action_guidance=action_guidance,
            notification_status=notif_status,
            official_priority_preserved=True,
        )

    # --------------------------------------------------------------------------
    # F. SMART CITY MODE
    # --------------------------------------------------------------------------
    @classmethod
    def evaluate_smart_city_mode(
        cls,
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        target_language: LanguageEnum = LanguageEnum.EN
    ) -> SmartCityAdvisoryResult:
        """Evaluates civic resilience, urban drainage hotspots, heat island, and environmental health."""
        active_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_present = active_warning is not None

        loc_name = "Metropolitan Area"
        if weather and getattr(weather, "location", None) and getattr(weather.location, "name", None):
            loc_name = weather.location.name

        temp_c = float(weather.temperature or 28.0) if weather else 28.0
        rain_prob = float(weather.rain_probability or 0.0) if weather else 0.0
        rain_mm = float(weather.rainfall_amount_mm or 0.0) if weather else 0.0
        wind_spd = float(weather.wind_speed or 0.0) if weather else 0.0

        # Drainage / Waterlogging watch status
        if warning_present or rain_mm >= 30.0 or rain_prob >= 75.0:
            drainage_status = "ALERT"
            drainage_risk = "CRITICAL"
            drainage_desc = "High urban inundation risk. Underpasses and arterial storm drains will face peak overflow capacity."
        elif rain_mm >= 10.0 or rain_prob >= 50.0:
            drainage_status = "WARNING"
            drainage_risk = "HIGH"
            drainage_desc = "Moderate waterlogging expected at known civic pinch points and subway underpasses."
        elif rain_prob >= 30.0:
            drainage_status = "WATCH"
            drainage_risk = "MODERATE"
            drainage_desc = "Localized water accumulation possible on road shoulders. Standard urban runoff."
        else:
            drainage_status = "NORMAL"
            drainage_risk = "LOW"
            drainage_desc = "Dry urban surfaces; municipal stormwater system operating under zero hydrological stress."

        rainfall_summary = {
            "current_rain_prob_pct": round(rain_prob, 1),
            "precipitation_amount_mm": round(rain_mm, 1),
            "waterlogging_risk": drainage_risk,
            "description": drainage_desc
        }

        # Heat Island / Thermal load
        if temp_c >= 40.0:
            heat_island_risk = "CRITICAL"
            heat_desc = "Extreme urban heat island conditions. High surface heat absorption from concrete and asphalt."
        elif temp_c >= 35.0:
            heat_island_risk = "ELEVATED"
            heat_desc = "Elevated urban thermal load. Increased air conditioning grid demand and thermal discomfort."
        else:
            heat_island_risk = "NORMAL"
            heat_desc = "Ambient urban temperature is within comfortable civic operating limits."

        heat_summary = {
            "temperature_c": round(temp_c, 1),
            "urban_heat_island_risk": heat_island_risk,
            "description": heat_desc
        }

        # AQI telemetry: NEVER FABRICATE
        raw_aqi = getattr(weather, "aqi", None) if weather else None
        if raw_aqi is not None:
            aqi_val = int(raw_aqi)
            if aqi_val <= 50:
                cat = "Good"
            elif aqi_val <= 100:
                cat = "Satisfactory"
            elif aqi_val <= 200:
                cat = "Moderate"
            elif aqi_val <= 300:
                cat = "Poor"
            elif aqi_val <= 400:
                cat = "Very Poor"
            else:
                cat = "Severe"

            aqi_summary = {
                "is_available": True,
                "aqi": aqi_val,
                "category": cat,
                "primary_pollutant": getattr(weather, "primary_pollutant", "PM2.5"),
                "health_recommendation": "Acceptable air quality." if aqi_val <= 100 else "Sensitive groups should reduce prolonged outdoor exertion."
            }
        else:
            aqi_summary = {
                "is_available": False,
                "aqi": None,
                "category": None,
                "primary_pollutant": None,
                "note": "Air quality index telemetry currently unavailable for this civic station node. Environmental sensors offline or unconfigured."
            }

        # Severe weather & alert overview
        all_hazards = reasoning.detected_hazards or []
        hazard_types = [h.hazard_type for h in all_hazards]
        severe_info = {
            "active_hazard_count": len(all_hazards),
            "hazard_types": hazard_types,
            "wind_speed_kmh": round(wind_spd, 1),
            "fallen_tree_risk": (wind_spd >= 35.0)
        }

        alert_overview: List[str] = []
        if warning_present:
            alert_overview.append(f"Official Warning: {active_warning.title} ({active_warning.severity.value})")
        for h in all_hazards:
            alert_overview.append(f"Civic Hazard: {h.hazard_type} ({h.severity.value})")

        # Municipal action items
        civic_actions: List[str] = []
        if drainage_status in ("ALERT", "WARNING"):
            civic_actions.append("Deploy mobile dewatering pump sets to designated railway and arterial underpasses.")
            civic_actions.append("Issue traffic police advisories on digital variable message signs for detour routes.")
            civic_actions.append("Dispatch municipal sanitation workers to clear trash and leaf litter from storm drain inlets.")
        if heat_island_risk in ("CRITICAL", "ELEVATED"):
            civic_actions.append("Open municipal air-conditioned cooling centers and public drinking water distribution points.")
            civic_actions.append("Adjust schedule for outdoor municipal sanitation and construction laborers to avoid 12:00-15:00 peak heat.")
        if wind_spd >= 35.0:
            civic_actions.append("Alert civic tree-pruning emergency teams for rapid clearance of fallen branches blocking thoroughfares.")
        if not civic_actions:
            civic_actions.append("Routine municipal infrastructure maintenance and continuous SCADA sensor monitoring.")

        return SmartCityAdvisoryResult(
            location_name=loc_name,
            rainfall_summary=rainfall_summary,
            heat_summary=heat_summary,
            aqi_summary=aqi_summary,
            severe_weather=severe_info,
            alert_overview=alert_overview,
            civic_action_items=civic_actions,
            drainage_watch_status=drainage_status,
        )

    # --------------------------------------------------------------------------
    # Central Evaluation & Multi-lingual Dispatcher
    # --------------------------------------------------------------------------
    @classmethod
    def evaluate_mode(
        cls,
        mode: Union[str, AdvisoryModeEnum, PersonaEnum],
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        target_language: LanguageEnum = LanguageEnum.EN,
        departure_time: Optional[str] = None,
        return_time: Optional[str] = None,
        airport_code: Optional[str] = None
    ) -> SpecializedModeResponse:
        """Unified entrypoint evaluating the requested specialized advisory mode with localized summaries."""
        m_str = str(getattr(mode, "value", mode)).lower().strip()

        active_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_present = active_warning is not None

        loc_name = "Location"
        if weather and getattr(weather, "location", None) and getattr(weather.location, "name", None):
            loc_name = weather.location.name
        elif active_warning and active_warning.affected_locations:
            loc_name = active_warning.affected_locations[0]

        timestamp_str = f"Updated {reasoning.data_age_minutes}m ago ({reasoning.freshness.value})"
        source_str = f"Source: {', '.join(reasoning.sources_used) if reasoning.sources_used else 'SkyZen Verified Ingestion'}"

        # 1. Dispatch Mode
        if m_str in ("farmer", "agriculture", "agri"):
            mode_key = "farmer"
            farmer_res = cls.evaluate_farmer_mode(reasoning, weather, forecast, target_language)
            details = farmer_res.model_dump()
            disclaimer = farmer_res.disclaimer
            key_precautions = farmer_res.weather_sensitive_planning[:4]
            headline = f"Agricultural Advisory for {loc_name}"
            concise_en = f"Farmer Advisory ({loc_name}): {farmer_res.irrigation_guidance}"
            concise_ta = f"விவசாய ஆலோசனை ({loc_name}): {farmer_res.rainfall_advisory} பாசன ஆலோசனை: {farmer_res.irrigation_timing}."
            concise_hi = f"कृषि सलाह ({loc_name}): {farmer_res.rainfall_advisory} सिंचाई सलाह: {farmer_res.irrigation_guidance}"
            concise_mr = f"शेतकरी सल्ला ({loc_name}): {farmer_res.rainfall_advisory} जलव्यवस्थापन सल्ला: {farmer_res.irrigation_guidance}"
            concise_te = f"వ్యవసాయ సలహా ({loc_name}): {farmer_res.rainfall_advisory} నీటిపారుదల సలహా: {farmer_res.irrigation_guidance}"

        elif m_str in ("fisherman", "marine", "fisher", "sea"):
            mode_key = "fisherman"
            marine_res = cls.evaluate_marine_mode(reasoning, weather, forecast, target_language)
            details = marine_res.model_dump()
            disclaimer = marine_res.disclaimer
            key_precautions = [marine_res.departure_advisory]
            if marine_res.has_official_warning:
                key_precautions.extend(marine_res.official_marine_warnings)
            headline = f"Marine Weather Advisory — Verdict: {marine_res.departure_verdict}"
            concise_en = f"Marine Advisory: {marine_res.departure_verdict} — {marine_res.departure_advisory}"
            concise_ta = f"கடல் வானிலை ஆலோசனை: முடிவு {marine_res.departure_verdict}. {marine_res.departure_advisory}"
            concise_hi = f"समुद्री मौसम सलाह: निर्णय {marine_res.departure_verdict}। {marine_res.departure_advisory}"
            concise_mr = f"सागरी हवामान सल्ला: निर्णय {marine_res.departure_verdict}. {marine_res.departure_advisory}"
            concise_te = f"సముద్ర వాతావరణ సలహా: నిర్ణయం {marine_res.departure_verdict}. {marine_res.departure_advisory}"

        elif m_str in ("aviation", "airport", "pilot", "flight"):
            mode_key = "aviation"
            aviation_res = cls.evaluate_aviation_mode(reasoning, weather, forecast, airport_code, target_language)
            details = aviation_res.model_dump()
            disclaimer = aviation_res.disclaimer
            key_precautions = aviation_res.weather_hazards[:4] or ["Standard flight watch in effect"]
            headline = f"Aviation Advisory ({aviation_res.airport_or_location}) — {aviation_res.flight_category_indicator}"
            concise_en = f"Aviation Advisory ({aviation_res.airport_or_location}): {aviation_res.advisory_summary}"
            concise_ta = f"விமான வானிலை ஆலோசனை ({aviation_res.airport_or_location}): {aviation_res.advisory_summary}"
            concise_hi = f"विमानन मौसम सलाह ({aviation_res.airport_or_location}): {aviation_res.advisory_summary}"
            concise_mr = f"विमान वाहतूक हवामान सल्ला ({aviation_res.airport_or_location}): {aviation_res.advisory_summary}"
            concise_te = f"విమానయాన వాతావరణ సలహా ({aviation_res.airport_or_location}): {aviation_res.advisory_summary}"

        elif m_str in ("commuter", "student", "transit"):
            mode_key = "commuter"
            commuter_res = cls.evaluate_commuter_student_mode(reasoning, weather, forecast, departure_time, return_time, target_language)
            details = commuter_res.model_dump()
            disclaimer = "Advisory interface for transit safety and commuter planning."
            key_precautions = [commuter_res.umbrella_rationale, commuter_res.clothing_advisory, commuter_res.travel_advisory]
            headline = f"Commuter & Student Advisory for {loc_name}"
            concise_en = f"Commuter Advisory: {commuter_res.travel_advisory} Umbrella: {'Yes' if commuter_res.umbrella_recommendation else 'No'}."
            concise_ta = f"பயணிகள் ஆலோசனை: {commuter_res.travel_advisory} குடை தேவை: {'ஆம்' if commuter_res.umbrella_recommendation else 'இல்லை'}."
            concise_hi = f"यात्री व छात्र सलाह: {commuter_res.travel_advisory} छाते की आवश्यकता: {'हाँ' if commuter_res.umbrella_recommendation else 'नहीं'}।"
            concise_mr = f"प्रवासी सल्ला: {commuter_res.travel_advisory} छत्री आवश्यक: {'होय' if commuter_res.umbrella_recommendation else 'नाही'}."
            concise_te = f"ప్రయాణికుల సలహా: {commuter_res.travel_advisory} గొడుగు అవసరం: {'అవును' if commuter_res.umbrella_recommendation else 'కాదు'}."

        elif m_str in ("disaster", "disaster_response", "emergency", "safety"):
            mode_key = "disaster"
            disaster_res = cls.evaluate_disaster_mode(reasoning, weather, forecast, target_language)
            details = disaster_res.model_dump()
            disclaimer = "Emergency management advisory synthesized from authoritative bulletins and sensor telemetry."
            key_precautions = disaster_res.action_guidance[:4]
            headline = f"Disaster Response Advisory — Severity: {disaster_res.severity.upper()}"
            concise_en = f"Disaster Response Advisory ({loc_name}): Severity {disaster_res.severity.upper()}. {'; '.join(disaster_res.action_guidance[:2])}"
            concise_ta = f"பேரிடர் மேலாண்மை ஆலோசனை ({loc_name}): தீவிரம் {disaster_res.severity.upper()}. அதிகாரப்பூர்வ வழிகாட்டுதலைப் பின்பற்றவும்."
            concise_hi = f"आपदा प्रबंधन सलाह ({loc_name}): गंभीरता {disaster_res.severity.upper()}। आपातकालीन दिशा-निर्देशों का पालन करें।"
            concise_mr = f"आपत्ती व्यवस्थापन सल्ला ({loc_name}): तीव्रता {disaster_res.severity.upper()}. अधिकृत सूचनांचे पालन करा."
            concise_te = f"విపత్తు నిర్వహణ సలహా ({loc_name}): తీవ్రత {disaster_res.severity.upper()}. అధికారిక ఆదేశాలను పాటించండి."

        elif m_str in ("smart_city", "smartcity", "civic", "urban"):
            mode_key = "smart_city"
            city_res = cls.evaluate_smart_city_mode(reasoning, weather, forecast, target_language)
            details = city_res.model_dump()
            disclaimer = "Municipal civic resilience advisory based on real-time meteorological observations."
            key_precautions = city_res.civic_action_items[:4]
            headline = f"Smart City Resilience Advisory for {city_res.location_name} — Drainage: {city_res.drainage_watch_status}"
            concise_en = f"Smart City Advisory ({city_res.location_name}): Drainage Status {city_res.drainage_watch_status}. {city_res.rainfall_summary['description']}"
            concise_ta = f"ஸ்மார்ட் சிட்டி ஆலோசனை ({city_res.location_name}): வடிகால் நிலை {city_res.drainage_watch_status}. {city_res.rainfall_summary['description']}"
            concise_hi = f"स्मार्ट सिटी सलाह ({city_res.location_name}): जल निकासी स्थिति {city_res.drainage_watch_status}। {city_res.rainfall_summary['description']}"
            concise_mr = f"स्मार्ट सिटी सल्ला ({city_res.location_name}): ड्रेनेज स्थिती {city_res.drainage_watch_status}. {city_res.rainfall_summary['description']}"
            concise_te = f"స్మార్ట్ సిటీ సలహా ({city_res.location_name}): డ్రైనేజ్ స్థితి {city_res.drainage_watch_status}. {city_res.rainfall_summary['description']}"

        else:
            # Fallback to general mode
            mode_key = "general"
            details = {"mode": "general", "status": "standard_evaluation"}
            disclaimer = "General weather advisory based on verified observation telemetry."
            key_precautions = ["Monitor official local weather updates", "Standard precautions apply"]
            headline = f"Weather Advisory for {loc_name}"
            concise_en = f"Weather for {loc_name}: Risk {reasoning.overall_risk.value}."
            concise_ta = f"வானிலை அறிக்கை ({loc_name}): ஆபத்து நிலை {reasoning.overall_risk.value}."
            concise_hi = f"मौसम सलाह ({loc_name}): जोखिम स्तर {reasoning.overall_risk.value}।"
            concise_mr = f"हवामान सल्ला ({loc_name}): जोखीम स्तर {reasoning.overall_risk.value}."
            concise_te = f"వాతావరణ సలహా ({loc_name}): ప్రమాద స్థాయి {reasoning.overall_risk.value}."

        # Select target localized answer
        localized_map = {
            "en": concise_en,
            "ta": concise_ta,
            "hi": concise_hi,
            "mr": concise_mr,
            "te": concise_te
        }

        lang_val = target_language.value if hasattr(target_language, "value") else str(target_language).lower()
        if lang_val in ("ta", "tanglish"):
            selected_answer = concise_ta
        elif lang_val in ("hi", "hinglish"):
            selected_answer = concise_hi
        elif lang_val in ("mr", "marathi"):
            selected_answer = concise_mr
        elif lang_val in ("te", "telugu"):
            selected_answer = concise_te
        else:
            selected_answer = concise_en

        # Determine priority
        if warning_present:
            priority = AdvisoryPriorityEnum.CRITICAL if active_warning.severity in (RiskLevelEnum.EXTREME, RiskLevelEnum.HIGH) else AdvisoryPriorityEnum.HIGH
        elif reasoning.overall_risk == RiskLevelEnum.EXTREME:
            priority = AdvisoryPriorityEnum.CRITICAL
        elif reasoning.overall_risk == RiskLevelEnum.HIGH:
            priority = AdvisoryPriorityEnum.HIGH
        elif reasoning.overall_risk == RiskLevelEnum.MEDIUM:
            priority = AdvisoryPriorityEnum.MEDIUM
        else:
            priority = AdvisoryPriorityEnum.LOW

        return SpecializedModeResponse(
            mode=mode_key,
            location=loc_name,
            risk_level=reasoning.overall_risk,
            priority=priority,
            headline=headline,
            concise_answer=selected_answer,
            localized_answers=localized_map,
            key_precautions=key_precautions,
            official_warning_present=warning_present,
            official_warning_title=active_warning.title if active_warning else None,
            source_attribution=source_str,
            timestamp_info=timestamp_str,
            details=details,
            disclaimer=disclaimer,
        )
