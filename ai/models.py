"""WeatherGPT — Core AI & Meteorological Data Models

Strictly defines schemas for NLU, Weather Observations, Forecasts,
Official IMD Alerts, Reasoning Results, and Persona Decision Advisories.
Aligned with docs/08_Api_Contracts.md and docs/09_AI_Design.md.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PersonaEnum(str, Enum):
    GENERAL = "general"
    GENERAL_USER = "general"
    STUDENT = "student"
    FARMER = "farmer"
    FISHERMAN = "fisherman"
    TRAVELLER = "traveller"
    TRAVELER = "traveller"
    COMMUTER = "commuter"
    DISASTER_RESPONSE = "disaster_response"


class AdvisoryTypeEnum(str, Enum):
    WEATHER_SUMMARY = "weather_summary"
    RAIN_CAUTION = "rain_caution"
    EXTREME_RAIN_ALERT = "extreme_rain_alert"
    WIND_CAUTION = "wind_caution"
    HEAT_CAUTION = "heat_caution"
    COLD_CAUTION = "cold_caution"
    THUNDERSTORM_CAUTION = "thunderstorm_caution"
    VISIBILITY_CAUTION = "visibility_caution"
    TRAVEL_CAUTION = "travel_caution"
    OUTDOOR_ACTIVITY_CAUTION = "outdoor_activity_caution"
    FARM_ACTIVITY_CAUTION = "farm_activity_caution"
    FISHING_CAUTION = "fishing_caution"
    OFFICIAL_WARNING = "official_warning"
    DATA_UNAVAILABLE = "data_unavailable"


class AdvisoryPriorityEnum(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimeContextEnum(str, Enum):
    NOW = "now"
    NEXT_FEW_HOURS = "next_few_hours"
    TODAY = "today"
    TOMORROW = "tomorrow"
    LATER = "later"


class LanguageEnum(str, Enum):
    EN = "en"
    TA = "ta"
    TANGLISH = "tanglish"
    HI = "hi"
    HINGLISH = "hinglish"
    UNKNOWN = "unknown"


class IntentEnum(str, Enum):
    CURRENT_WEATHER = "current_weather"
    FORECAST = "forecast"
    RAIN_FORECAST = "rain_forecast"
    TEMPERATURE = "temperature"
    WIND = "wind"
    HUMIDITY = "humidity"
    WEATHER_ALERT = "weather_alert"
    TRAVEL_ADVISORY = "travel_advisory"
    OUTDOOR_DECISION = "outdoor_decision"
    AGRICULTURE_ADVISORY = "agriculture_advisory"
    HISTORICAL_WEATHER = "historical_weather"
    CLIMATE_TREND = "climate_trend"
    LOCATION_WEATHER = "location_weather"
    FORECAST_COMPARISON = "forecast_comparison"
    WEATHER_EXPLANATION = "weather_explanation"
    CYCLONE_INQUIRY = "cyclone_inquiry"
    GENERAL_WEATHER_QUESTION = "general_weather_question"


class RiskLevelEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"
    CRITICAL = "extreme"


class FreshnessStatusEnum(str, Enum):
    FRESH = "fresh"          # < 60 mins
    ACCEPTABLE = "acceptable" # 60 - 180 mins
    STALE = "stale"          # > 180 mins


class SourceAgreementEnum(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    MEDIUM = "moderate"  # Phase 9 alias
    LOW = "low"
    SINGLE_SOURCE = "single_source"


class ConfidenceLevelEnum(str, Enum):
    """Application-level data confidence indicator levels (Phase 9)."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ForecastConsistencyFactors(BaseModel):
    """Deterministic breakdown of consistency factors across NWP / forecast sources."""
    rainfall_agreement: str = Field(description="Precipitation agreement status")
    temperature_agreement: str = Field(description="Thermal agreement status")
    wind_agreement: str = Field(description="Wind speed agreement status")
    timing_agreement: Optional[str] = Field(default=None, description="Precipitation or hazard onset timing agreement")
    source_freshness: str = Field(description="Observation or forecast model cycle freshness")
    completeness: str = Field(description="Data telemetry completeness status")
    contradictions: List[str] = Field(default_factory=list, description="Explicit discrepancies identified")
    summary: Optional[str] = Field(default=None, description="Deterministic summary explanation")


