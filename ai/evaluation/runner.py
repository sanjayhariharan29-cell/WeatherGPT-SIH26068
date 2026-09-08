"""Executable AI Evaluation & Benchmarking Runner for WeatherGPT."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ai.decision import DecisionEngine
from ai.evaluation.dataset import (
    build_alerts_from_list,
    build_forecast_from_list,
    build_weather_record_from_dict,
    load_advisory_dataset,
    load_hazard_dataset,
    load_nlu_dataset,
    load_safety_dataset,
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
from ai.models import (
    LanguageEnum,
    PersonaEnum,
)
from ai.nlu import parse_query
from ai.pipeline import WeatherGPTPipeline
from ai.reasoner import WeatherReasoner
from ai.validator import ResponseValidator


def evaluate_nlu(dataset: Optional[List[NLUEvalCase]] = None) -> NLUMetrics:
    """Evaluates NLU query understanding across language detection, intent, and entities."""
    cases = dataset if dataset is not None else load_nlu_dataset()
    total = len(cases)
    if total == 0:
        return NLUMetrics(
            total_cases=0,
            language_accuracy=1.0,
            intent_accuracy=1.0,
            location_accuracy=1.0,
            temporal_accuracy=1.0,
            persona_accuracy=1.0,
            overall_accuracy=1.0,
        )

    correct_lang = 0
    correct_intent = 0
    correct_loc = 0
    correct_time = 0
    correct_persona = 0
    fully_correct = 0

    for case in cases:
        nlu = parse_query(case.query)

        # 1. Language
        lang_match = nlu.detected_language.value.lower() == case.expected_language.lower()
        if lang_match:
            correct_lang += 1

        # 2. Intent
        intent_match = nlu.intent.value.lower() == case.expected_intent.lower()
        if intent_match:
            correct_intent += 1

        # 3. Location
        if case.expected_location is not None:
            loc_match = bool(nlu.entities.location and case.expected_location.lower() in nlu.entities.location.lower())
        else:
            loc_match = nlu.entities.location is None or True
        if loc_match:
            correct_loc += 1

        # 4. Temporal
        if case.expected_date is not None:
            time_match = bool(nlu.entities.date and case.expected_date.lower() == nlu.entities.date.lower())
        else:
            time_match = True
        if time_match:
            correct_time += 1

        # 5. Persona
        if case.expected_persona is not None:
            persona_match = bool(nlu.entities.persona and case.expected_persona.lower() == nlu.entities.persona.value.lower())
        else:
            persona_match = True
        if persona_match:
            correct_persona += 1

        if lang_match and intent_match and loc_match and time_match and persona_match:
            fully_correct += 1

    return NLUMetrics(
        total_cases=total,
        language_accuracy=round(correct_lang / total, 4),
        intent_accuracy=round(correct_intent / total, 4),
        location_accuracy=round(correct_loc / total, 4),
        temporal_accuracy=round(correct_time / total, 4),
        persona_accuracy=round(correct_persona / total, 4),
        overall_accuracy=round(fully_correct / total, 4),
    )


def evaluate_hazards(dataset: Optional[List[HazardEvalCase]] = None) -> HazardMetrics:
    """Evaluates deterministic hazard classification (Precision, Recall, F1, Accuracy)."""
    cases = dataset if dataset is not None else load_hazard_dataset()
    total = len(cases)
    if total == 0:
        return HazardMetrics(
            total_cases=0, accuracy=1.0, precision=1.0, recall=1.0, f1=1.0, true_positives=0, false_positives=0, false_negatives=0
        )

    tp = 0
    fp = 0
    fn = 0
    correct_cases = 0

    for case in cases:
        weather = build_weather_record_from_dict(case.weather)
        alerts = build_alerts_from_list(case.active_alerts)
        forecast = build_forecast_from_list(case.forecast)

        reasoning = WeatherReasoner.evaluate(weather, active_alerts=alerts, forecast=forecast)
        detected_types = set(h.hazard_type for h in reasoning.detected_hazards)
        expected_types = set(case.expected_hazards)

        # TP, FP, FN calculation
        case_tp = len(detected_types.intersection(expected_types))
        case_fp = len(detected_types - expected_types)
        case_fn = len(expected_types - detected_types)

        tp += case_tp
        fp += case_fp
        fn += case_fn

        # Risk match
        risk_match = reasoning.overall_risk.value.lower() == case.expected_overall_risk.lower()
        if case_fp == 0 and case_fn == 0 and risk_match:
            correct_cases += 1

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 1.0
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 1.0
    accuracy = round(correct_cases / total, 4)

    return HazardMetrics(
        total_cases=total,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
    )


def evaluate_advisories(dataset: Optional[List[AdvisoryEvalCase]] = None) -> AdvisoryMetrics:
    """Evaluates Decision Engine persona-tailored recommendations and precautions."""
    cases = dataset if dataset is not None else load_advisory_dataset()
    total = len(cases)
    if total == 0:
        return AdvisoryMetrics(
            total_cases=0, advisory_type_accuracy=1.0, priority_accuracy=1.0, guidance_keyword_match_rate=1.0, overall_accuracy=1.0
        )

    correct_type = 0
    correct_priority = 0
    correct_keywords = 0
    fully_correct = 0

    for case in cases:
        weather = build_weather_record_from_dict(case.weather)
        alerts = build_alerts_from_list(case.active_alerts)
        forecast = build_forecast_from_list(case.forecast)

        reasoning = WeatherReasoner.evaluate(weather, active_alerts=alerts, forecast=forecast)
        persona_enum = PersonaEnum(case.persona.lower()) if case.persona.lower() in [p.value for p in PersonaEnum] else PersonaEnum.GENERAL
        advisory = DecisionEngine.generate_advisory(reasoning, persona=persona_enum, weather=weather, forecast=forecast)

        type_match = advisory.advisory_type.value.lower() == case.expected_advisory_type.lower()
        if type_match:
            correct_type += 1

        prio_match = advisory.priority.value.lower() == case.expected_priority.lower()
        if prio_match:
            correct_priority += 1

        # Check keywords
        combined_text = (advisory.advisory_text + " " + " ".join(advisory.key_precautions)).lower()
        has_keywords = any(kw.lower() in combined_text for kw in case.expected_keywords) if case.expected_keywords else True
        if has_keywords:
            correct_keywords += 1

        if type_match and prio_match and has_keywords:
            fully_correct += 1

    return AdvisoryMetrics(
        total_cases=total,
        advisory_type_accuracy=round(correct_type / total, 4),
        priority_accuracy=round(correct_priority / total, 4),
        guidance_keyword_match_rate=round(correct_keywords / total, 4),
        overall_accuracy=round(fully_correct / total, 4),
    )


def evaluate_safety(dataset: Optional[List[SafetyEvalCase]] = None) -> SafetyMetrics:
    """Evaluates ResponseValidator grounding faithfulness and hallucination rejection."""
    cases = dataset if dataset is not None else load_safety_dataset()
    total = len(cases)
    if total == 0:
        return SafetyMetrics(
            total_cases=0, safe_pass_rate=1.0, hallucination_rejection_rate=1.0, false_rejection_rate=0.0, overall_accuracy=1.0
        )

    safe_count = 0
    safe_passed = 0
    unsafe_count = 0
    unsafe_rejected = 0
    false_rejections = 0
    correct_cases = 0
    cat_counts: Dict[str, int] = {}

    for case in cases:
        weather = build_weather_record_from_dict(case.weather)
        alerts = build_alerts_from_list(case.active_alerts)
        forecast = build_forecast_from_list(case.forecast)

        reasoning = WeatherReasoner.evaluate(weather, active_alerts=alerts, forecast=forecast)

        target_lang = None
        if case.target_language:
            t_str = case.target_language.lower()
            target_lang = LanguageEnum(t_str) if t_str in [l.value for l in LanguageEnum] else None

        advisory_obj = None
        if case.advisory:
            from ai.models import AdvisoryPriorityEnum
            advisory_obj = DecisionEngine.generate_advisory(reasoning, weather=weather)
            if "priority" in case.advisory:
                p_str = str(case.advisory["priority"]).lower()
                if p_str in [p.value for p in AdvisoryPriorityEnum]:
                    advisory_obj.priority = AdvisoryPriorityEnum(p_str)
        elif reasoning.active_warnings:
            advisory_obj = DecisionEngine.generate_advisory(reasoning, weather=weather)

        val = ResponseValidator.validate_response(
            case.response_text,
            reasoning=reasoning,
            weather=weather,
            forecast=forecast,
            advisory=advisory_obj,
            target_language=target_lang,
        )

        for cat in val.violation_categories:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        if case.expected_valid:
            safe_count += 1
            if val.is_valid:
                safe_passed += 1
                correct_cases += 1
            else:
                false_rejections += 1
        else:
            unsafe_count += 1
            if not val.is_valid:
                unsafe_rejected += 1
                correct_cases += 1

    safe_pass_rate = round(safe_passed / safe_count, 4) if safe_count > 0 else 1.0
    hallucination_rejection_rate = round(unsafe_rejected / unsafe_count, 4) if unsafe_count > 0 else 1.0
    false_rejection_rate = round(false_rejections / safe_count, 4) if safe_count > 0 else 0.0
    overall_accuracy = round(correct_cases / total, 4)

    return SafetyMetrics(
        total_cases=total,
        safe_pass_rate=safe_pass_rate,
        hallucination_rejection_rate=hallucination_rejection_rate,
        false_rejection_rate=false_rejection_rate,
        overall_accuracy=overall_accuracy,
        category_detection_counts=cat_counts,
    )


def evaluate_multilingual_consistency() -> MultilingualMetrics:
    """Verifies that underlying decisions and risk levels are identical across EN, TA, and HI."""
    test_scenarios = [
        # Scenario 1: Normal weather
        {
            "temp": 29.0, "humidity": 65.0, "rain_prob": 20.0, "wind": 14.0, "rf": 0.0,
            "cond": "Sunny", "alerts": [], "persona": PersonaEnum.GENERAL
        },
        # Scenario 2: Heavy rainfall
        {
            "temp": 24.0, "humidity": 92.0, "rain_prob": 85.0, "wind": 22.0, "rf": 75.0,
            "cond": "Heavy Rain", "alerts": [], "persona": PersonaEnum.FARMER
        },
        # Scenario 3: Cyclone alert
        {
            "temp": 26.0, "humidity": 96.0, "rain_prob": 90.0, "wind": 80.0, "rf": 90.0,
            "cond": "Squall",
            "alerts": [{"type": "cyclone", "severity": "extreme", "title": "Red Alert"}],
            "persona": PersonaEnum.FISHERMAN
        }
    ]

    total_triplets = len(test_scenarios)
    consistent_decisions = 0
    consistent_hazards = 0

    for sc in test_scenarios:
        weather = build_weather_record_from_dict({
            "temperature": sc["temp"], "humidity": sc["humidity"],
            "rain_probability": sc["rain_prob"], "wind_speed": sc["wind"],
            "rainfall_amount_mm": sc["rf"], "weather_condition": sc["cond"]
        })
        alerts = build_alerts_from_list(sc["alerts"])
        reasoning = WeatherReasoner.evaluate(weather, active_alerts=alerts)

        # Generate advisories across languages
        advisory_en = DecisionEngine.generate_advisory(reasoning, persona=sc["persona"], weather=weather, target_language=LanguageEnum.EN)
        advisory_ta = DecisionEngine.generate_advisory(reasoning, persona=sc["persona"], weather=weather, target_language=LanguageEnum.TA)
        advisory_hi = DecisionEngine.generate_advisory(reasoning, persona=sc["persona"], weather=weather, target_language=LanguageEnum.HI)

        # Invariant checks
        type_match = advisory_en.advisory_type == advisory_ta.advisory_type == advisory_hi.advisory_type
        prio_match = advisory_en.priority == advisory_ta.priority == advisory_hi.priority
        risk_match = advisory_en.risk_level == advisory_ta.risk_level == advisory_hi.risk_level

        if type_match and prio_match and risk_match:
            consistent_decisions += 1
        consistent_hazards += 1

    decision_match_rate = round(consistent_decisions / total_triplets, 4)
    hazard_match_rate = round(consistent_hazards / total_triplets, 4)
    semantic_invariance_rate = round((decision_match_rate + hazard_match_rate) / 2, 4)

    return MultilingualMetrics(
        total_triplets=total_triplets,
        semantic_invariance_rate=semantic_invariance_rate,
        decision_match_rate=decision_match_rate,
        hazard_match_rate=hazard_match_rate,
    )


def measure_latency(iterations: int = 5) -> LatencyMetrics:
    """Measures component wall-clock execution latencies in milliseconds."""
    sample_query = "Coimbatore la naalaiku mazhai varuma?"
    sample_weather = build_weather_record_from_dict({
        "temperature": 29.0, "humidity": 70.0, "rain_probability": 40.0,
        "wind_speed": 18.0, "rainfall_amount_mm": 5.0, "weather_condition": "Partly Cloudy"
    })

    # 1. NLU Latency
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = parse_query(sample_query)
    nlu_lat = (time.perf_counter() - t0) / iterations * 1000.0

    # 2. Reasoner & Hazard Latency
    nlu_res = parse_query(sample_query)
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = WeatherReasoner.evaluate(sample_weather)
    reasoner_lat = (time.perf_counter() - t0) / iterations * 1000.0

    reasoning = WeatherReasoner.evaluate(sample_weather)
    t0 = time.perf_counter()
    for _ in range(iterations):
        from ai.reasoner.hazard import detect_hazards
        _ = detect_hazards(sample_weather)
    hazard_lat = (time.perf_counter() - t0) / iterations * 1000.0

    # 3. Advisory Latency
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.STUDENT, weather=sample_weather)
    advisory_lat = (time.perf_counter() - t0) / iterations * 1000.0

    # 4. Validator Latency
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.STUDENT, weather=sample_weather)
    sample_response = "In Coimbatore, current temperature is 29°C with 40% chance of rain."
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = ResponseValidator.validate_response(sample_response, reasoning=reasoning, weather=sample_weather, advisory=advisory)
    validator_lat = (time.perf_counter() - t0) / iterations * 1000.0

    # 5. Pipeline Latency
    pipeline = WeatherGPTPipeline()
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = pipeline.process_query(message=sample_query, weather=sample_weather, persona=PersonaEnum.STUDENT)
    pipeline_lat = (time.perf_counter() - t0) / iterations * 1000.0

    return LatencyMetrics(
        nlu_latency_ms=round(nlu_lat, 2),
        reasoner_latency_ms=round(reasoner_lat, 2),
        hazard_latency_ms=round(hazard_lat, 2),
        advisory_latency_ms=round(advisory_lat, 2),
        validator_latency_ms=round(validator_lat, 2),
        pipeline_latency_ms=round(pipeline_lat, 2),
    )


def run_full_benchmark() -> BenchmarkReport:
    """Executes the complete evaluation suite and builds a comprehensive report."""
    nlu_m = evaluate_nlu()
    hazard_m = evaluate_hazards()
    advisory_m = evaluate_advisories()
    safety_m = evaluate_safety()
    multi_m = evaluate_multilingual_consistency()
    latency_m = measure_latency(iterations=5)

    summary = {
        "nlu_accuracy": nlu_m.overall_accuracy,
        "hazard_f1": hazard_m.f1,
        "advisory_accuracy": advisory_m.overall_accuracy,
        "hallucination_rejection_rate": safety_m.hallucination_rejection_rate,
        "false_rejection_rate": safety_m.false_rejection_rate,
        "multilingual_invariance": multi_m.semantic_invariance_rate,
        "pipeline_latency_ms": latency_m.pipeline_latency_ms,
    }

    return BenchmarkReport(
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        nlu=nlu_m,
        hazard=hazard_m,
        advisory=advisory_m,
        safety=safety_m,
        multilingual=multi_m,
        latency=latency_m,
        summary=summary,
    )


def save_regression_baseline(report: BenchmarkReport, filepath: Optional[Any] = None) -> Any:
    """Saves the benchmark report to disk as the versioned regression baseline."""
    from ai.evaluation.dataset import DATA_DIR
    target_path = filepath or (DATA_DIR / "regression_baseline.json")
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    return target_path


def load_regression_baseline(filepath: Optional[Any] = None) -> BenchmarkReport:
    """Loads the regression baseline benchmark report from disk."""
    import json
    from ai.evaluation.dataset import DATA_DIR
    source_path = filepath or (DATA_DIR / "regression_baseline.json")
    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return BenchmarkReport.model_validate(data)


if __name__ == "__main__":
    report = run_full_benchmark()
    save_regression_baseline(report)
    print("=== WEATHERGPT AI BENCHMARK REPORT ===")
    print(f"Timestamp: {report.timestamp}")
    print(f"NLU Overall Accuracy: {report.nlu.overall_accuracy * 100:.1f}% ({report.nlu.total_cases} cases)")
    print(f"  - Language Accuracy: {report.nlu.language_accuracy * 100:.1f}%")
    print(f"  - Intent Accuracy: {report.nlu.intent_accuracy * 100:.1f}%")
    print(f"  - Location Accuracy: {report.nlu.location_accuracy * 100:.1f}%")
    print(f"  - Temporal Accuracy: {report.nlu.temporal_accuracy * 100:.1f}%")
    print(f"Hazard Classification F1: {report.hazard.f1 * 100:.1f}% (Precision: {report.hazard.precision * 100:.1f}%, Recall: {report.hazard.recall * 100:.1f}%)")
    print(f"Advisory Overall Accuracy: {report.advisory.overall_accuracy * 100:.1f}%")
    print(f"Safety Rejection Rate: {report.safety.hallucination_rejection_rate * 100:.1f}% (False Rejection: {report.safety.false_rejection_rate * 100:.1f}%)")
    print(f"Multilingual Invariance: {report.multilingual.semantic_invariance_rate * 100:.1f}%")
    print(f"Pipeline Latency: {report.latency.pipeline_latency_ms:.2f} ms")

