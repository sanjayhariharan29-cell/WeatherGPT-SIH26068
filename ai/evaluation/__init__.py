"""WeatherGPT AI Evaluation and Quality Benchmarking Package."""

from ai.evaluation.dataset import (
    build_alerts_from_list,
    build_forecast_from_list,
    build_weather_record_from_dict,
    load_advisory_dataset,
    load_hazard_dataset,
    load_nlu_dataset,
    load_safety_dataset,
)
from ai.evaluation.runner import (
    evaluate_advisories,
    evaluate_hazards,
    evaluate_multilingual_consistency,
    evaluate_nlu,
    evaluate_safety,
    measure_latency,
    run_full_benchmark,
)
from ai.evaluation.schemas import (
    AdvisoryEvalCase,
    AdvisoryMetrics,
    BenchmarkReport,
    HazardEvalCase,
    HazardMetrics,
    LatencyMetrics,
    MultilingualMetrics,
    NLUEvalCase,
    NLUMetrics,
    SafetyEvalCase,
    SafetyMetrics,
)

from ai.evaluation.safety_evaluator import (
    SevereSafetyReport,
    SevereSafetyScenario,
    SevereWeatherSafetyEvaluator,
    build_safety_benchmark_dataset,
    run_severe_weather_safety_benchmark,
)

from ai.evaluation.pipeline_evaluator import (
    FullPipelineReport,
    FullPipelineScenario,
    FullPipelineEvaluator,
    build_pipeline_benchmark_dataset,
    run_full_pipeline_benchmark,
)

__all__ = [
    "load_nlu_dataset",
    "load_hazard_dataset",
    "load_advisory_dataset",
    "load_safety_dataset",
    "build_weather_record_from_dict",
    "build_alerts_from_list",
    "build_forecast_from_list",
    "evaluate_nlu",
    "evaluate_hazards",
    "evaluate_advisories",
    "evaluate_safety",
    "evaluate_multilingual_consistency",
    "measure_latency",
    "run_full_benchmark",
    "NLUEvalCase",
    "HazardEvalCase",
    "AdvisoryEvalCase",
    "SafetyEvalCase",
    "NLUMetrics",
    "HazardMetrics",
    "AdvisoryMetrics",
    "SafetyMetrics",
    "MultilingualMetrics",
    "LatencyMetrics",
    "BenchmarkReport",
    "SevereSafetyScenario",
    "SevereSafetyReport",
    "SevereWeatherSafetyEvaluator",
    "build_safety_benchmark_dataset",
    "run_severe_weather_safety_benchmark",
    "FullPipelineScenario",
    "FullPipelineReport",
    "FullPipelineEvaluator",
    "build_pipeline_benchmark_dataset",
    "run_full_pipeline_benchmark",
]