class WeatherDataType(str, Enum):
    HISTORICAL = "HISTORICAL"
    CURRENT = "CURRENT"
    FORECAST = "FORECAST"
    OFFICIAL_WARNING = "OFFICIAL_WARNING"


class LocationInfo(BaseModel):
    name: str
    latitude: float
    longitude: float
    district: Optional[str] = None
    state: Optional[str] = None


class WeatherRecord(BaseModel):
    """Normalized observation schema (docs/06_Data_sources.md)."""
    data_type: WeatherDataType = WeatherDataType.CURRENT
    location: LocationInfo
    observed_at: datetime
    retrieved_at: datetime
    temperature: float = Field(description="Temperature in Celsius")
    humidity: float = Field(description="Relative humidity in percentage")
    rain_probability: float = Field(description="Precipitation probability 0-100%")
    wind_speed: float = Field(description="Wind speed in km/h")
    weather_condition: str = Field(description="e.g. Rain, Thunderstorm, Sunny, Cloudy")
    source: str = Field(default="IMD", description="Data source name e.g. IMD, Open-Meteo")
    rainfall_amount_mm: Optional[float] = Field(default=0.0, description="Observed/expected rainfall in mm")


class ForecastItem(BaseModel):
    data_type: WeatherDataType = WeatherDataType.FORECAST
    time: str
    temperature: float
    rain_probability: float
    wind_speed: float
    condition: str
    rainfall_amount_mm: Optional[float] = 0.0


class OfficialAlert(BaseModel):
    """Official severe weather warning (docs/08_Api_Contracts.md)."""
    data_type: WeatherDataType = WeatherDataType.OFFICIAL_WARNING
    id: Optional[str] = Field(default=None, description="Authoritative warning identifier / CAP identifier")
    type: str = Field(description="e.g. heavy_rain, cyclone, thunderstorm, heatwave")
    severity: RiskLevelEnum = Field(description="low, medium, high, extreme")
    title: str
    description: str
    instructions: Optional[str] = Field(default=None, description="Civil defense emergency instructions")
    source: str = Field(default="IMD")
    source_url: Optional[str] = Field(default=None, description="Official meteorological bulletin reference URL")
    issued_at: datetime
    expires_at: datetime
    valid_from: Optional[datetime] = None
    status: str = Field(default="ACTIVE", description="ACTIVE, SCHEDULED, EXPIRED, CANCELLED")
    version: int = Field(default=1, description="Update sequence version number")
    affected_locations: List[str] = Field(default_factory=list)


class HistoricalWeatherDataset(BaseModel):
    """Normalized historical weather dataset and climate reference for a location."""
    data_type: WeatherDataType = WeatherDataType.HISTORICAL
    location: LocationInfo
    start_date: str
    end_date: str
    record_count: int = 0
    average_temperature_c: Optional[float] = None
    min_temperature_c: Optional[float] = None
    max_temperature_c: Optional[float] = None
    total_rainfall_mm: Optional[float] = None
    average_annual_rainfall_mm: Optional[float] = None
    max_single_day_rainfall_mm: Optional[float] = None
    hottest_month: Optional[str] = None
    wettest_month: Optional[str] = None
    weather_patterns: List[str] = Field(default_factory=list)
    recurring_hazards: List[str] = Field(default_factory=list)
    seasonal_normals: Dict[str, Any] = Field(default_factory=dict)
    records: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = Field(default="NASA POWER / IMD Historical Archive")
    primary_source: Optional[str] = Field(default="IMD Archive / NASA POWER")
    data_quality: Optional[str] = Field(default="verified_archive")
    safety_disclaimer: Optional[str] = Field(
        default="Historical records reflect past meteorological observations and climate baselines. "
                "They do not represent active forecasts or warnings."
    )
    rainfall_normal_mm: Optional[float] = None
    temp_normal_c: Optional[float] = None
    retrieved_at: Optional[datetime] = None
    is_available: bool = True
    unavailability_reason: Optional[str] = None

    @property
    def avg_temperature_c(self) -> Optional[float]:
        return self.average_temperature_c


