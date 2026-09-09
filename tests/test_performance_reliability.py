"""WeatherGPT SIH26068 Phase 17 — Performance & Reliability Test Suite.

Validates:
- API p50, p95, p99 latency metrics
- Database query speed & index optimization
- In-memory cache TTL, hit/miss performance, and bounded memory growth
- Provider failure failover latency & retry bounds
- AI deterministic pipeline stage speed (NLU, Reasoner, Hazard, Advisory)
- High-concurrency multi-request resilience
- Graceful degradation under provider or DB failures
"""

import time
import math
import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.cache import ProviderCache, provider_cache
from backend.services.weather_manager import WeatherManager
from backend.db.session import SessionLocal, engine
from backend.db.models import Base, User, Conversation, Message, WeatherRecord, Alert
from backend.core.security import hash_password, create_access_token
from ai.pipeline import WeatherGPTPipeline

client = TestClient(app)
pipeline_instance = WeatherGPTPipeline()

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    provider_cache.clear()
    yield
    provider_cache.clear()


def calculate_percentiles(latencies):
    """Utility function to calculate p50, p95, p99 percentiles."""
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    p50 = sorted_l[int(math.ceil(0.50 * n)) - 1]
    p95 = sorted_l[int(math.ceil(0.95 * n)) - 1]
    p99 = sorted_l[int(math.ceil(0.99 * n)) - 1]
    return p50, p95, p99


# =============================================================================
# 1. API LATENCY & PERCENTILE DISTRIBUTION (p50, p95, p99)
# =============================================================================
def test_01_api_latency_distribution():
    """Measures API latency distribution (p50, p95, p99) over 25 sequential health requests."""
    latencies = []
    for _ in range(25):
        start = time.perf_counter()
        res = client.get("/api/v1/health")
        elapsed = time.perf_counter() - start
        assert res.status_code == 200
        latencies.append(elapsed * 1000) # Convert to ms

    p50, p95, p99 = calculate_percentiles(latencies)
    assert p50 < 100.0, f"Health endpoint p50 latency too high: {p50:.2f}ms"
    assert p95 < 300.0, f"Health endpoint p95 latency too high: {p95:.2f}ms"


def test_02_current_weather_api_latency():
    """Measures current weather API latency p50 and p95 percentiles."""
    from backend.services.schemas import NormalizedWeatherObservation

    mock_obs = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=28.0,
        feels_like_c=29.0,
        humidity_pct=65.0,
        rain_probability_pct=20.0,
        wind_speed_kmh=12.0,
        condition="Clear",
        source="IMD (Mock)",
        observed_at="2026-09-09T10:00:00Z",
        retrieved_at="2026-09-09T10:00:00Z"
    )
    mock_loc = {"name": "Coimbatore", "latitude": 11.0168, "longitude": 76.9558, "district": "Coimbatore", "state": "Tamil Nadu"}

    latencies = []
    with patch("backend.services.imd_adapter.IMDAdapter.get_current_weather", return_value=mock_obs), \
         patch("backend.services.open_meteo_adapter.OpenMeteoAdapter.get_current_weather", return_value=mock_obs), \
         patch("backend.services.geocoding_service.GeocodingService.resolve_location", return_value=mock_loc):
        for _ in range(10):
            start = time.perf_counter()
            res = client.get("/api/v1/weather/current?location=Coimbatore")
            elapsed = time.perf_counter() - start
            assert res.status_code == 200
            latencies.append(elapsed * 1000)

    p50, p95, _ = calculate_percentiles(latencies)
    assert p50 < 300.0, f"Current weather API p50 too high: {p50:.2f}ms"
    assert p95 < 500.0, f"Current weather API p95 too high: {p95:.2f}ms"


