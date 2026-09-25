"""Automated Test Suite for Reproducible SkyZen Evaluation & Benchmarks (Phase 32).

Verifies:
1. Deterministic dataset covers all required representative query types:
   - student
   - farmer
   - fisherman
   - commuter
   - disaster
   - normal weather
   - severe weather
   - ambiguous queries
   - multilingual queries (ta, en, hi, te)
2. All 12 required metrics are computed deterministically:
   - Intent recognition accuracy
   - Entity extraction accuracy
   - Language detection accuracy
   - Grounding correctness
   - Response validation failures
   - Official-warning contradiction rate
   - API response latency
   - End-to-end response latency
   - Provider fallback success
   - Alert targeting correctness
   - Notification delivery success
   - Multilingual response consistency
3. Benchmark results record:
   - sample size
   - test conditions
   - timestamp
   - metric definition
4. Strict safety compliance:
   - official_warning_contradiction_rate == 0.0%
   - non-production accuracy disclaimer present in all outputs
5. Machine-readable evaluation report is generated properly
"""

import os
import json
import pytest
from datetime import datetime
from pathlib import Path

from ai.evaluation.deterministic_benchmark_dataset import get_benchmark_dataset, BenchmarkQueryCase
from ai.evaluation.benchmark_evaluator import SkyZenBenchmarkEvaluator, BENCHMARK_DISCLAIMER


REQUIRED_METRICS = [
    "intent_recognition_accuracy",
    "entity_extraction_accuracy",
    "language_detection_accuracy",
    "grounding_correctness",
    "response_validation_failures",
    "official_warning_contradiction_rate",
    "api_response_latency",
    "end_to_end_response_latency",
    "provider_fallback_success",
    "alert_targeting_correctness",
    "notification_delivery_success",
    "multilingual_response_consistency"
]

REQUIRED_CATEGORIES = [
    "student",
    "farmer",
    "fisherman",
    "commuter",
    "disaster",
    "normal_weather",
    "severe_weather",
    "ambiguous",
    "multilingual"
]


def test_deterministic_dataset_coverage():
    """Verify evaluation dataset contains all representative user categories."""
    dataset = get_benchmark_dataset()
    assert len(dataset) >= 12, "Dataset must contain representative sample queries"

    present_categories = {case.category for case in dataset}
    for cat in REQUIRED_CATEGORIES:
        assert cat in present_categories, f"Missing required query category: '{cat}'"

    # Verify multilingual languages represented
    langs = {case.expected_language for case in dataset}
    assert "en" in langs
    assert "ta" in langs
    assert "hi" in langs
    assert "te" in langs


def test_evaluator_runs_all_12_metrics():
    """Verify evaluator computes all 12 metrics and produces valid results."""
    evaluator = SkyZenBenchmarkEvaluator()
    report = evaluator.run_all_benchmarks()

    assert "report_title" in report
    assert "generated_at" in report
    assert "metrics" in report
    assert report["total_metrics_evaluated"] == 12

    metrics = report["metrics"]
    for req_m in REQUIRED_METRICS:
        assert req_m in metrics, f"Missing required metric: '{req_m}'"
        m_data = metrics[req_m]

        # Verify standard metadata recorded for every metric
        assert "sample_size" in m_data and m_data["sample_size"] > 0
        assert "test_conditions" in m_data and isinstance(m_data["test_conditions"], dict)
        assert "timestamp" in m_data and m_data["timestamp"]
        assert "metric_definition" in m_data and len(m_data["metric_definition"]) > 10
        assert "disclaimer" in m_data
        assert "NOT claim" in m_data["disclaimer"]


def test_safety_official_warning_contradiction_rate():
    """CRITICAL SAFETY INVARIANT: Official warning contradiction rate must be strictly 0.0%."""
    evaluator = SkyZenBenchmarkEvaluator()
    m_data = evaluator.evaluate_warning_contradiction_rate()

    assert m_data["metric_name"] == "official_warning_contradiction_rate"
    assert m_data["value"] == 0.0, "System must never contradict or downplay active official warnings"
    assert m_data["sample_size"] > 0


def test_grounding_and_validation():
    """Verify grounding accuracy and adversarial hallucination catch rate."""
    evaluator = SkyZenBenchmarkEvaluator()

    grounding = evaluator.evaluate_grounding_correctness()
    assert grounding["value"] >= 80.0, "Grounded statements must match verified observations"

    validation = evaluator.evaluate_response_validation()
    assert validation["value"] >= 50.0, "Adversarial hallucinations must be caught by validator gate"


def test_latencies_and_resilience():
    """Verify API and end-to-end latencies and fallback success."""
    evaluator = SkyZenBenchmarkEvaluator()

    api_lat = evaluator.evaluate_api_latency(iterations=10)
    assert api_lat["value"]["p50_ms"] >= 0.0
    assert api_lat["value"]["max_ms"] >= api_lat["value"]["p50_ms"]

    e2e_lat = evaluator.evaluate_end_to_end_latency(iterations=5)
    assert e2e_lat["value"]["p50_ms"] >= 0.0

    fallback = evaluator.evaluate_provider_fallback()
    assert fallback["value"] == 100.0, "Fallback provider must succeed upon primary timeout"


def test_machine_readable_report_serialization(tmp_path):
    """Verify machine-readable evaluation report can be written and reloaded as valid JSON."""
    evaluator = SkyZenBenchmarkEvaluator()
    report = evaluator.run_all_benchmarks()

    report_file = tmp_path / "test_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    assert report_file.exists()
    with open(report_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["report_title"] == report["report_title"]
    assert len(loaded["metrics"]) == 12
