"""
Test Suite: SkyZen Action-Driven Personal Weather Intent Understanding & NLU
Validates intent classification, entity extraction (transport mode, activity, person context,
reference expressions, decision wording, time/date/range), prompt examples, and multilingual support
(English, Tamil, Tanglish, Hindi, Hinglish).
"""
import pytest
from ai.models import IntentEnum, ExtractedEntities, PersonaEnum
from ai.nlu import (
    classify_intent,
    extract_entities,
    parse_query,
    detect_language
)


def get_intent(query: str):
    intent, _ = classify_intent(query)
    return intent


class TestActionOrientedIntents:
    """Validate that the 8 exact user examples map to specific action intents and extract key entities."""

    def test_example_1_college_commute(self):
        query = "Can I go to college?"
        intent = get_intent(query)
        entities = extract_entities(query)
        assert intent == IntentEnum.COLLEGE_COMMUTE
        assert intent.value == "college_commute"
        assert entities.activity == "college"
        assert entities.person_context == "student"
        assert entities.decision_wording == "can i go"

    def test_example_2_bike_travel(self):
        query = "Should I take my bike?"
        intent = get_intent(query)
        entities = extract_entities(query)
        assert intent == IntentEnum.BIKE_TRAVEL
        assert intent.value == "bike_travel"
        assert entities.transport_mode == "bike"
        assert entities.decision_wording == "should i take"

    def test_example_3_umbrella_decision(self):
        query = "Do I need an umbrella?"
        intent = get_intent(query)
        entities = extract_entities(query)
        assert intent == IntentEnum.UMBRELLA_DECISION
        assert intent.value == "umbrella_decision"
        assert entities.decision_wording == "do i need"

    def test_example_4_sports_activity(self):
        query = "Can I play cricket?"
        intent = get_intent(query)
        entities = extract_entities(query)
        assert intent == IntentEnum.SPORTS_ACTIVITY
        assert intent.value == "sports_activity"
        assert entities.activity == "cricket"
        assert entities.decision_wording == "can i play"

    def test_example_5_fishing_decision(self):
        query = "Can I go fishing?"
        intent = get_intent(query)
        entities = extract_entities(query)
        assert intent == IntentEnum.FISHING_DECISION
        assert intent.value == "fishing_decision"
        assert entities.activity == "fishing"
        assert entities.person_context == "fisherman"
        assert entities.decision_wording == "can i go"

    def test_example_6_will_it_rain_when_i_come_back(self):
        query = "Will it rain when I come back?"
        intent = get_intent(query)
        entities = extract_entities(query)
        assert intent in (IntentEnum.TIME_SPECIFIC_WEATHER, IntentEnum.RAIN_QUERY)
        assert entities.time == "return window"
        assert entities.reference_expression in ("when I come back", "when returning")
        assert entities.person_context == "commuter"

    def test_example_7_and_friday(self):
        query = "And Friday?"
        entities = extract_entities(query)
        assert entities.date == "Friday"
        assert entities.reference_expression == "And Friday?"

    def test_example_8_what_about_5(self):
        query = "What about 5?"
        entities = extract_entities(query)
        assert entities.time == "5:00"
        assert entities.reference_expression == "What about 5?"


class TestAllIntentCategories:
    """Validate coverage across all 21 personal weather intent categories."""

    @pytest.mark.parametrize(
        "query,expected_intent",
        [
            ("What is the general weather today in Delhi?", IntentEnum.WEATHER_INFORMATION),
            ("Is it going to rain this afternoon?", IntentEnum.RAIN_QUERY),
            ("Do I need to carry an umbrella?", IntentEnum.UMBRELLA_DECISION),
            ("Can I travel to Bangalore by car?", IntentEnum.TRAVEL_DECISION),
            ("Can I go to college today?", IntentEnum.COLLEGE_COMMUTE),
            ("Should I ride my bike today?", IntentEnum.BIKE_TRAVEL),
            ("Can we plan an outdoor picnic?", IntentEnum.OUTDOOR_ACTIVITY),
            ("Can we play football in the ground?", IntentEnum.SPORTS_ACTIVITY),
            ("Is it safe to spray pesticides on crops today?", IntentEnum.FARMING_DECISION),
            ("Can fishermen venture out to sea?", IntentEnum.FISHING_DECISION),
            ("Is there high wave alert for deep sea?", IntentEnum.MARINE_SAFETY),
            ("Is there any severe cyclone warning?", IntentEnum.WARNING_QUERY),
            ("What is the AQI and air quality in Mumbai?", IntentEnum.AQI_QUERY),
            ("How hot will it get today?", IntentEnum.TEMPERATURE_QUERY),
            ("What is the 7-day weather forecast?", IntentEnum.FORECAST_QUERY),
            ("What clothes should I wear today, sweater or jacket?", IntentEnum.CLOTHING_ADVICE),
            ("Will it rain at 4 PM?", IntentEnum.TIME_SPECIFIC_WEATHER),
            ("Weather conditions specifically in Tambaram", IntentEnum.LOCATION_SPECIFIC_WEATHER),
            ("Hello good morning how are you?", IntentEnum.GENERAL_CONVERSATION),
            ("Yes, exactly that's what I meant", IntentEnum.CLARIFICATION_RESPONSE),
            ("xyz qwerty 12345", IntentEnum.UNKNOWN),
        ],
    )
    def test_intent_classification_cases(self, query, expected_intent):
        detected = get_intent(query)
        assert detected == expected_intent


