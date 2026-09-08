"""Unit Test Suite for Phase 10 AI Evaluation & Benchmarking Framework.

Verifies:
1. Dataset loading
2. Schema validation
3. NLU metrics computation
4. Hazard metrics computation (Precision, Recall, F1)
5. Validator and safety metrics computation
6. Multilingual semantic equivalence
7. End-to-end benchmark execution
8. Deterministic reproducibility
9. Malformed/empty dataset handling
10. Regression baseline loading and verification against thresholds
"""

import pytest
from pydantic import ValidationError

from ai.evaluation import (
    AdvisoryEvalCase,
    BenchmarkReport,
    HazardEvalCase,
    NLUEvalCase,
    SafetyEvalCase,
    evaluate_advisories,
    evaluate_hazards,
    evaluate_multilingual_consistency,
    evaluate_nlu,
    evaluate_safety,
    load_advisory_dataset,
    load_hazard_dataset,
    load_nlu_dataset,
    load_safety_dataset,
    measure_latency,
    run_full_benchmark,
)
from ai.evaluation.runner import load_regression_baseline


def test_01_datasets_load():
    """Verify that all golden evaluation datasets load properly from disk."""
    nlu_data = load_nlu_dataset()
    hazard_data = load_hazard_dataset()
    advisory_data = load_advisory_dataset()
    safety_data = load_safety_dataset()

    assert len(nlu_data) >= 30
    assert len(hazard_data) >= 10
    assert len(advisory_data) >= 5
    assert len(safety_data) >= 15


def test_02_schemas_validate():
    """Verify Pydantic models validate good records and reject malformed schemas."""
    # Valid NLU case
    good_case = NLUEvalCase(
        id="test_01",
        query="What is the weather?",
        expected_language="en",
        expected_intent="current_weather",
    )
    assert good_case.id == "test_01"

    # Missing required query field
    with pytest.raises(ValidationError):
        NLUEvalCase.model_validate({"id": "bad_case", "expected_language": "en"})


def test_03_nlu_metrics_calculate():
    """Verify NLU metrics calculation produces valid percentages."""
    metrics = evaluate_nlu()
    assert metrics.total_cases >= 30
    assert 0.0 <= metrics.language_accuracy <= 1.0
    assert 0.0 <= metrics.intent_accuracy <= 1.0
    assert 0.0 <= metrics.location_accuracy <= 1.0
    assert 0.0 <= metrics.temporal_accuracy <= 1.0
    assert 0.0 <= metrics.overall_accuracy <= 1.0
    assert metrics.language_accuracy >= 0.90
    assert metrics.intent_accuracy >= 0.90


def test_04_hazard_metrics_calculate():
    """Verify hazard metrics calculation yields mathematically sound Precision, Recall, and F1."""
    metrics = evaluate_hazards()
    assert metrics.total_cases >= 10
    assert 0.0 <= metrics.precision <= 1.0
    assert 0.0 <= metrics.recall <= 1.0
    assert 0.0 <= metrics.f1 <= 1.0
    assert metrics.f1 >= 0.90
    assert metrics.true_positives > 0


def test_05_validator_metrics_calculate():
    """Verify safety metrics calculation properly isolates safe passes vs hallucination rejections."""
    metrics = evaluate_safety()
    assert metrics.total_cases >= 15
    assert metrics.safe_pass_rate == 1.0
    assert metrics.hallucination_rejection_rate == 1.0
    assert metrics.false_rejection_rate == 0.0
    assert metrics.overall_accuracy == 1.0
    assert "UNSUPPORTED_NUMBER" in metrics.category_detection_counts
    assert "WARNING_CONTRADICTION" in metrics.category_detection_counts


def test_06_multilingual_equivalence_works():
    """Verify that semantic decisions are invariant across English, Tamil, and Hindi."""
    metrics = evaluate_multilingual_consistency()
    assert metrics.total_triplets >= 3
    assert metrics.decision_match_rate == 1.0
    assert metrics.hazard_match_rate == 1.0
    assert metrics.semantic_invariance_rate == 1.0


def test_07_end_to_end_benchmark_works():
    """Verify that run_full_benchmark() executes and produces a complete BenchmarkReport."""
    report = run_full_benchmark()
    assert isinstance(report, BenchmarkReport)
    assert report.version == "1.0.0"
    assert report.nlu.total_cases > 0
    assert report.hazard.total_cases > 0
    assert report.advisory.total_cases > 0
    assert report.safety.total_cases > 0
    assert report.latency.pipeline_latency_ms >= 0.0


def test_08_deterministic_results():
    """Verify that repeated benchmark evaluations produce identical, reproducible results."""
    m1 = evaluate_nlu()
    m2 = evaluate_nlu()
    assert m1.overall_accuracy == m2.overall_accuracy
    assert m1.intent_accuracy == m2.intent_accuracy

    h1 = evaluate_hazards()
    h2 = evaluate_hazards()
    assert h1.f1 == h2.f1
    assert h1.true_positives == h2.true_positives


def test_09_malformed_dataset_handled():
    """Verify that empty or single-item datasets calculate gracefully without division by zero."""
    empty_nlu = evaluate_nlu(dataset=[])
    assert empty_nlu.total_cases == 0
    assert empty_nlu.overall_accuracy == 1.0

    empty_hazard = evaluate_hazards(dataset=[])
    assert empty_hazard.total_cases == 0
    assert empty_hazard.f1 == 1.0

    empty_safety = evaluate_safety(dataset=[])
    assert empty_safety.total_cases == 0
    assert empty_safety.overall_accuracy == 1.0


def test_10_regression_baseline_loads_and_verifies():
    """Verify that the stored regression baseline loads and meets conservative quality thresholds."""
    baseline = load_regression_baseline()
    assert baseline.version == "1.0.0"
    assert baseline.nlu.language_accuracy >= 0.90
    assert baseline.nlu.intent_accuracy >= 0.90
    assert baseline.hazard.f1 >= 0.90
    assert baseline.advisory.overall_accuracy >= 0.90
    assert baseline.safety.hallucination_rejection_rate >= 0.90
    assert baseline.safety.false_rejection_rate <= 0.05
    assert baseline.multilingual.semantic_invariance_rate >= 0.95