class ExtractedEntities(BaseModel):
    location: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    time_range: Optional[str] = None
    weather_variable: Optional[str] = None
    hazard: Optional[str] = None
    persona: Optional[PersonaEnum] = None
    activity: Optional[str] = None
    departure_time: Optional[str] = None
    return_time: Optional[str] = None


class NLUResult(BaseModel):
    original_text: str
    normalized_text: Optional[str] = None
    detected_language: LanguageEnum
    intent: IntentEnum
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    ambiguity: Optional[str] = None


class HazardDetection(BaseModel):
    hazard_type: str
    detected: bool = True
    severity: RiskLevelEnum
    details: str
    evidence: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    is_official_warning: bool = False
    current_or_forecast: str = Field(default="current", description="'current', 'forecast', or 'both'")
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


class WeatherReasoningResult(BaseModel):
    """Output of the Weather Reasoner engine."""
    evaluated_at: datetime
    location: str
    freshness: FreshnessStatusEnum
    data_age_minutes: int
    data_complete: bool = True
    missing_fields: List[str] = Field(default_factory=list)
    source_agreement: SourceAgreementEnum
    consistency_score: int = Field(ge=0, le=100, description="0-100 composite indicator")
    confidence_level: ConfidenceLevelEnum = ConfidenceLevelEnum.HIGH
    confidence_indicator: str = "High"
    consistency_factors: Optional[Dict[str, Any]] = None
    contradictions: List[str] = Field(default_factory=list)
    active_warnings: List[OfficialAlert] = Field(default_factory=list)
    detected_hazards: List[HazardDetection] = Field(default_factory=list)
    ai_detected_hazards: List[HazardDetection] = Field(default_factory=list)
    overall_risk: RiskLevelEnum
    uncertainty_note: Optional[str] = None
    sources_used: List[str] = Field(default_factory=list)


class DecisionAdvisory(BaseModel):
    """Persona-tailored actionable recommendation."""
    persona: PersonaEnum
    risk_level: RiskLevelEnum
    headline: str
    advisory_text: str
    key_precautions: List[str]
    official_warning_present: bool
    official_warning_title: Optional[str] = None
    source_attribution: str
    timestamp_info: str

    # Phase 7 Structured Decision Fields
    advisory_type: AdvisoryTypeEnum = AdvisoryTypeEnum.WEATHER_SUMMARY
    priority: AdvisoryPriorityEnum = AdvisoryPriorityEnum.LOW
    time_context: TimeContextEnum = TimeContextEnum.TODAY
    reason_codes: List[str] = Field(default_factory=list)
    risk_summary: str = ""
    action_guidance: List[str] = Field(default_factory=list)
    source_basis: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    schedule_decision: Optional[Dict[str, Any]] = None
    language: LanguageEnum = LanguageEnum.EN


