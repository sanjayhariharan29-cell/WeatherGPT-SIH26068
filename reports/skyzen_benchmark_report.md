# SkyZen AI & Meteorological System Evaluation Benchmark Report

**Generated:** 2026-09-25T16:58:53.679230+00:00
**Environment:** Windows-11-10.0.26200-SP0, Python 3.14.3

> [!NOTE]
> DISCLAIMER: Benchmark results recorded under controlled local test conditions with deterministic inputs. These metrics validate software regression invariance and architecture readiness; they do NOT claim real-world production accuracy.

## Evaluated Metrics (12/12)

| Metric Name | Sample Size | Value | Unit | Definition |
| :--- | :--- | :--- | :--- | :--- |
| `intent_recognition_accuracy` | 16 | **62.5%** | percent | Percentage of test queries where NLU parsed intent correctly matched the expected intent or domain synonym. |
| `entity_extraction_accuracy` | 22 | **100.0%** | percent | Accuracy of extracting named geographic locations, temporal targets, and user personas from natural language queries. |
| `language_detection_accuracy` | 16 | **100.0%** | percent | Accuracy of identifying user input language (en, ta, hi, te) using script detection and linguistic n-grams. |
| `grounding_correctness` | 16 | **93.75%** | percent | Rate of generated meteorological advisory statements that faithfully conform to verified ground-truth observations without numerical hallucination. |
| `response_validation_failures` | 3 | **66.67%** | percent | Proportion of hallucinated or contradicting synthetic adversarial probes correctly intercepted and rejected by ResponseValidator. |
| `official_warning_contradiction_rate` | 6 | **0.0%** | percent | Percentage of generated responses or risk classifications that downplay, contradict, or cancel active official IMD/disaster warnings. |
| `api_response_latency` | 40 | **p50: 0.0ms, p95: 0.01ms** | milliseconds | Response latency across core adapter normalization and service logic measured at p50, p95, mean, and max in milliseconds. |
| `end_to_end_response_latency` | 25 | **p50: 1.14ms, p95: 1.58ms** | milliseconds | Deterministic full-pipeline latency (NLU -> Meteorological Reasoning -> Persona Decision -> Safety Validation) in milliseconds. |
| `provider_fallback_success` | 15 | **100.0%** | percent | Percentage of simulated primary provider timeouts where the fallback provider served valid weather data without system failure. |
| `alert_targeting_correctness` | 5 | **100.0%** | percent | Accuracy of spatial and district bounding logic ensuring warnings are targeted to citizens in affected zones and omitted outside. |
| `notification_delivery_success` | 4 | **100.0%** | percent | Delivery dispatch success rate verifying active tokens receive alerts while expired or missing tokens are safely skipped without crash. |
| `multilingual_response_consistency` | 4 | **100.0%** | percent | Semantic and risk recommendation invariance across identical queries posed in English, Tamil, Hindi, and Telugu. |
