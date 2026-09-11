"""Automated Test Suite for SkyZen Decision-Oriented Personal Weather Engine.

Tests each structured decision type:
1. College Commute
2. General Travel
3. Bike Travel
4. Umbrella Decision
5. Outdoor Activity
6. Sports Activity
7. Fishing / Marine Safety
8. Clothing Advice
9. General "Can I go?" Decisions
10. Multilingual Decision Direct Answers (English, Tamil, Hindi)
11. AI Pipeline Integration & Structured Payload
"""

from datetime import datetime, timezone
import pytest

from ai.decision import (
    PersonalDecisionEngine,
    DecisionTypeEnum,
    DecisionVerdictEnum,
    PersonalDecisionResult,
)
from ai.models import (
    HazardDetection,
    LanguageEnum,
    NLUResult,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    SourceAgreementEnum,
    WeatherReasoningResult,
    WeatherRecord,
    ForecastItem,
    ExtractedEntities,
)
from ai.nlu import parse_query
from ai.pipeline import WeatherGPTPipeline


# Helper to build mock Reasoning
def create_reasoning(
    risk: RiskLevelEnum = RiskLevelEnum.LOW,
    warnings: list = None,
    hazards: list = None,
    location: str = "Coimbatore"
) -> WeatherReasoningResult:
    from ai.models import FreshnessStatusEnum
    return WeatherReasoningResult(
        evaluated_at=datetime.now(timezone.utc),
        location=location,
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=5,
        data_complete=True,
        missing_fields=[],
        source_agreement=SourceAgreementEnum.HIGH,
        consistency_score=90.0,
        consistency_factors={},
        detected_hazards=hazards or [],
        ai_detected_hazards=[],
        overall_risk=risk,
        active_warnings=warnings or [],
        sources_used=["IMD"],
    )


# Helper to build mock WeatherRecord
def create_weather(
    temp: float = 28.0,
    rain_prob: float = 10.0,
    wind: float = 12.0,
    cond: str = "Clear",
    rain_mm: float = 0.0,
    loc: str = "Coimbatore"
) -> WeatherRecord:
    from ai.models import LocationInfo
    return WeatherRecord(
        location=LocationInfo(name=loc, latitude=11.0168, longitude=76.9558),
        observed_at=datetime.now(timezone.utc),
        retrieved_at=datetime.now(timezone.utc),
        temperature=temp,
        humidity=65.0,
        rain_probability=rain_prob,
        wind_speed=wind,
        weather_condition=cond,
        source="IMD",
        rainfall_amount_mm=rain_mm,
    )


