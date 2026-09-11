"""Decision-Oriented Personal Weather AI Models for SkyZen.

Defines structured decision types, verdicts, evidence models, and results
for deterministic personal weather guidance.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ai.models import RiskLevelEnum, LanguageEnum


class DecisionTypeEnum(str, Enum):
    COLLEGE_COMMUTE = "college_commute"
    GENERAL_TRAVEL = "general_travel"
    BIKE_TRAVEL = "bike_travel"
    UMBRELLA = "umbrella"
    OUTDOOR_ACTIVITY = "outdoor_activity"
    SPORTS = "sports"
    FISHING_MARINE = "fishing_marine"
    CLOTHING = "clothing"
    GENERAL_GO = "general_go"


class DecisionVerdictEnum(str, Enum):
    GO = "GO"
    CAUTION = "CAUTION"
    NO_GO = "NO_GO"
    RECOMMENDED = "RECOMMENDED"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"


class StructuredEvidence(BaseModel):
    """Verified meteorological and safety evidence backing a decision."""
    temperature_c: Optional[float] = None
    rain_probability: float = 0.0
    rainfall_mm: float = 0.0
    wind_speed_kmh: float = 0.0
    weather_condition: str = "Clear"
    humidity: Optional[float] = None
    visibility_km: Optional[float] = None
    is_rain_expected: bool = False
    data_freshness: str = "fresh"
    data_age_minutes: int = 0
    is_stale: bool = False
    data_available: bool = True
    warnings_available: bool = True
    forecast_period: Optional[str] = None
    active_warnings: List[str] = Field(default_factory=list)
    hazards_detected: List[str] = Field(default_factory=list)
    transit_departure_prob: Optional[float] = None
    transit_return_prob: Optional[float] = None
    transit_departure_time: Optional[str] = None
    transit_return_time: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)


class PersonalDecisionResult(BaseModel):
    """Structured decision output containing evidence and recommended actions."""
    decision_type: DecisionTypeEnum
    verdict: DecisionVerdictEnum
    recommended_action: str
    primary_factor: str
    risk_level: RiskLevelEnum = RiskLevelEnum.LOW
    confidence: str = "HIGH"
    location: str = "Unknown"
    time_window: str = "today"
    evidence: StructuredEvidence = Field(default_factory=StructuredEvidence)
    precautions: List[str] = Field(default_factory=list)
    concise_answer_en: str = ""
    concise_answer_ta: str = ""
    concise_answer_hi: str = ""

    def get_concise_answer(self, language: LanguageEnum = LanguageEnum.EN) -> str:
        """Returns concise direct answer in the requested language."""
        if language in (LanguageEnum.TA, LanguageEnum.TANGLISH):
            return self.concise_answer_ta or self.concise_answer_en
        if language in (LanguageEnum.HI, LanguageEnum.HINGLISH):
            return self.concise_answer_hi or self.concise_answer_en
        return self.concise_answer_en or self.recommended_action

    def to_dict(self) -> Dict[str, Any]:
        """Serializes decision result to a dictionary for pipeline and API payloads."""
        return {
            "decision_type": self.decision_type.value,
            "verdict": self.verdict.value,
            "recommended_action": self.recommended_action,
            "primary_factor": self.primary_factor,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
            "location": self.location,
            "time_window": self.time_window,
            "evidence": self.evidence.model_dump(),
            "precautions": self.precautions,
            "concise_answer": self.concise_answer_en,
            "concise_answer_ta": self.concise_answer_ta,
            "concise_answer_hi": self.concise_answer_hi,
        }
