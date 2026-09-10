"""SkyZen Phase 8: Historical Weather & Risk Intelligence Test Suite.

Validates the complete historical weather and risk intelligence layer across all required specifications:
1. Valid historical weather request with explicit dates and verified metrics
2. Invalid date range handling (start_date > end_date raises descriptive ValueError)
3. Future date request rejection (dates ahead of UTC now rejected with forecast guidance)
4. Missing historical data handled gracefully without hallucinated statistics
5. Provider failure resilience and clean fallback
6. Seasonal comparison & anomaly detection using actual retrieved records ("Is this rainfall unusual?")
7. Strict data type separation: HISTORICAL, CURRENT, FORECAST, OFFICIAL_WARNING
8. Safety invariant: Historical hazards cannot become current warnings (enforced by ResponseValidator & prompt)
9. Performance & caching: 24h TTL cache avoids redundant provider calls
10. End-to-end conversational AI answers historical queries ("How much did it rain last year?", multilingual Tamil/Hindi)
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from ai.models import (
    WeatherDataType,
    HistoricalWeatherDataset,
    WeatherRecord,
    ForecastItem,
    OfficialAlert,
    LocationInfo,
    DecisionTrace,
    PersonaEnum,
    RiskLevelEnum,
)
from ai.pipeline import WeatherGPTPipeline
from ai.reasoner import WeatherReasoner
from ai.validator.response_validator import ResponseValidator
from backend.services.historical_weather_service import HistoricalWeatherService
from backend.services.weather_manager import WeatherManager
from backend.services.chat_integration_service import ChatIntegrationService
from backend.services.exceptions import ProviderError
from backend.db.session import get_db, Base, engine


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_location():
    return LocationInfo(name="Chennai", latitude=13.0827, longitude=80.2707, state="Tamil Nadu", country="India")


@pytest.fixture
def sample_current_weather(now, sample_location):
    return WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=31.0,
        humidity=68.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Partly Cloudy",
        source="IMD",
        data_type=WeatherDataType.CURRENT
    )


@pytest.fixture
def sample_forecast(now, sample_location):
    return [
        ForecastItem(
            time=(now + timedelta(hours=3)).isoformat(),
            temperature=30.0,
            rain_probability=20.0,
            wind_speed=11.0,
            condition="Partly Cloudy",
            rainfall_amount_mm=0.5,
            data_type=WeatherDataType.FORECAST
        )
    ]


@pytest.fixture
def sample_historical_dataset(sample_location):
    return HistoricalWeatherDataset(
        location=sample_location,
        start_date="2023-01-01",
        end_date="2023-12-31",
        data_type=WeatherDataType.HISTORICAL,
        is_available=True,
        total_rainfall_mm=1340.5,
        average_temperature_c=29.2,
        max_temperature_c=41.5,
        min_temperature_c=21.0,
        weather_patterns=["Northeast monsoon peak in November", "Dry summer between March and May"],
        recurring_hazards=["Cyclonic depressions in coastal Tamil Nadu (October-December)"],
        rainfall_normal_mm=1200.0,
        temp_normal_c=28.8,
        record_count=365,
        primary_source="IMD Archive / NASA POWER",
        data_quality="verified_archive",
        safety_disclaimer=(
            "Historical records reflect past meteorological observations and climate baselines. "
            "They do not represent active forecasts or warnings."
        )
    )


# =========================================================================
# 1. VALID HISTORICAL REQUEST
# =========================================================================
def test_01_valid_historical_request(db_session):
    """Test 1: Valid historical weather request returns verified dataset with explicit dates."""
    service = HistoricalWeatherService()
    dataset = asyncio.run(
        service.get_historical_dataset(
            lat=13.0827,
            lon=80.2707,
            location_name="Chennai",
            start_date="2023-01-01",
            end_date="2023-12-31",
            db_session=db_session
        )
    )

    assert dataset.is_available is True
    assert dataset.data_type == WeatherDataType.HISTORICAL
    assert dataset.start_date == "2023-01-01"
    assert dataset.end_date == "2023-12-31"
    assert dataset.location.name == "Chennai"
    assert dataset.total_rainfall_mm is not None and dataset.total_rainfall_mm >= 0
    assert dataset.avg_temperature_c is not None
    assert dataset.primary_source is not None
    assert len(dataset.weather_patterns) > 0
    assert "Historical records reflect past meteorological observations" in dataset.safety_disclaimer


# =========================================================================
# 2. INVALID DATE RANGE
# =========================================================================
def test_02_invalid_date_range():
    """Test 2: Reject start_date > end_date with descriptive error."""
    service = HistoricalWeatherService()
    with pytest.raises(ValueError, match="must be <= end_date"):
        asyncio.run(
            service.fetch_historical_weather(
                location_name="Chennai",
                start_date="2024-06-01",
                end_date="2024-01-01"
            )
        )

    with pytest.raises(ValueError, match="must be <= end_date"):
        HistoricalWeatherService.parse_and_validate_dates("2024-12-01", "2024-01-01")


# =========================================================================
# 3. FUTURE DATE REQUEST REJECTION
# =========================================================================
def test_03_future_date_request():
    """Test 3: Reject dates in the future with clear error explaining archives cover past only."""
    with pytest.raises(ValueError, match="cannot be in the future"):
        HistoricalWeatherService.parse_and_validate_dates("2030-01-01", "2030-12-31")

    future_year = datetime.now(timezone.utc).year + 5
    with pytest.raises(ValueError, match="cannot be in the future|live forecast"):
        HistoricalWeatherService.parse_and_validate_dates(f"{future_year}-01-01", f"{future_year}-06-01")


# =========================================================================
# 4. MISSING HISTORICAL DATA GRACEFUL HANDLING
# =========================================================================
def test_04_missing_historical_data_graceful():
    """Test 4: Handle missing historical data gracefully without crashing or fabricating numbers."""
    service = HistoricalWeatherService()

    # Mock fetch_historical_weather returning an empty object with count=0 and records=[]
    empty_mock = MagicMock()
    empty_mock.count = 0
    empty_mock.records = []
    empty_mock.summary = {}
    empty_mock.location = "NowhereIsland"
    empty_mock.latitude = 0.0
    empty_mock.longitude = 0.0
    empty_mock.source = "Historical Archive"

    with patch.object(service, "fetch_historical_weather", return_value=empty_mock):
        dataset = asyncio.run(
            service.get_historical_dataset(
                lat=0.0,
                lon=0.0,
                location_name="NowhereIsland",
                start_date="2022-01-01",
                end_date="2022-01-10"
            )
        )

    assert dataset.is_available is False
    assert dataset.data_quality == "no_records"
    assert dataset.total_rainfall_mm is None
    assert dataset.avg_temperature_c is None
    assert dataset.start_date == "2022-01-01"
    assert dataset.end_date == "2022-01-10"


# =========================================================================
# 5. PROVIDER FAILURE RESILIENCE
# =========================================================================
def test_05_provider_failure_resilience():
    """Test 5: Provider connection failure degrades cleanly to an unavailable dataset without raising exceptions."""
    service = HistoricalWeatherService()

    with patch.object(service, "fetch_historical_weather", side_effect=ProviderError("Archive unreachable")):
        dataset = asyncio.run(
            service.get_historical_dataset(
                lat=13.0827,
                lon=80.2707,
                location_name="Chennai",
                start_date="2021-01-01",
                end_date="2021-12-31"
            )
        )

    assert dataset.is_available is False
    assert dataset.data_quality == "provider_error"
    assert dataset.location.name == "Chennai"
    assert dataset.total_rainfall_mm is None


# =========================================================================
# 6. SEASONAL COMPARISON & ANOMALY DETECTION
# =========================================================================
def test_06_seasonal_comparison_and_anomaly_detection(sample_historical_dataset, sample_current_weather, sample_forecast):
    """Test 6: AI answers comparison queries using actual retrieved numbers vs historical baselines."""
    pipeline = WeatherGPTPipeline()

    # Case A: "Is this rainfall unusual compared with previous years?"
    res_a = pipeline.process_query(
        message="Is this rainfall unusual compared with previous years?",
        weather=sample_current_weather,
        forecast=sample_forecast,
        historical_weather=sample_historical_dataset
    )
    ans_a = res_a["answer"]

    # Must contain actual figures from retrieved dataset (1340.5 mm or normal 1200.0 mm)
    assert "1340.5" in ans_a or "1,340.5" in ans_a or "1340" in ans_a
    assert "1200" in ans_a or "baseline" in ans_a.lower() or "normal" in ans_a.lower()
    # Must explicitly state the date range
    assert "2023-01-01" in ans_a and "2023-12-31" in ans_a

    # Case B: "What is the typical temperature this month?"
    res_b = pipeline.process_query(
        message="What is the typical temperature this month?",
        weather=sample_current_weather,
        forecast=sample_forecast,
        historical_weather=sample_historical_dataset
    )
    ans_b = res_b["answer"]
    assert "29.2" in ans_b or "28.8" in ans_b
    assert "baseline" in ans_b.lower() or "typical" in ans_b.lower() or "average" in ans_b.lower()


# =========================================================================
# 7. STRICT HISTORICAL / CURRENT / FORECAST / WARNING SEPARATION
# =========================================================================
def test_07_strict_historical_current_forecast_separation(sample_historical_dataset, sample_current_weather, sample_forecast, now):
    """Test 7: Strict data type discrimination across models, pipeline, and decision traces."""
    # Verify Enum values
    assert WeatherDataType.HISTORICAL == "HISTORICAL"
    assert WeatherDataType.CURRENT == "CURRENT"
    assert WeatherDataType.FORECAST == "FORECAST"
    assert WeatherDataType.OFFICIAL_WARNING == "OFFICIAL_WARNING"

    # Verify model tags
    assert sample_historical_dataset.data_type == WeatherDataType.HISTORICAL
    assert sample_current_weather.data_type == WeatherDataType.CURRENT
    assert sample_forecast[0].data_type == WeatherDataType.FORECAST

    alert = OfficialAlert(
        type="heavy_rain",
        severity=RiskLevelEnum.HIGH,
        title="Heavy Rain Warning",
        description="Official IMD alert",
        issued_at=now,
        expires_at=now + timedelta(hours=6),
        source="IMD",
        data_type=WeatherDataType.OFFICIAL_WARNING
    )
    assert alert.data_type == WeatherDataType.OFFICIAL_WARNING

    # Pipeline output separation
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="Tell me about Chennai weather last year and today",
        weather=sample_current_weather,
        forecast=sample_forecast,
        active_alerts=[alert],
        historical_weather=sample_historical_dataset
    )

    # Must return separated outputs
    assert "historical" in result
    assert result["historical"] is not None
    assert result["historical"]["data_type"] == "HISTORICAL"
    assert result["weather"]["temperature"] == sample_current_weather.temperature
    assert result["forecast_count"] > 0
    assert len(result["alerts"]) > 0

    # Decision trace must record all active data types without confusion
    trace: DecisionTrace = result["decision_trace_model"]
    assert "HISTORICAL" in trace.data_types_used
    assert "CURRENT" in trace.data_types_used
    assert "FORECAST" in trace.data_types_used
    assert "OFFICIAL_WARNING" in trace.data_types_used
    assert trace.historical_context is not None
    assert trace.historical_context["start_date"] == "2023-01-01"


# =========================================================================
# 8. SAFETY: HISTORICAL HAZARD CANNOT BECOME A CURRENT WARNING
# =========================================================================
def test_08_safety_historical_hazard_never_becomes_warning(sample_historical_dataset, sample_current_weather):
    """Test 8: Validator blocks conflating historical events with active warnings."""
    validator = ResponseValidator()
    reasoning = WeatherReasoner.evaluate(primary_weather=sample_current_weather)

    # Bad response: claims flooding expected today because of last year's flooding
    hallucinated_warning = (
        "Last year there was flooding, so flooding is expected today. "
        "Take immediate shelter and evacuate low-lying areas."
    )
    validation_bad = validator.validate_response(
        response_text=hallucinated_warning,
        reasoning=reasoning,
        weather=sample_current_weather,
        historical_weather=sample_historical_dataset
    )
    assert validation_bad.is_valid is False
    assert any("historical" in err.lower() or "confusion" in err.lower() or "warning" in err.lower() for err in validation_bad.violations)

    # Safe response: clearly separates past hazards and advises checking current forecasts
    safe_response = (
        "Historical records show flooding occurred in similar periods during 2023, "
        "but today's conditions should be evaluated using current forecasts (currently partly cloudy, 31°C) "
        "and official warnings."
    )
    validation_good = validator.validate_response(
        response_text=safe_response,
        reasoning=reasoning,
        weather=sample_current_weather,
        historical_weather=sample_historical_dataset
    )
    assert validation_good.is_valid is True


# =========================================================================
# 9. NO FABRICATION OF HISTORICAL STATISTICS
# =========================================================================
def test_09_no_fabrication_of_historical_statistics(sample_current_weather, sample_forecast):
    """Test 9: AI explicitly states lack of data instead of hallucinating historical numbers."""
    pipeline = WeatherGPTPipeline()

    # Dataset marked as unavailable
    unavailable_dataset = HistoricalWeatherDataset(
        location=sample_current_weather.location,
        start_date="2021-01-01",
        end_date="2021-12-31",
        is_available=False,
        data_quality="no_records"
    )

    result = pipeline.process_query(
        message="How much did it rain here last year?",
        weather=sample_current_weather,
        forecast=sample_forecast,
        historical_weather=unavailable_dataset
    )
    answer = result["answer"]

    # Must contain explicit refusal to fabricate
    assert "SkyZen does not fabricate historical statistics" in answer
    assert "unavailable" in answer.lower()


# =========================================================================
# 10. PERFORMANCE & 24H TTL CACHING
# =========================================================================
def test_10_performance_ttl_caching():
    """Test 10: In-memory TTL cache prevents duplicate provider calls for identical queries."""
    service = HistoricalWeatherService()

    # First call (populates provider_cache)
    res1 = asyncio.run(
        service.fetch_historical_weather(
            lat=11.0168,
            lon=76.9558,
            location_name="Coimbatore",
            start_date="2023-01-01",
            end_date="2023-06-01"
        )
    )

    # Spy/mock the provider to ensure it is NOT called on second identical fetch
    with patch.object(service.provider, "get_historical_weather", side_effect=Exception("Should use cache!")):
        res2 = asyncio.run(
            service.fetch_historical_weather(
                lat=11.0168,
                lon=76.9558,
                location_name="Coimbatore",
                start_date="2023-01-01",
                end_date="2023-06-01"
            )
        )

    assert res1.location == res2.location
    assert res1.count == res2.count


# =========================================================================
# 11. END-TO-END CONVERSATIONAL AI (ENGLISH, TAMIL, HINDI)
# =========================================================================
def test_11_e2e_conversational_historical_answers(db_session):
    """Test 11: End-to-end ChatIntegrationService handles historical questions in English, Tamil, and Hindi."""
    chat_service = ChatIntegrationService()

    # English query: "How much did it rain in Chennai last year?"
    res_en = asyncio.run(
        chat_service.handle_chat_request(
            message="How much did it rain in Chennai last year?",
            lat=13.0827,
            lon=80.2707,
            location_name="Chennai",
            language="en"
        )
    )
    assert res_en["answer"] is not None
    assert "mm" in res_en["answer"] or "rainfall" in res_en["answer"].lower()
    assert res_en.get("historical") is not None
    # Check trace includes historical metadata
    trace_en = res_en.get("decision_trace")
    assert trace_en is not None
    assert "HISTORICAL" in trace_en.get("data_types_used", [])
    assert trace_en.get("historical_context") is not None
    assert trace_en["historical_context"]["data_type"] == "HISTORICAL"

    # Tamil query: "சென்னையில் கடந்த ஆண்டு எவ்வளவு மழை பெய்தது?"
    res_ta = asyncio.run(
        chat_service.handle_chat_request(
            message="சென்னையில் கடந்த ஆண்டு எவ்வளவு மழை பெய்தது?",
            lat=13.0827,
            lon=80.2707,
            location_name="Chennai",
            language="ta"
        )
    )
    assert res_ta["answer"] is not None
    assert "மழை" in res_ta["answer"] or "வரலாற்று" in res_ta["answer"] or "மி.மீ" in res_ta["answer"]
    assert "HISTORICAL" in res_ta.get("decision_trace", {}).get("data_types_used", [])

    # Hindi query: "चेन्नई में पिछले साल कितनी बारिश हुई थी?"
    res_hi = asyncio.run(
        chat_service.handle_chat_request(
            message="चेन्नई में पिछले साल कितनी बारिश हुई थी?",
            lat=13.0827,
            lon=80.2707,
            location_name="Chennai",
            language="hi"
        )
    )
    assert res_hi["answer"] is not None
    assert "बारिश" in res_hi["answer"] or "वर्षा" in res_hi["answer"] or "ऐतिहासिक" in res_hi["answer"]
    assert "HISTORICAL" in res_hi.get("decision_trace", {}).get("data_types_used", [])