class TestPersonalDecisions:
    """Validates deterministic decision rules and structured evidence across all decision types."""

    # -------------------------------------------------------------------------
    # 1. COLLEGE COMMUTE
    # -------------------------------------------------------------------------
    def test_01_college_commute_clear(self):
        nlu = parse_query("Can I go to college today?")
        weather = create_weather(rain_prob=10.0, cond="Clear")
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.COLLEGE_COMMUTE
        assert res.verdict == DecisionVerdictEnum.GO
        assert "clear and safe" in res.recommended_action.lower()
        assert "yes" in res.concise_answer_en.lower()

    def test_02_college_commute_rain_expected(self):
        nlu = parse_query("Can I go to college today?")
        weather = create_weather(rain_prob=60.0, cond="Rain")
        reasoning = create_reasoning(risk=RiskLevelEnum.MEDIUM)
        sched = {"return_prob": 65.0, "departure_prob": 20.0}

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN, schedule_decision=sched)
        assert res.decision_type == DecisionTypeEnum.COLLEGE_COMMUTE
        assert res.verdict == DecisionVerdictEnum.GO
        assert "umbrella" in res.recommended_action.lower() or "raincoat" in res.recommended_action.lower()

    def test_03_college_commute_official_warning(self):
        nlu = parse_query("Can I go to college today?")
        weather = create_weather(rain_prob=80.0, cond="Heavy Rain")
        alert = OfficialAlert(
            source="IMD",
            type="rain_red",
            severity=RiskLevelEnum.EXTREME,
            title="Extremely Heavy Rain Red Alert",
            description="Severe flooding expected in low lying corridors.",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )
        reasoning = create_reasoning(risk=RiskLevelEnum.EXTREME, warnings=[alert])

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.COLLEGE_COMMUTE
        assert res.verdict == DecisionVerdictEnum.CAUTION
        assert "official college notices" in res.recommended_action.lower() or "imd alert" in res.recommended_action.lower()

    # -------------------------------------------------------------------------
    # 2. BIKE TRAVEL
    # -------------------------------------------------------------------------
    def test_04_bike_travel_clear(self):
        nlu = parse_query("Should I take my bike?")
        weather = create_weather(wind=10.0, rain_prob=5.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.BIKE_TRAVEL
        assert res.verdict == DecisionVerdictEnum.RECOMMENDED
        assert "safe to ride your bike" in res.recommended_action.lower()

    def test_05_bike_travel_high_winds_hazardous(self):
        nlu = parse_query("Should I take my bike?")
        weather = create_weather(wind=45.0, rain_prob=70.0, cond="Thunderstorm")
        storm_hazard = HazardDetection(
            hazard_type="thunderstorm",
            severity=RiskLevelEnum.HIGH,
            details="High winds and convective storm",
            is_official_warning=False
        )
        reasoning = create_reasoning(risk=RiskLevelEnum.HIGH, hazards=[storm_hazard])

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.BIKE_TRAVEL
        assert res.verdict == DecisionVerdictEnum.NOT_RECOMMENDED
        assert "avoid" in res.recommended_action.lower()

    # -------------------------------------------------------------------------
    # 3. UMBRELLA DECISION
    # -------------------------------------------------------------------------
    def test_06_umbrella_dry_not_needed(self):
        nlu = parse_query("Do I need an umbrella?")
        weather = create_weather(rain_prob=10.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.UMBRELLA
        assert res.verdict == DecisionVerdictEnum.NOT_RECOMMENDED
        assert "not required" in res.recommended_action.lower()

    def test_07_umbrella_rain_recommended(self):
        nlu = parse_query("Do I need an umbrella?")
        weather = create_weather(rain_prob=70.0)
        reasoning = create_reasoning(risk=RiskLevelEnum.MEDIUM)

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.UMBRELLA
        assert res.verdict == DecisionVerdictEnum.RECOMMENDED
        assert "carrying an umbrella is recommended" in res.recommended_action.lower()

    def test_08_wetness_inquiry_return(self):
        # "Will I get wet when I come back?"
        nlu = parse_query("Will I get wet when I come back?")
        weather = create_weather(rain_prob=75.0)
        reasoning = create_reasoning(risk=RiskLevelEnum.MEDIUM)

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.UMBRELLA
        assert res.verdict == DecisionVerdictEnum.RECOMMENDED

    # -------------------------------------------------------------------------
    # 4. SPORTS ACTIVITY
    # -------------------------------------------------------------------------
    def test_09_sports_clear_evening(self):
        nlu = parse_query("Can I play cricket this evening?")
        weather = create_weather(temp=27.0, rain_prob=5.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.SPORTS
        assert res.verdict == DecisionVerdictEnum.GO
        assert "great conditions" in res.recommended_action.lower()

    def test_10_sports_rain_no_go(self):
        nlu = parse_query("Can I play cricket this evening?")
        weather = create_weather(temp=25.0, rain_prob=60.0, cond="Rain")
        reasoning = create_reasoning(risk=RiskLevelEnum.MEDIUM)

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.SPORTS
        assert res.verdict == DecisionVerdictEnum.NO_GO
        assert "not recommended" in res.recommended_action.lower()

    # -------------------------------------------------------------------------
    # 5. OUTDOOR ACTIVITY & GENERAL "CAN I GO?"
    # -------------------------------------------------------------------------
    def test_11_outdoor_activity_go_outside(self):
        nlu = parse_query("Can I go outside?")
        weather = create_weather(temp=26.0, rain_prob=10.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.OUTDOOR_ACTIVITY
        assert res.verdict == DecisionVerdictEnum.GO
        assert "comfortably go outside" in res.recommended_action.lower()

    def test_12_general_can_i_go(self):
        nlu = parse_query("Can I go?")
        weather = create_weather(temp=26.0, rain_prob=10.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.GENERAL_GO
        assert res.verdict == DecisionVerdictEnum.GO

    # -------------------------------------------------------------------------
    # 6. FISHING & MARINE SAFETY
    # -------------------------------------------------------------------------
    def test_13_marine_fishing_calm(self):
        nlu = parse_query("Can I go fishing tomorrow?")
        weather = create_weather(wind=15.0, loc="Rameswaram")
        reasoning = create_reasoning(location="Rameswaram")

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.FISHING_MARINE
        assert res.verdict == DecisionVerdictEnum.GO
        assert "calm and favorable" in res.recommended_action.lower()

    def test_14_marine_fishing_rough_squally_no_go(self):
        nlu = parse_query("Can I go fishing tomorrow?")
        weather = create_weather(wind=52.0, loc="Rameswaram")
        reasoning = create_reasoning(risk=RiskLevelEnum.HIGH, location="Rameswaram")

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.FISHING_MARINE
        assert res.verdict == DecisionVerdictEnum.NO_GO
        assert "strictly advised not to venture" in res.recommended_action.lower()

    # -------------------------------------------------------------------------
    # 7. GENERAL TRAVEL
    # -------------------------------------------------------------------------
    def test_15_general_travel_safe(self):
        nlu = parse_query("Is it safe to travel?")
        weather = create_weather(rain_prob=5.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.GENERAL_TRAVEL
        assert res.verdict == DecisionVerdictEnum.GO
        assert "favorable and safe" in res.recommended_action.lower()

    # -------------------------------------------------------------------------
    # 8. CLOTHING ADVICE
    # -------------------------------------------------------------------------
    def test_16_clothing_advice_hot(self):
        nlu = parse_query("What should I wear today?")
        weather = create_weather(temp=36.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.CLOTHING
        assert "cotton" in res.recommended_action.lower()

    def test_17_clothing_advice_cold(self):
        nlu = parse_query("What should I wear today?")
        weather = create_weather(temp=14.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.CLOTHING
        assert "warm" in res.recommended_action.lower() or "jacket" in res.recommended_action.lower()

    # -------------------------------------------------------------------------
    # 9. MULTILINGUAL RESPONSES
    # -------------------------------------------------------------------------
    def test_18_multilingual_tamil_and_hindi(self):
        nlu = parse_query("Can I go to college today?")
        weather = create_weather(rain_prob=10.0)
        reasoning = create_reasoning()

        res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.TA)
        ans_ta = res.get_concise_answer(LanguageEnum.TA)
        assert "கல்லூரிக்கு செல்லலாம்" in ans_ta

        res_hi = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.HI)
        ans_hi = res_hi.get_concise_answer(LanguageEnum.HI)
        assert "कॉलेज" in ans_hi

    # -------------------------------------------------------------------------
    # 10. PIPELINE INTEGRATION
    # -------------------------------------------------------------------------
    def test_19_pipeline_personal_decision_payload(self):
        pipeline = WeatherGPTPipeline()
        from ai.models import LocationInfo
        mock_weather = WeatherRecord(
            location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
            observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc),
            temperature=28.0,
            humidity=60.0,
            rain_probability=10.0,
            wind_speed=12.0,
            weather_condition="Clear",
            source="IMD",
        )

        res = pipeline.process_query(
            message="Can I go to college today?",
            weather=mock_weather,
            persona=PersonaEnum.STUDENT
        )

        assert "personal_decision" in res
        dec = res["personal_decision"]
        assert dec is not None
        assert dec["decision_type"] == "college_commute"
        assert dec["verdict"] in ("GO", "CAUTION")
        assert "recommended_action" in dec
        assert "evidence" in dec