class ValidationStatusEnum(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNING = "PASS_WITH_WARNING"
    REJECT = "REJECT"
    FALLBACK = "FALLBACK"


class ValidationCategoryEnum(str, Enum):
    UNSUPPORTED_NUMBER = "UNSUPPORTED_NUMBER"
    UNSUPPORTED_LOCATION = "UNSUPPORTED_LOCATION"
    UNSUPPORTED_TIME = "UNSUPPORTED_TIME"
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"
    UNSUPPORTED_HAZARD = "UNSUPPORTED_HAZARD"
    SEVERITY_DOWNGRADE = "SEVERITY_DOWNGRADE"
    WARNING_CONTRADICTION = "WARNING_CONTRADICTION"
    MISSING_WARNING = "MISSING_WARNING"
    FABRICATED_DATA = "FABRICATED_DATA"
    FABRICATED_ACTION = "FABRICATED_ACTION"
    FALSE_CERTAINTY = "FALSE_CERTAINTY"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    LANGUAGE_MISMATCH = "LANGUAGE_MISMATCH"
    UNAUTHORIZED_DECLARATION = "UNAUTHORIZED_DECLARATION"


class ValidationResult(BaseModel):
    is_valid: bool
    hallucination_detected: bool = False
    warning_consistency_passed: bool = True
    issues: List[str] = Field(default_factory=list)
    verified_claims: List[str] = Field(default_factory=list)

    # Phase 9 Unified Safety Gate Fields
    status: ValidationStatusEnum = ValidationStatusEnum.PASS
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    checked_fields: List[str] = Field(default_factory=list)
    fallback_required: bool = False
    violation_categories: List[str] = Field(default_factory=list)


class GroundedResponse(BaseModel):
    """Structured output contract for grounded LLM responses per Phase 5 spec."""
    answer: str
    grounded_facts: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    used_grounded_context: bool = True
    is_fallback: bool = False


class DegradedStateEnum(str, Enum):
    """Structured system degradation states (Phase 16)."""
    NORMAL = "NORMAL"
    DEGRADED_LLM = "DEGRADED_LLM"
    DEGRADED_RAG = "DEGRADED_RAG"
    DEGRADED_VOICE = "DEGRADED_VOICE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    SAFETY_FALLBACK = "SAFETY_FALLBACK"


class DegradationTelemetry(BaseModel):
    """Structured telemetry on subsystem degradation without exposing internals to users."""
    state: DegradedStateEnum = DegradedStateEnum.NORMAL
    reasons: List[str] = Field(default_factory=list)
    circuit_breaker_open: bool = False
    subsystems_degraded: List[str] = Field(default_factory=list)


class EvidenceLink(BaseModel):
    """Machine-readable evidence reference linking AI decisions directly to observations or rules (Phase 19)."""
    field_or_entity: str = Field(description="e.g. weather.temperature, warning.cyclone, hazard_rule.wind")
    observed_or_rule_value: Any = Field(description="Observed value, forecast value, or threshold")
    source: str = Field(default="IMD", description="Meteorological source or authority")
    temporal_scope: str = Field(default="current", description="Time window: current, today, tomorrow, forecast")
    decision_impact: str = Field(description="How this evidence shaped the advisory or hazard")
    timestamp: Optional[str] = Field(default=None, description="Observation or bulletin timestamp")
    reason_code: Optional[str] = Field(default=None, description="Reason code or rule identifier")
    reference_type: str = Field(default="observation", description="observation, forecast, alert, hazard_rule, advisory_rule")


class DecisionTrace(BaseModel):
    """Explainable, auditable internal decision trace showing WHY a response was generated.
    
    Exposes concise structured evidence and deterministic logic without exposing hidden LLM chain-of-thought.
    """
    trace_id: str
    evaluated_at: datetime
    query_summary: str
    resolved_location: str
    resolved_time_window: str
    detected_intent: str
    persona: str
    language: str
    data_freshness: str
    data_completeness: bool
    source_agreement: str
    consistency_score: Optional[int] = 0
    official_warning_status: str
    official_warning_details: Optional[Dict[str, Any]] = None
    warning_count: int = 0
    hazards_detected: List[Dict[str, Any]] = Field(default_factory=list)
    overall_risk: str = "low"
    advisory_category: str
    advisory_priority: str = "normal"
    advisory_action_class: str
    evidence_basis: List[str] = Field(default_factory=list)
    evidence_links: List[EvidenceLink] = Field(default_factory=list)
    validation_status: str
    violation_category: Optional[str] = None
    fallback_used: bool
    degraded_state: str
    degraded_subsystems: List[str] = Field(default_factory=list)
    degradation_reason: Optional[str] = None
    stage_latencies_ms: Dict[str, float] = Field(default_factory=dict)
    final_response_status: str

    # Phase 6 Explainability & System Factor Fields
    request: Optional[str] = None
    location: Optional[str] = None
    forecast_period: Optional[str] = None
    confidence_score: Optional[int] = None
    confidence_indicator: str = "High"
    rainfall_indicators: Optional[Dict[str, Any]] = None
    temperature: Optional[Dict[str, Any]] = None
    wind: Optional[Dict[str, Any]] = None
    hazard_signals: List[Dict[str, Any]] = Field(default_factory=list)
    official_warnings: List[Dict[str, Any]] = Field(default_factory=list)
    persona_context: Dict[str, Any] = Field(default_factory=dict)
    final_recommendation: Optional[str] = None
    explanation_points: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    confidence_level: Optional[str] = "HIGH"
    consistency_factors: Optional[Dict[str, Any]] = None
    historical_context: Optional[Dict[str, Any]] = None
    data_types_used: List[str] = Field(default_factory=list)

    def to_debug_dict(self) -> Dict[str, Any]:
        """Controlled debug dictionary for developer testing, SIH demo, and evaluators."""
        eff_req = self.request or self.query_summary
        eff_loc = self.location or self.resolved_location
        eff_period = self.forecast_period or self.resolved_time_window
        eff_score = self.confidence_score if self.confidence_score is not None else self.consistency_score

        return {
            "trace_id": self.trace_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "query": self.query_summary,
            "request": eff_req,
            "location": eff_loc,
            "resolved_location": self.resolved_location,
            "time_window": self.resolved_time_window,
            "resolved_time_window": self.resolved_time_window,
            "forecast_period": eff_period,
            "intent": self.detected_intent,
            "detected_intent": self.detected_intent,
            "persona": self.persona,
            "language": self.language,
            "data_freshness": self.data_freshness,
            "data_completeness": self.data_completeness,
            "source_agreement": self.source_agreement,
            "consistency_score": eff_score,
            "confidence_score": eff_score,
            "confidence_indicator": self.confidence_indicator,
            "warning_status": self.official_warning_status,
            "official_warning_status": self.official_warning_status,
            "warning_count": self.warning_count,
            "warning_details": self.official_warning_details,
            "official_warnings": self.official_warnings,
            "hazards_count": len(self.hazards_detected),
            "hazards": self.hazards_detected,
            "hazard_signals": self.hazard_signals or self.hazards_detected,
            "rainfall_indicators": self.rainfall_indicators,
            "temperature": self.temperature,
            "wind": self.wind,
            "overall_risk": self.overall_risk,
            "advisory_category": self.advisory_category,
            "advisory_priority": self.advisory_priority,
            "action_class": self.advisory_action_class,
            "advisory_action_class": self.advisory_action_class,
            "persona_context": self.persona_context,
            "final_recommendation": self.final_recommendation,
            "explanation_points": self.explanation_points,
            "sources": self.sources,
            "validation_status": self.validation_status,
            "violation_category": self.violation_category,
            "fallback_used": self.fallback_used,
            "degraded_state": self.degraded_state,
            "degraded_subsystems": self.degraded_subsystems,
            "degradation_reason": self.degradation_reason,
            "stage_latencies_ms": self.stage_latencies_ms,
            "final_status": self.final_response_status,
            "final_response_status": self.final_response_status,
            "evidence_links_count": len(self.evidence_links),
            "evidence_links": [link.model_dump() for link in self.evidence_links],
            "historical_context": self.historical_context,
            "data_types_used": self.data_types_used,
            "confidence_level": self.confidence_level,
            "consistency_factors": self.consistency_factors,
        }

    def to_explanation_dict(self) -> Dict[str, Any]:
        """Clean explainability representation for frontend cards and API responses.

        Zero hidden chain-of-thought; structured system factors only.
        """
        eff_score = self.confidence_score if self.confidence_score is not None else self.consistency_score
        return {
            "trace_id": self.trace_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "request": self.request or self.query_summary,
            "location": self.location or self.resolved_location,
            "forecast_period": self.forecast_period or self.resolved_time_window,
            "data_freshness": self.data_freshness,
            "data_completeness": self.data_completeness,
            "source_agreement": self.source_agreement,
            "consistency_score": eff_score,
            "confidence_score": eff_score,
            "confidence_indicator": self.confidence_indicator,
            "warning_status": self.official_warning_status,
            "official_warnings": self.official_warnings,
            "hazard_signals": self.hazard_signals or self.hazards_detected,
            "overall_risk": self.overall_risk,
            "rainfall_indicators": self.rainfall_indicators,
            "temperature": self.temperature,
            "wind": self.wind,
            "persona_context": self.persona_context,
            "final_recommendation": self.final_recommendation,
            "explanation_points": self.explanation_points,
            "sources": self.sources,
            "evidence_links": [link.model_dump() for link in self.evidence_links],
            "historical_context": self.historical_context,
            "data_types_used": self.data_types_used,
            "confidence_level": self.confidence_level,
            "consistency_factors": self.consistency_factors,
        }
