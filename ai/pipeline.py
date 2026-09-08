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
        context_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs the complete conversational pipeline from user text to validated answer."""
        forecast = forecast or []
        active_alerts = active_alerts or []

        # 1. NLU: Language detection, Intent, Entity extraction
        nlu = parse_query(message)

        # Persona resolution: explicit argument overrides query entity
        resolved_persona = persona or nlu.entities.persona or PersonaEnum.GENERAL

        # 2. Weather Reasoning: Freshness, Hazards, Source agreement, Consistency Score
        reasoning = WeatherReasoner.evaluate(
            primary_weather=weather,
            secondary_weather=secondary_weather,
            forecast=forecast,
            active_alerts=active_alerts
        )

        # 3. Decision Engine: Persona-tailored advice in target language
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

        # 4. RAG Safety Knowledge & Reference Retrieval
        hazard_types = [h.hazard_type for h in reasoning.detected_hazards]
        safety_notes = retrieve_safety_guidance(hazard_types, language=target_lang.value)
        
        from ai.rag import get_knowledge_retriever
        retriever = get_knowledge_retriever()
        search_query = f"{message} {' '.join(hazard_types)}"
        lang_filter = target_lang.value if target_lang.value in ("en", "ta") else None
        ref_chunks = retriever.retrieve(search_query, top_k=2, language=lang_filter)

        # 5. Grounded LLM Generation
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
            raw_answer = self.llm._generate_fallback(
                nlu=nlu,
                weather=weather,
                reasoning=reasoning,
                advisory=advisory,
                target_language=target_lang,
            )

        # 6. Response Validation & Hallucination Guard
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
        if not validation.is_valid or validation.fallback_required:
            # If the LLM response violated grounding or warning constraints,
            # fall back immediately to the deterministic grounded advisory
            final_answer = self.llm._generate_fallback(
                nlu=nlu,
                weather=weather,
                reasoning=reasoning,
                advisory=advisory,
                target_language=target_lang,
            )

        # 7. Record Structured Safety Telemetry (Phase 14 Step 18)
        fallback_used = (not validation.is_valid or validation.fallback_required or raw_answer != final_answer)
        safety_telemetry = {
            "warning_present": len(reasoning.active_warnings) > 0,
            "hazard_present": len(reasoning.detected_hazards) > 0,
            "advisory_priority": advisory.priority.value if hasattr(advisory, "priority") else "normal",
            "validation_status": validation.status.value,
            "fallback_used": fallback_used,
        }

        # 8. Return payload conforming to docs/08_Api_Contracts.md:230 & Phase 14
        return {
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
            "source": ", ".join(reasoning.sources_used) if reasoning.sources_used else "None",
            "data_timestamp": weather.retrieved_at.isoformat() if weather else reasoning.evaluated_at.isoformat(),
            "validation": {
                "passed": validation.is_valid,
                "status": validation.status.value,
                "violations": validation.violations,
                "warnings": validation.warnings,
                "checked_fields": validation.checked_fields,
                "issues": validation.issues
            },
            "safety_telemetry": safety_telemetry
        }