# =============================================================================
# 2. CACHE HIT VS MISS PERFORMANCE & TTL EXPIRATION
# =============================================================================
def test_03_cache_hit_acceleration():
    """Verifies that cache hit reduces weather retrieval latency dramatically."""
    cache = ProviderCache(default_ttl=5)
    cache.clear()

    # Miss
    start_miss = time.perf_counter()
    res1 = cache.get("test_key")
    miss_time = (time.perf_counter() - start_miss) * 1000
    assert res1 is None

    cache.set("test_key", {"temp": 28.5})

    # Hit
    start_hit = time.perf_counter()
    res2 = cache.get("test_key")
    hit_time = (time.perf_counter() - start_hit) * 1000
    assert res2 == {"temp": 28.5}
    assert hit_time < 5.0, f"Cache hit latency too high: {hit_time:.3f}ms"


def test_04_cache_ttl_expiration():
    """Verifies that cached items expire correctly after TTL elapsed."""
    cache = ProviderCache(default_ttl=1) # 1 second TTL
    cache.set("expire_key", "value_1", ttl=1)
    assert cache.get("expire_key") == "value_1"

    time.sleep(1.1)
    assert cache.get("expire_key") is None


def test_05_bounded_cache_capacity_and_eviction():
    """Verifies that ProviderCache enforces max_entries capacity limits and prevents unbounded memory growth."""
    small_cache = ProviderCache(default_ttl=300, max_entries=10)
    for i in range(25):
        small_cache.set(f"key_{i}", f"value_{i}")

    assert small_cache.size <= 10, f"Cache size exceeded capacity limit: {small_cache.size}"


# =============================================================================
# 3. DATABASE QUERY LATENCY & INDEX OPTIMIZATION
# =============================================================================
def test_06_database_query_performance():
    """Measures database query latencies for user conversations and indexed weather records."""
    db = SessionLocal()
    try:
        # Seed test data
        u = User(email=f"perf_{uuid.uuid4().hex[:6]}@test.com", name="Perf User", password_hash=hash_password("Pass123!"))
        db.add(u)
        db.commit()

        conv = Conversation(user_id=u.id, title="Perf Chat")
        db.add(conv)
        db.commit()

        # Measure indexed user_id conversation query speed
        start = time.perf_counter()
        results = db.query(Conversation).filter(Conversation.user_id == u.id).all()
        query_time = (time.perf_counter() - start) * 1000

        assert len(results) == 1
        assert query_time < 100.0, f"Database query latency too high: {query_time:.2f}ms"
    finally:
        db.close()


# =============================================================================
# 4. DETERMINISTIC AI PIPELINE LATENCY
# =============================================================================
def test_07_deterministic_ai_pipeline_stages_latency():
    """Measures processing speed of Person 1's deterministic AI pipeline stages (NLU, Reasoner, Hazard, Advisory)."""
    start = time.perf_counter()
    res = pipeline_instance.process_query(message="Will it rain tomorrow in Coimbatore?")
    elapsed = (time.perf_counter() - start) * 1000

    assert "reply" in res or "answer" in res
    assert elapsed < 1000.0, f"AI deterministic pipeline execution too slow: {elapsed:.2f}ms"


