"""Master WeatherGPT AI Pipeline.

Orchestrates NLU, Meteorological Reasoning, Decision Advisories,
RAG Safety Retrieval, Grounded LLM Generation, and Anti-Hallucination Validation.
Aligned with docs/05_Architectuaral.md and docs/08_Api_Contracts.md.
"""

from typing import Any, Dict, List, Optional
from ai.decision import DecisionEngine
from ai.llm import GroundedLLMGenerator
from ai.models import (
    ForecastItem,
    OfficialAlert,
    PersonaEnum,
    WeatherRecord,
)
from ai.nlu import parse_query
from ai.rag import retrieve_safety_guidance
from ai.reasoner import WeatherReasoner
from ai.validator import ResponseValidator


class WeatherGPTPipeline:
    """End-to-End AI Engine for WeatherGPT."""

    def __init__(self, llm_api_key: Optional[str] = None):
        self.llm = GroundedLLMGenerator(api_key=llm_api_key)

    def process_query(
        self,
        message: str,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        active_alerts: Optional[List[OfficialAlert]] = None,
        secondary_weather: Optional[WeatherRecord] = None,
        persona: Optional[PersonaEnum] = None,
        conversation_id: str = "default",
        target_language: Optional[Any] = None,
        context_summary: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs the complete conversational pipeline from user text to validated answer."""
        forecast = forecast or []
        active_alerts = active_alerts or []

        import time
        t_start = time.perf_counter()

        # 1. NLU: Language detection, Intent, Entity extraction
        t0 = time.perf_counter()
        nlu = parse_query(message)
        t_nlu = (time.perf_counter() - t0) * 1000

        # Persona resolution: explicit argument overrides query entity
        resolved_persona = persona or nlu.entities.persona or PersonaEnum.GENERAL

        # 2. Weather Reasoning: Freshness, Hazards, Source agreement, Consistency Score
        t1 = time.perf_counter()
        reasoning = WeatherReasoner.evaluate(
            primary_weather=weather,
            secondary_weather=secondary_weather,
            forecast=forecast,
            active_alerts=active_alerts
        )
        t_reasoner = (time.perf_counter() - t1) * 1000

        # 3. Decision Engine: Persona-tailored advice in target language
        t2 = time.perf_counter()
        from ai.llm.multilingual import resolve_target_language
        from ai.models import LanguageEnum
        explicit_pref = None
        if isinstance(target_language, str):
            try:
                explicit_pref = LanguageEnum(target_language.lower())
            except Exception:
                explicit_pref = None
        elif isinstance(target_language, LanguageEnum):
            explicit_pref = target_language

        target_lang = resolve_target_language(
            nlu_lang=nlu.detected_language,
            query_text=message,
            explicit_preference=explicit_pref
        )

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=resolved_persona,
            target_language=target_lang,
            nlu=nlu,
            weather=weather,
            forecast=forecast
        )
        t_advisory = (time.perf_counter() - t2) * 1000

        # 4. RAG Safety Knowledge & Reference Retrieval
        t3 = time.perf_counter()
        hazard_types = [h.hazard_type for h in reasoning.detected_hazards]
        safety_notes = retrieve_safety_guidance(hazard_types, language=target_lang.value)
        
        from ai.rag import get_knowledge_retriever
        retriever = get_knowledge_retriever()
        search_query = f"{message} {' '.join(hazard_types)}"
        lang_filter = target_lang.value if target_lang.value in ("en", "ta") else None
        ref_chunks = retriever.retrieve(search_query, top_k=2, language=lang_filter)
        t_rag = (time.perf_counter() - t3) * 1000

        # 5. Grounded LLM Generation
        t4 = time.perf_counter()
        llm_fallback_triggered = False
        try:
            raw_answer = self.llm.generate(
                nlu=nlu,
                weather=weather,
                reasoning=reasoning,
                advisory=advisory,
                forecast=forecast,
                safety_guidance=safety_notes,
                reference_knowledge=ref_chunks,
                context_summary=context_summary
            )
        except Exception:
            llm_fallback_triggered = True
            raw_answer = self.llm._generate_fallback(
                nlu=nlu,
                weather=weather,
                reasoning=reasoning,
                advisory=advisory,
                target_language=target_lang,
            )
        t_llm = (time.perf_counter() - t4) * 1000

        # 6. Response Validation & Hallucination Guard
        t5 = time.perf_counter()
        validation = ResponseValidator.validate_response(
            response_text=raw_answer,
            reasoning=reasoning,
            weather=weather,
            forecast=forecast,
            advisory=advisory,
            nlu=nlu,
            target_language=target_lang,
        )

        final_answer = raw_answer
        fallback_required = not validation.is_valid or validation.fallback_required
        if fallback_required:
            # If the LLM response violated grounding or warning constraints,
            # fall back immediately to the deterministic grounded advisory
            final_answer = self.llm._generate_fallback(
                nlu=nlu,
                weather=weather,
                reasoning=reasoning,
                advisory=advisory,
                target_language=target_lang,
            )
        t_validator = (time.perf_counter() - t5) * 1000
        t_total = (time.perf_counter() - t_start) * 1000

        # 7. Record Structured Safety Telemetry & Invariants (Phase 14 & Phase 15)
        fallback_used = (fallback_required or raw_answer != final_answer or llm_fallback_triggered)
        safety_telemetry = {
            "warning_present": len(reasoning.active_warnings) > 0,
            "hazard_present": len(reasoning.detected_hazards) > 0,
            "advisory_priority": advisory.priority.value if hasattr(advisory, "priority") else "normal",
            "validation_status": validation.status.value,
            "fallback_used": fallback_used,
        }

        stage_latencies = {
            "nlu_ms": round(t_nlu, 2),
            "reasoner_ms": round(t_reasoner, 2),
            "advisory_ms": round(t_advisory, 2),
            "rag_ms": round(t_rag, 2),
            "llm_ms": round(t_llm, 2),
            "validator_ms": round(t_validator, 2),
            "total_pipeline_ms": round(t_total, 2)
        }

        # 8. Build Unified Structured Sub-Models (Step 20 Response Contract)
        weather_summary = {
            "temperature": weather.temperature,
            "humidity": weather.humidity,
            "rain_probability": weather.rain_probability,
            "wind_speed": weather.wind_speed,
            "condition": weather.weather_condition,
            "rainfall_mm": weather.rainfall_amount_mm or 0.0
        } if weather else None

        warnings_list = [
            {
                "type": w.type,
                "severity": w.severity.value if hasattr(w.severity, "value") else str(w.severity),
                "title": w.title,
                "description": w.description,
                "source": w.source,
                "issued_at": w.issued_at.isoformat() if hasattr(w, "issued_at") and w.issued_at else None,
                "expires_at": w.expires_at.isoformat() if hasattr(w, "expires_at") and w.expires_at else None,
                "affected_locations": w.affected_locations if hasattr(w, "affected_locations") else []
            }
            for w in reasoning.active_warnings
        ]

        hazards_list = [
            {
                "hazard_type": h.hazard_type,
                "severity": h.severity.value if hasattr(h.severity, "value") else str(h.severity),
                "details": h.details,
                "is_official_warning": h.is_official_warning,
                "current_or_forecast": getattr(h, "current_or_forecast", "current")
            }
            for h in reasoning.detected_hazards
        ]

        advisory_dict = {
            "priority": advisory.priority.value if hasattr(advisory, "priority") else "normal",
            "type": advisory.advisory_type.value if hasattr(advisory, "advisory_type") else "general",
            "action_summary": advisory.advisory_text if hasattr(advisory, "advisory_text") else str(advisory),
            "precautions": advisory.key_precautions if hasattr(advisory, "key_precautions") else [],
            "target_persona": resolved_persona.value,
            "language": target_lang.value
        }

        data_quality_dict = {
            "consistency_score": reasoning.consistency_score,
            "freshness": reasoning.freshness.value if hasattr(reasoning.freshness, "value") else str(reasoning.freshness),
            "data_age_minutes": reasoning.data_age_minutes,
            "data_complete": reasoning.data_complete,
            "missing_fields": reasoning.missing_fields,
            "source_agreement": reasoning.source_agreement.value if hasattr(reasoning.source_agreement, "value") else str(reasoning.source_agreement)
        }

        # 9. Return Canonical Payload conforming to docs/08_Api_Contracts.md & Step 20
        return {
            "request_id": request_id,
            "conversation_id": conversation_id,
            "answer": final_answer,
            "language": nlu.detected_language.value,
            "intent": nlu.intent.value,
            "location": reasoning.location,
            "persona": resolved_persona.value,
            "risk": {
                "level": reasoning.overall_risk.value,
                "consistency": reasoning.source_agreement.value,
                "consistency_score": reasoning.consistency_score
            },
            "weather": weather_summary,
            "weather_summary": weather_summary,
            "forecast_count": len(forecast),
            "warnings": warnings_list,
            "alerts": warnings_list,
            "hazards": hazards_list,
            "advisory": advisory_dict,
            "source": ", ".join(reasoning.sources_used) if reasoning.sources_used else "None",
            "sources": reasoning.sources_used,
            "data_quality": data_quality_dict,
            "data_timestamp": weather.retrieved_at.isoformat() if weather else reasoning.evaluated_at.isoformat(),
            "validation": {
                "passed": validation.is_valid,
                "status": validation.status.value,
                "violations": validation.violations,
                "warnings": validation.warnings,
                "checked_fields": validation.checked_fields,
                "issues": validation.issues
            },
            "safety_telemetry": safety_telemetry,
            "fallback_used": fallback_used,
            "stage_latencies_ms": stage_latencies
        }

    # Canonical entrypoint alias (Phase 15 Step 4)
    run = process_query

