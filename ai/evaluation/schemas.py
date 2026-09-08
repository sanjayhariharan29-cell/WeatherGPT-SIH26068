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


class BenchmarkReport(BaseModel):
    timestamp: datetime
    version: str = "1.0.0"
    nlu: NLUMetrics
    hazard: HazardMetrics
    advisory: AdvisoryMetrics
    safety: SafetyMetrics
    multilingual: MultilingualMetrics
    latency: LatencyMetrics
    summary: Dict[str, Any] = Field(default_factory=dict)