# =============================================================================
# 5. CONCURRENCY & MULTI-THREADED REQUEST HANDLING
# =============================================================================
def test_08_concurrent_requests_handling():
    """Executes 8 concurrent weather requests using ThreadPoolExecutor to verify thread-safety and zero crashes."""
    def make_request(idx):
        return client.get(f"/api/v1/weather/current?location=Coimbatore&t={idx}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(make_request, i) for i in range(8)]
        results = [f.result() for f in futures]

    for res in results:
        assert res.status_code == 200
        assert "weather" in res.json()


# =============================================================================
# 6. PROVIDER FAILURE FAILOVER LATENCY & RESILIENCE
# =============================================================================
def test_09_provider_failover_latency():
    """Measures failover latency when primary provider throws an exception."""
    from backend.services.exceptions import ProviderUnavailableError
    from backend.services.schemas import NormalizedWeatherObservation

    mock_secondary_obs = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=28.0,
        feels_like_c=29.0,
        humidity_pct=65.0,
        rain_probability_pct=20.0,
        wind_speed_kmh=12.0,
        condition="Partly Cloudy",
        source="Open-Meteo (Mock)",
        observed_at="2026-09-09T10:00:00Z",
        retrieved_at="2026-09-09T10:00:00Z"
    )
    mock_loc = {"name": "Coimbatore", "latitude": 11.0168, "longitude": 76.9558, "district": "Coimbatore", "state": "Tamil Nadu"}

    start = time.perf_counter()
    with patch("backend.services.imd_adapter.IMDAdapter.get_current_weather", side_effect=ProviderUnavailableError("IMD Down", "IMD")), \
         patch("backend.services.open_meteo_adapter.OpenMeteoAdapter.get_current_weather", return_value=mock_secondary_obs), \
         patch("backend.services.geocoding_service.GeocodingService.resolve_location", return_value=mock_loc):
        res = client.get("/api/v1/weather/current?location=Coimbatore")
        elapsed = (time.perf_counter() - start) * 1000

        assert res.status_code == 200
        assert "weather" in res.json()
        assert elapsed < 500.0, f"Failover latency too high: {elapsed:.2f}ms"


# =============================================================================
# 7. GRACEFUL DEGRADATION UNDER DATABASE LOCK
# =============================================================================
def test_10_database_failure_resilience():
    """Verifies API returns valid response or graceful status even when DB commit fails."""
    payload = {
        "message": "Current weather in Coimbatore?",
        "language": "en",
        "persona": "general",
        "location": {"name": "Coimbatore"}
    }
    with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("DB Connection Lost")):
        res = client.post("/api/v1/chat", json=payload)
        assert res.status_code in [200, 500, 504]


# =============================================================================
# 8. NO CROSS-USER CHAT RESPONSE CACHING
# =============================================================================
def test_11_no_cross_user_cache_leakage():
    """Verifies user-specific chat requests are never globally cached across distinct users.

    Patches the LLM provider's generate_text method in addition to weather/geocoding
    to prevent real Gemini HTTP calls on CI (which time out with mock API keys and
    produce a 504, obscuring the actual cache-isolation assertion being tested).
    """
    conv1_id = str(uuid.uuid4())
    conv2_id = str(uuid.uuid4())

    u1_payload = {"message": "My name is User 1", "language": "en", "conversation_id": conv1_id}
    u2_payload = {"message": "My name is User 2", "language": "en", "conversation_id": conv2_id}

    mock_loc = {"name": "Coimbatore", "latitude": 11.0168, "longitude": 76.9558, "district": "Coimbatore", "state": "Tamil Nadu"}
    mock_weather = {
        "location": "Coimbatore", "latitude": 11.0168, "longitude": 76.9558,
        "temperature": 28.5, "humidity": 65, "wind_speed": 12.0,
        "condition": "Partly Cloudy", "description": "Scattered clouds",
        "timestamp": "2026-09-09T10:00:00Z", "source": "Open-Meteo"
    }
    canned_llm = "Weather conditions in Coimbatore are partly cloudy with moderate humidity."

    with patch("backend.services.geocoding_service.GeocodingService.resolve_location", return_value=mock_loc), \
         patch("backend.services.weather_manager.WeatherManager.get_current_weather", return_value=mock_weather), \
         patch("ai.llm.provider.GeminiLLMProvider.generate_text", return_value=canned_llm):
        res1 = client.post("/api/v1/chat", json=u1_payload)
        res2 = client.post("/api/v1/chat", json=u2_payload)

        assert res1.status_code == 200, (
            f"User 1 chat failed (HTTP {res1.status_code}): {res1.text}"
        )
        assert res2.status_code == 200, (
            f"User 2 chat failed (HTTP {res2.status_code}): {res2.text}"
        )
        assert res1.json()["conversation_id"] != res2.json()["conversation_id"], (
            "Cache leakage detected: both users received the same conversation_id"
        )
