"""Lightweight Local Load-Test Framework for SkyZen (Phase 33).

Provides controlled, deterministic local load testing for:
1. Weather API latency
2. AI pipeline latency
3. End-to-end response latency
4. Notification processing & targeting latency

Records real local numbers without invention, and explicitly documents
what was load-tested versus what was not.
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from ai.models import (
    WeatherRecord,
    LocationInfo,
    OfficialAlert,
    RiskLevelEnum,
    LanguageEnum,
    PersonaEnum,
)
from ai.nlu import parse_query
from ai.reasoner import WeatherReasoner
from ai.decision import DecisionEngine
from ai.validator import ResponseValidator
from backend.services.alert_engine import AlertEngine

client = TestClient(app)

LOAD_TESTED_TARGETS = [
    "FastAPI Weather Current Observation Endpoint (/api/v1/weather/current)",
    "AI Meteorological Reasoner (WeatherReasoner.evaluate)",
    "AI Persona Decision Advisory Engine (DecisionEngine.generate_advisory)",
    "AI Safety Response Validation Gate (ResponseValidator.validate_response)",
    "Full End-to-End Query Pipeline (NLU -> Reasoner -> Decision -> Validator)",
    "Disaster Notification Geographic Targeting & Bounding Engine (AlertEngine.match_affected_area)"
]

NOT_LOAD_TESTED_TARGETS = [
    "External Live IMD GeoServer WFS Production Endpoint (prohibited to avoid DoS on government servers)",
    "External Firebase Cloud Messaging (FCM) Production Push Delivery Gateway",
    "External Live SMS Gateway Delivery (untested to prevent telecom carrier throttling/charges)",
    "Distributed Kubernetes Cluster Pod Auto-scaling (not currently deployed)"
]


def calculate_latencies(latencies: List[float], total_time_sec: float) -> Dict[str, Any]:
    """Calculates throughput (RPS) and latency percentiles."""
    if not latencies:
        return {"count": 0, "rps": 0.0}

    s = sorted(latencies)
    n = len(s)

    def pct(p: float) -> float:
        return round(s[min(int(n * p), n - 1)], 2)

    mean_val = round(sum(s) / n, 2)
    rps = round(n / total_time_sec, 1) if total_time_sec > 0 else 0.0

    return {
        "sample_size": n,
        "rps": rps,
        "p50_ms": pct(0.50),
        "p90_ms": pct(0.90),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
        "mean_ms": mean_val,
        "min_ms": round(s[0], 2),
        "max_ms": round(s[-1], 2)
    }


def benchmark_weather_api(concurrency: int, total_requests: int) -> Dict[str, Any]:
    """Measures local Weather API endpoint latency and throughput."""
    latencies = []
    successes = 0

    def single_req():
        t0 = time.perf_counter()
        resp = client.get("/api/v1/weather/current?location=Coimbatore")
        dt = (time.perf_counter() - t0) * 1000.0
        return resp.status_code == 200, dt

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(single_req) for _ in range(total_requests)]
        for f in as_completed(futures):
            ok, dt = f.result()
            if ok:
                successes += 1
            latencies.append(dt)
    t_total = time.perf_counter() - t_start

    res = calculate_latencies(latencies, t_total)
    res["success_count"] = successes
    res["concurrency"] = concurrency
    return res


def benchmark_ai_pipeline(concurrency: int, total_requests: int) -> Dict[str, Any]:
    """Measures AI reasoning, persona decision, and validation latency under concurrent load."""
    latencies = []
    successes = 0

    now = time.time()
    w_rec = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558, state="Tamil Nadu"),
        observed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now - 600)),
        retrieved_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
        temperature=28.5,
        humidity=72.0,
        rain_probability=45.0,
        wind_speed=15.0,
        weather_condition="Scattered Clouds",
        source="IMD"
    )

    def single_eval():
        t0 = time.perf_counter()
        hazards = WeatherReasoner.evaluate(primary_weather=w_rec)
        advisory = DecisionEngine.generate_advisory(
            hazards,
            persona=PersonaEnum.STUDENT,
            target_language=LanguageEnum.EN,
            weather=w_rec
        )
        val = ResponseValidator.validate_response(
            response_text=advisory.advisory_text,
            reasoning=hazards,
            weather=w_rec,
            advisory=advisory
        )
        dt = (time.perf_counter() - t0) * 1000.0
        return val.is_valid, dt

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(single_eval) for _ in range(total_requests)]
        for f in as_completed(futures):
            ok, dt = f.result()
            if ok:
                successes += 1
            latencies.append(dt)
    t_total = time.perf_counter() - t_start

    res = calculate_latencies(latencies, t_total)
    res["success_count"] = successes
    res["concurrency"] = concurrency
    return res


def benchmark_end_to_end(concurrency: int, total_requests: int) -> Dict[str, Any]:
    """Measures complete end-to-end query to advisory response pipeline latency."""
    latencies = []
    successes = 0

    query = "Will it rain during school hours in Coimbatore tomorrow?"

    def single_e2e():
        t0 = time.perf_counter()
        # 1. NLU
        nlu = parse_query(query)
        # 2. Reasoner & Decision
        w_rec = WeatherRecord(
            location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558, state="Tamil Nadu"),
            observed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            retrieved_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            temperature=27.0,
            humidity=80.0,
            rain_probability=85.0,
            wind_speed=18.0,
            weather_condition="Moderate Rain",
            source="IMD"
        )
        hazards = WeatherReasoner.evaluate(primary_weather=w_rec)
        advisory = DecisionEngine.generate_advisory(hazards, persona=PersonaEnum.STUDENT, weather=w_rec)
        val = ResponseValidator.validate_response(advisory.advisory_text, reasoning=hazards, weather=w_rec)
        dt = (time.perf_counter() - t0) * 1000.0
        return val.is_valid, dt

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(single_e2e) for _ in range(total_requests)]
        for f in as_completed(futures):
            ok, dt = f.result()
            if ok:
                successes += 1
            latencies.append(dt)
    t_total = time.perf_counter() - t_start

    res = calculate_latencies(latencies, t_total)
    res["success_count"] = successes
    res["concurrency"] = concurrency
    return res


def benchmark_notification_processing(concurrency: int, total_requests: int) -> Dict[str, Any]:
    """Measures spatial geographic targeting and eligibility check throughput."""
    engine = AlertEngine()
    latencies = []
    successes = 0

    def single_target():
        t0 = time.perf_counter()
        matched = engine.match_affected_area(
            alert_area="Coimbatore District",
            user_location_name="Coimbatore",
            alert_lat=11.0168,
            alert_lon=76.9558,
            user_lat=11.0168,
            user_lon=76.9558
        )
        dt = (time.perf_counter() - t0) * 1000.0
        return matched, dt

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(single_target) for _ in range(total_requests)]
        for f in as_completed(futures):
            matched, dt = f.result()
            if matched:
                successes += 1
            latencies.append(dt)
    t_total = time.perf_counter() - t_start

    res = calculate_latencies(latencies, t_total)
    res["success_count"] = successes
    res["concurrency"] = concurrency
    return res


def run_load_test(concurrency: int = 5, requests_per_target: int = 40) -> Dict[str, Any]:
    """Executes full load-test across all four targets."""
    print(f"[*] Running SkyZen Local Load-Test with concurrency={concurrency}, requests={requests_per_target}...")

    weather_api_res = benchmark_weather_api(concurrency, requests_per_target)
    ai_pipeline_res = benchmark_ai_pipeline(concurrency, requests_per_target)
    e2e_res = benchmark_end_to_end(concurrency, requests_per_target)
    notif_res = benchmark_notification_processing(concurrency, requests_per_target)

    report = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "configuration": {
            "concurrency": concurrency,
            "requests_per_target": requests_per_target,
            "environment": "local_testing"
        },
        "load_tested_targets": LOAD_TESTED_TARGETS,
        "not_load_tested_targets": NOT_LOAD_TESTED_TARGETS,
        "results": {
            "weather_api_latency": weather_api_res,
            "ai_pipeline_latency": ai_pipeline_res,
            "end_to_end_response_latency": e2e_res,
            "notification_processing_latency": notif_res
        }
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Run controlled local load testing for SkyZen.")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent workers")
    parser.add_argument("--requests", type=int, default=40, help="Requests per target")
    parser.add_argument("--output", type=str, default="reports/local_load_test_report.json", help="Report output path")
    args = parser.parse_args()

    report = run_load_test(concurrency=args.concurrency, requests_per_target=args.requests)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"[+] Load test complete. Report saved to: {out_path.resolve()}\n")
    print("-------------------------------------------------------------------------")
    print(f"{'TARGET':<32} | {'RPS':<8} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'max (ms)':<10}")
    print("-------------------------------------------------------------------------")
    for k, v in report["results"].items():
        print(f"{k:<32} | {v.get('rps', 0):<8} | {v.get('p50_ms', 0):<10} | {v.get('p95_ms', 0):<10} | {v.get('max_ms', 0):<10}")
    print("-------------------------------------------------------------------------")


if __name__ == "__main__":
    main()