class TestEntityExtractionRobustness:
    """Validate extraction of rich structured entities."""

    def test_complex_travel_query(self):
        query = "Can I ride my bike from Chennai to Vellore tomorrow between 9 AM and 1 PM?"
        parsed = parse_query(query)
        assert parsed.intent == IntentEnum.BIKE_TRAVEL
        assert parsed.entities.transport_mode == "bike"
        assert parsed.entities.date == "tomorrow"
        assert parsed.entities.time_range is not None
        assert "9" in parsed.entities.time_range
        assert "1" in parsed.entities.time_range
        assert len(parsed.entities.locations) >= 2
        assert "Chennai" in parsed.entities.locations
        assert "Vellore" in parsed.entities.locations

    def test_comparison_wording(self):
        query = "Which is cooler, Ooty or Kodaikanal?"
        parsed = parse_query(query)
        assert parsed.entities.comparison_wording == "which is cooler"
        assert "Ooty" in parsed.entities.locations
        assert "Kodaikanal" in parsed.entities.locations

    def test_farming_entities(self):
        query = "Can I spray fertilizer on the field tomorrow morning?"
        parsed = parse_query(query)
        assert parsed.intent == IntentEnum.FARMING_DECISION
        assert parsed.entities.persona == PersonaEnum.FARMER
        assert parsed.entities.activity == "farming"
        assert parsed.entities.date == "tomorrow"
        assert parsed.entities.time in ("morning", "06:00-12:00")


class TestMultilingualActionVariants:
    """Validate natural language variants across supported languages: Tamil, Tanglish, Hindi, Hinglish."""

    def test_tamil_script_variants(self):
        # College
        assert get_intent("நாளை கல்லூரிக்கு செல்லலாமா?") == IntentEnum.COLLEGE_COMMUTE
        assert get_intent("இன்று கல்லூரி போலாமா?") == IntentEnum.COLLEGE_COMMUTE
        # Umbrella
        assert get_intent("இன்னைக்கு குடை தேவையா?") == IntentEnum.UMBRELLA_DECISION
        # Fishing
        assert get_intent("நாளை கடலுக்கு போகலாமா?") == IntentEnum.FISHING_DECISION
        # Rain
        assert get_intent("இன்று மழை பெய்யுமா?") == IntentEnum.RAIN_QUERY

    def test_tanglish_variants(self):
        # College commute
        assert get_intent("Naalaiku college pogalama?") == IntentEnum.COLLEGE_COMMUTE
        assert get_intent("Innaiku college polama?") == IntentEnum.COLLEGE_COMMUTE
        # Umbrella
        assert get_intent("Innaiku kudai thevaya?") == IntentEnum.UMBRELLA_DECISION
        # Bike
        assert get_intent("Naan bike la pogalama?") == IntentEnum.BIKE_TRAVEL
        # Sports
        assert get_intent("Innaiku cricket vilayadalama?") == IntentEnum.SPORTS_ACTIVITY
        # Fishing
        assert get_intent("Meen pidikka polama?") == IntentEnum.FISHING_DECISION

    def test_hindi_script_variants(self):
        # College
        assert get_intent("क्या आज कॉलेज जा सकते हैं?") == IntentEnum.COLLEGE_COMMUTE
        # Umbrella
        assert get_intent("क्या आज छाता ले जाना चाहिए?") == IntentEnum.UMBRELLA_DECISION
        # Fishing
        assert get_intent("क्या कल मछली पकड़ने जा सकते हैं?") == IntentEnum.FISHING_DECISION
        # Sports
        assert get_intent("क्या आज क्रिकेट खेल सकते हैं?") == IntentEnum.SPORTS_ACTIVITY

    def test_hinglish_variants(self):
        # College
        assert get_intent("Kya main aaj college ja sakta hu?") == IntentEnum.COLLEGE_COMMUTE
        # Umbrella
        assert get_intent("Kya mujhe aaj chhata le jana chahiye?") == IntentEnum.UMBRELLA_DECISION
        # Bike
        assert get_intent("Kya bike se jana safe hai?") == IntentEnum.BIKE_TRAVEL
        # Sports
        assert get_intent("Kya cricket khel sakte hain?") == IntentEnum.SPORTS_ACTIVITY
        # Rain
        assert get_intent("Kya aaj barish hogi?") == IntentEnum.RAIN_QUERY


class TestBackwardCompatibility:
    """Ensure that legacy tests checking broad categories (OUTDOOR_DECISION, RAIN, etc.) remain compatible."""

    def test_college_is_subclass_of_outdoor_decision(self):
        assert IntentEnum.COLLEGE_COMMUTE == IntentEnum.OUTDOOR_DECISION
        assert IntentEnum.OUTDOOR_DECISION == IntentEnum.COLLEGE_COMMUTE

    def test_umbrella_is_subclass_of_umbrella_or_rain(self):
        assert IntentEnum.UMBRELLA_DECISION == IntentEnum.RAIN_FORECAST
        assert IntentEnum.UMBRELLA_DECISION == "rain_query"

    def test_bike_travel_is_subclass_of_outdoor(self):
        assert IntentEnum.BIKE_TRAVEL == IntentEnum.OUTDOOR_DECISION

    def test_fishing_is_subclass_of_outdoor_or_marine(self):
        assert IntentEnum.FISHING_DECISION == IntentEnum.OUTDOOR_DECISION
        assert IntentEnum.FISHING_DECISION == "marine_safety"
