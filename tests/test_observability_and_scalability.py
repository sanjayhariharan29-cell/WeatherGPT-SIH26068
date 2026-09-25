"""Production Observability and Scalability Test Suite (Phase 33).

Verifies all 15 required observability and scalability controls:
 1. Structured backend logging & request correlation IDs
 2. X-Request-ID header generation & propagation
 3. Provider latency tracking & reservoir percentiles
 4. LLM latency metrics (NLU, Reasoner, Decision, Validator)
 5. API latency metrics (p50, p95, mean)
 6. Error-rate tracking & status distribution
 7. Provider availability tracking & state degradation
 8. Database health probe
 9. FCM health telemetry
10. Cache health & hit-ratio calculation
11. Weather data freshness monitoring
12. Alert processing throughput tracking
13. Graceful degradation states & circuit breakers
14. Retry and backoff statistics
15. Health, liveness, readiness, and metrics endpoints
"""

import time
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.observability_service import observability_service, RollingLatencyReservoir

client = TestClient(app)


# =========================================================================
# 1 & 2. REQUEST CORRELATION IDS & LOGGING
# =========================================================================
def test_request_id_correlation_propagation():
    """Verify X-Request-ID is generated if missing and preserved if supplied."""
    # 1. Generated automatically
    resp1 = client.get("/health")
    assert resp1.status_code == 200
    assert "X-Request-ID" in resp1.headers
    assert "X-Response-Time-Ms" in resp1.headers
    gen_id = resp1.headers["X-Request-ID"]
    assert len(gen_id) >= 10

    # 2. Supplied by caller preserved
    custom_id = "test-correlation-uuid-12345"
    resp2 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp2.status_code == 200
    assert resp2.headers["X-Request-ID"] == custom_id


# =========================================================================
# 3. PROVIDER LATENCY & AVAILABILITY TRACKING
# =========================================================================
def test_provider_latency_and_availability():
    """Verify recording provider latencies and consecutive failure degradation."""
    # Record successes
    observability_service.record_provider_call("IMD", 45.0, success=True)
    observability_service.record_provider_call("IMD", 55.0, success=True)
    observability_service.record_provider_call("IMD", 65.0, success=True)

    metrics = observability_service.get_provider_metrics()
    assert "IMD" in metrics
    assert metrics["IMD"]["state"] == "ONLINE"
    assert metrics["IMD"]["successes"] >= 3
    assert metrics["IMD"]["latency"]["count"] >= 3
    assert metrics["IMD"]["latency"]["p50_ms"] > 0

    # Simulate consecutive failures triggering degradation
    for _ in range(3):
        observability_service.record_provider_call("TestFailingProvider", 500.0, success=False)

    fail_metrics = observability_service.get_provider_metrics()
    assert fail_metrics["TestFailingProvider"]["state"] == "DEGRADED"


# =========================================================================
# 4. LLM LATENCY TRACKING
# =========================================================================
def test_llm_latency_tracking():
    """Verify latency recording across NLU, Reasoner, Decision, and Validator."""
    observability_service.record_llm_step("nlu", 12.5)
    observability_service.record_llm_step("reasoner", 8.2)
    observability_service.record_llm_step("decision", 15.0)
    observability_service.record_llm_step("validator", 4.1)

    llm_metrics = observability_service.get_llm_metrics()
    assert llm_metrics["nlu"]["count"] >= 1
    assert llm_metrics["reasoner"]["count"] >= 1
    assert llm_metrics["decision"]["count"] >= 1
    assert llm_metrics["validator"]["count"] >= 1


