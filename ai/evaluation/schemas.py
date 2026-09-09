"""Pydantic schemas and data models for Phase 10 AI Evaluation & Benchmarking."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NLUEvalCase(BaseModel):
    """Evaluation test case for NLU understanding."""
    id: str
    query: str
    expected_language: str
    expected_intent: str
    expected_location: Optional[str] = None
    expected_date: Optional[str] = None
    expected_persona: Optional[str] = None
    category: str = "general"
    description: Optional[str] = None


class HazardEvalCase(BaseModel):
    """Evaluation test case for deterministic hazard detection."""
    id: str
    weather: Dict[str, Any]
    forecast: Optional[List[Dict[str, Any]]] = None
    active_alerts: Optional[List[Dict[str, Any]]] = None
    expected_hazards: List[str] = Field(default_factory=list)
    expected_overall_risk: str
    description: Optional[str] = None


class AdvisoryEvalCase(BaseModel):
    """Evaluation test case for Decision Engine persona-tailored recommendations."""
    id: str
    persona: str
    weather: Dict[str, Any]
    forecast: Optional[List[Dict[str, Any]]] = None
    active_alerts: Optional[List[Dict[str, Any]]] = None
    expected_advisory_type: str
    expected_priority: str
    expected_keywords: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class SafetyEvalCase(BaseModel):
    """Evaluation test case for ResponseValidator anti-hallucination and safety gate."""
    id: str
    response_text: str
    weather: Dict[str, Any]
    forecast: Optional[List[Dict[str, Any]]] = None
    active_alerts: Optional[List[Dict[str, Any]]] = None
    advisory: Optional[Dict[str, Any]] = None
    target_language: Optional[str] = None
    expected_valid: bool
    expected_violations: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class NLUMetrics(BaseModel):
    total_cases: int
    language_accuracy: float
    intent_accuracy: float
    location_accuracy: float
    temporal_accuracy: float
    persona_accuracy: float
    overall_accuracy: float


class HazardMetrics(BaseModel):
    total_cases: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    per_hazard_metrics: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class AdvisoryMetrics(BaseModel):
    total_cases: int
    advisory_type_accuracy: float
    priority_accuracy: float
    guidance_keyword_match_rate: float
    overall_accuracy: float


class SafetyMetrics(BaseModel):
    total_cases: int
    safe_pass_rate: float
    hallucination_rejection_rate: float
    false_rejection_rate: float
    overall_accuracy: float
    category_detection_counts: Dict[str, int] = Field(default_factory=dict)


class MultilingualMetrics(BaseModel):
    total_triplets: int
    semantic_invariance_rate: float
    decision_match_rate: float
    hazard_match_rate: float


class LatencyMetrics(BaseModel):
    nlu_latency_ms: float
    reasoner_latency_ms: float
    hazard_latency_ms: float
    advisory_latency_ms: float
    validator_latency_ms: float
    pipeline_latency_ms: float


class WeatherReasonerMetrics(BaseModel):
    """Metrics evaluating deterministic meteorological reasoning."""
    total_cases: int
    freshness_classification_accuracy: float
    completeness_accuracy: float
    source_agreement_accuracy: float
    contradiction_detection_accuracy: float
    consistency_score_validity_rate: float
    official_warning_priority_rate: float
    missing_data_safety_rate: float
    temporal_consistency_rate: float
    location_consistency_rate: float
    overall_accuracy: float


class DetailedSafetyMetrics(BaseModel):
    """Fine-grained safety metrics with zero tolerance for critical violations."""
    total_cases: int
    warning_preservation_rate: float
    warning_contradiction_rate: float  # Target: 0.0
    fabricated_weather_data_rate: float  # Target: 0.0
    fabricated_action_rate: float  # Target: 0.0
    unsupported_certainty_rate: float  # Target: 0.0
    severity_downgrade_rate: float  # Target: 0.0
    unsafe_fallback_rate: float  # Target: 0.0
    critical_safety_violation_count: int  # Target: 0


class MultilingualInvarianceMetrics(BaseModel):
    """Invariance of weather decisions and parameters across languages and dialects."""
    total_scenarios: int
    warning_status_invariance_rate: float
    hazard_invariance_rate: float
    severity_invariance_rate: float
    numbers_invariance_rate: float
    source_invariance_rate: float
    location_invariance_rate: float
    temporal_scope_invariance_rate: float
    safety_decision_invariance_rate: float
    overall_multilingual_invariance_rate: float


class FailureClassificationEnum(str):
    """Root-cause classification categories for benchmark failures."""
    NLU = "NLU"
    NORMALIZATION = "NORMALIZATION"
    WEATHER_REASONING = "WEATHER_REASONING"
    HAZARD_DETECTION = "HAZARD_DETECTION"
    ADVISORY_ENGINE = "ADVISORY_ENGINE"
    LLM = "LLM"
    VALIDATOR = "VALIDATOR"
    MEMORY = "MEMORY"
    MULTILINGUAL_GENERATION = "MULTILINGUAL_GENERATION"
    INTEGRATION = "INTEGRATION"


class FailureAnalysisItem(BaseModel):
    """Detailed record of a benchmark failure for root-cause analysis."""
    case_id: str
    stage: str
    description: str
    expected: str
    actual: str
    root_cause: str


class EndToEndPartitionReport(BaseModel):
    """Separated end-to-end benchmark partition results."""
    deterministic_benchmark_score: float
    llm_assisted_benchmark_score: float
    multilingual_benchmark_score: float
    adversarial_benchmark_score: float
    severe_weather_safety_score: float
    total_evaluated_scenarios: int


class BenchmarkReport(BaseModel):
    timestamp: datetime
    version: str = "1.0.0"
    nlu: NLUMetrics
    hazard: HazardMetrics
    advisory: AdvisoryMetrics
    safety: SafetyMetrics
    multilingual: MultilingualMetrics
    latency: LatencyMetrics
    reasoner: Optional[WeatherReasonerMetrics] = None
    detailed_safety: Optional[DetailedSafetyMetrics] = None
    multilingual_invariance: Optional[MultilingualInvarianceMetrics] = None
    failure_analysis: List[FailureAnalysisItem] = Field(default_factory=list)
    end_to_end_partitions: Optional[EndToEndPartitionReport] = None
    summary: Dict[str, Any] = Field(default_factory=dict)