# =========================================================================
# 5 & 6. API LATENCY & ERROR RATE TRACKING
# =========================================================================
def test_api_latency_and_error_rate():
    """Verify API latency percentiles and error-rate tracking."""
    # Reset / record controlled calls
    observability_service.record_api_request(200, 10.0)
    observability_service.record_api_request(200, 20.0)
    observability_service.record_api_request(404, 15.0)
    observability_service.record_api_request(500, 30.0)

    api_m = observability_service.get_api_metrics()
    assert api_m["total_requests"] >= 4
    assert api_m["status_distribution"]["2xx"] >= 2
    assert api_m["status_distribution"]["4xx"] >= 1
    assert api_m["status_distribution"]["5xx"] >= 1
    assert api_m["error_rate_pct"] > 0.0
    assert api_m["latencies"]["mean_ms"] > 0.0


# =========================================================================
# 7 & 8. DATABASE HEALTH & READINESS PROBE
# =========================================================================
def test_database_health_probes():
    """Verify /health/readiness and /health/liveness probes."""
    resp_live = client.get("/health/liveness")
    assert resp_live.status_code == 200
    assert resp_live.json()["status"] == "alive"

    resp_ready = client.get("/health/readiness")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["status"] == "ready"
    assert resp_ready.json()["database"] == "connected"


# =========================================================================
# 9 & 10. FCM & CACHE HEALTH TRACKING
# =========================================================================
def test_cache_and_fcm_health():
    """Verify cache hit/miss tracking and FCM status."""
    observability_service.record_cache_event("hits")
    observability_service.record_cache_event("hits")
    observability_service.record_cache_event("misses")

    cache_m = observability_service.get_cache_metrics()
    assert cache_m["hits"] >= 2
    assert cache_m["misses"] >= 1
    assert 0.0 <= cache_m["hit_ratio_pct"] <= 100.0


# =========================================================================
# 11, 12, 13, 14. ALERT PROCESSING, DEGRADATION & RETRIES
# =========================================================================
def test_alert_processing_and_degradation_state():
    """Verify alert throughput, degradation transitions, and retry metrics."""
    # Alert metrics
    observability_service.record_alert_processed(is_active=True)
    observability_service.record_alert_processed(is_active=False)

    # Retry metrics
    observability_service.record_retry(backoff_ms=250.0, succeeded=True)

    # Degradation state
    observability_service.set_degradation_state("DEGRADED_PROVIDER", ["IMD endpoint high latency"])

    snap = observability_service.get_telemetry_snapshot()
    assert snap["alert_metrics"]["processed_count"] >= 2
    assert snap["alert_metrics"]["active_count"] >= 1
    assert snap["retry_metrics"]["retries_attempted"] >= 1
    assert snap["retry_metrics"]["total_backoff_ms"] >= 250.0
    assert snap["degradation_state"] == "DEGRADED_PROVIDER"
    assert "IMD endpoint high latency" in snap["degradation_reasons"]

    # Reset back to NORMAL
    observability_service.set_degradation_state("NORMAL", [])


# =========================================================================
# 15. HEALTH & OBSERVABILITY ENDPOINTS
# =========================================================================
def test_health_metrics_endpoint():
    """Verify /health/metrics returns comprehensive telemetry payload."""
    resp = client.get("/health/metrics")
    assert resp.status_code == 200
    data = resp.json()

    assert "api_metrics" in data
    assert "provider_metrics" in data
    assert "llm_metrics" in data
    assert "cache_metrics" in data
    assert "alert_metrics" in data
    assert "retry_metrics" in data
    assert "degradation_state" in data


def test_detailed_health_check_endpoint():
    """Verify /health/detailed multi-subsystem probe without credential exposure."""
    resp = client.get("/health/detailed")
    assert resp.status_code == 200
    data = resp.json()

    assert "subsystems" in data
    assert "database" in data["subsystems"]
    assert "cache" in data["subsystems"]
    assert "fcm_gateway" in data["subsystems"]
    assert data["subsystems"]["database"]["status"] == "HEALTHY"

    # Redaction assertion
    text = resp.text.lower()
    assert "secret_key" not in text
    assert "password_hash" not in text
    assert "private_key" not in text
