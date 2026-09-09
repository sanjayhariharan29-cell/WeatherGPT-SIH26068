import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from ai.decision import DecisionEngine
from ai.llm import GroundedLLMGenerator
from ai.models import (
    DecisionTrace,
    DegradedStateEnum,
    EvidenceLink,
    ForecastItem,
    OfficialAlert,
    PersonaEnum,
    WeatherRecord,
)
from ai.nlu import parse_query, normalize_query
from ai.rag import retrieve_safety_guidance
from ai.reasoner import WeatherReasoner
from ai.resilience import get_circuit_breaker
from ai.validator import ResponseValidator


class WeatherGPTPipeline:
    """End-to-End AI Engine for WeatherGPT with Phase 16 Graceful Degradation."""

    def __init__(
        self,
        llm_api_key: Optional[str] = None,
        llm_circuit_breaker: Optional[Any] = None,
        rag_circuit_breaker: Optional[Any] = None,
    ):
        self.llm = GroundedLLMGenerator(api_key=llm_api_key)
        self.llm_circuit_breaker = llm_circuit_breaker or get_circuit_breaker("llm_generator")
        self.rag_circuit_breaker = rag_circuit_breaker or get_circuit_breaker("rag_retriever")

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
        request_id: Optional[str] = None,
        llm_timeout_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        """Runs the complete conversational pipeline from user text to validated answer."""
        t_start = time.perf_counter()
        forecast = forecast or []
        active_alerts = active_alerts or []
        degraded_reasons: List[str] = []
        subsystems_degraded: List[str] = []

        # 1. Input Normalization Stage
        t_in = time.perf_counter()
        cleaned_msg = normalize_query(message) if message else ""
        t_norm = (time.perf_counter() - t_in) * 1000

        # 2. Memory Resolution Stage (with failure isolation)
        t_mem = time.perf_counter()
        resolved_context_summary = context_summary
        if not resolved_context_summary and conversation_id and conversation_id != "default":
            try:
                from ai.memory import memory_manager, ContextResolver
                ctx = memory_manager.get_context(conversation_id)
                resolved = ContextResolver.resolve_query(message, context=ctx)
                resolved_context_summary = resolved.context_summary
            except Exception as mem_err:
                # Failure isolation: memory manager failure MUST NEVER crash query processing
                degraded_reasons.append(f"Memory resolution failed: {str(mem_err)}")
                subsystems_degraded.append("memory")
                resolved_context_summary = None
        t_memory = (time.perf_counter() - t_mem) * 1000

        # 3. NLU: Language detection, Intent, Entity extraction
        t0 = time.perf_counter()
        nlu = parse_query(message)
        t_nlu = (time.perf_counter() - t0) * 1000

        # Persona resolution: explicit argument overrides query entity
        resolved_persona = persona or nlu.entities.persona or PersonaEnum.GENERAL

        # 4. Weather Reasoning: Freshness, Hazards, Source agreement, Consistency Score
        t1 = time.perf_counter()
        reasoning = WeatherReasoner.evaluate(
            primary_weather=weather,
            secondary_weather=secondary_weather,
            forecast=forecast,
            active_alerts=active_alerts
        )
        t_reasoner = (time.perf_counter() - t1) * 1000

        # 5. Hazard Detection & Invariant Verification
        t_hz = time.perf_counter()
        hazard_types = [h.hazard_type for h in reasoning.detected_hazards]
        t_hazard = (time.perf_counter() - t_hz) * 1000

        # 6. Advisory Engine: Persona-tailored advice in target language
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

        # 7. RAG Safety Knowledge & Reference Retrieval (with timeout & failure isolation)
        t3 = time.perf_counter()
        safety_notes: List[str] = []
        try:
            safety_notes = retrieve_safety_guidance(hazard_types, language=target_lang.value)
        except Exception as rag_err1:
            degraded_reasons.append(f"RAG safety guidance retrieval failed: {str(rag_err1)}")
            subsystems_degraded.append("rag")
            safety_notes = []

        ref_chunks: List[Any] = []
        rag_breaker = self.rag_circuit_breaker
        try:
            from ai.rag import get_knowledge_retriever
            retriever = get_knowledge_retriever()
            search_query = f"{message} {' '.join(hazard_types)}"
            lang_filter = target_lang.value if target_lang.value in ("en", "ta") else None

            ref_chunks = rag_breaker.execute(
                retriever.retrieve,
                search_query,
                top_k=2,
                language=lang_filter,
                timeout_seconds=3.0,
                fallback_func=lambda *a, **kw: []
            )
        except Exception as rag_err2:
            ref_chunks = []
            if "rag" not in subsystems_degraded:
                degraded_reasons.append(f"RAG knowledge retrieval degraded: {str(rag_err2)}")
                subsystems_degraded.append("rag")
        t_rag = (time.perf_counter() - t3) * 1000

        # 8. Grounded LLM Generation (with circuit breaker & timeout protection)
        t4 = time.perf_counter()
        llm_fallback_triggered = False
        llm_breaker = self.llm_circuit_breaker

        # Timeout config
        if llm_timeout_seconds is not None:
            timeout_sec = llm_timeout_seconds
        else:
            llm_cfg = getattr(getattr(self.llm, "config", None), "llm", None)
            timeout_sec = getattr(llm_cfg, "timeout_seconds", 10.0) if llm_cfg else 10.0

        if not llm_breaker.can_execute():
            llm_fallback_triggered = True
            degraded_reasons.append(
                f"LLM circuit breaker is OPEN (fast-failing). Cooldown remaining: {llm_breaker.remaining_cooldown():.1f}s"
            )
            subsystems_degraded.append("llm")
            raw_answer = self.llm._generate_fallback(
                nlu=nlu,
                weather=weather,
                reasoning=reasoning,
                advisory=advisory,
                target_language=target_lang,
            )
        else:
            try:
                def _call_llm():
                    prov = getattr(self.llm, "provider", None)
                    if getattr(prov, "simulate_timeout", False):
                        raise TimeoutError("LLM provider timed out during text generation")
                    if getattr(prov, "should_fail", False):
                        if getattr(prov, "failure_exception", None):
                            raise prov.failure_exception
                        raise RuntimeError("LLM provider failed")
                    return self.llm.generate(
                        nlu=nlu,
                        weather=weather,
                        reasoning=reasoning,
                        advisory=advisory,
                        forecast=forecast,
                        safety_guidance=safety_notes,
                        reference_knowledge=ref_chunks,
                        context_summary=resolved_context_summary
                    )

                raw_answer = llm_breaker.execute(
                    _call_llm,
                    timeout_seconds=timeout_sec
                )
            except Exception as llm_err:
                llm_fallback_triggered = True
                llm_breaker.record_failure(llm_err)
                degraded_reasons.append(f"LLM generation failed: {type(llm_err).__name__} ({str(llm_err)})")
                if "llm" not in subsystems_degraded:
                    subsystems_degraded.append("llm")
                raw_answer = self.llm._generate_fallback(
                    nlu=nlu,
                    weather=weather,
                    reasoning=reasoning,
                    advisory=advisory,
                    target_language=target_lang,
                )
        t_llm = (time.perf_counter() - t4) * 1000

        # 9. Response Validation & Hallucination Guard
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
        t_validator = (time.perf_counter() - t5) * 1000

        # 10. Fallback Stage
        t_fb = time.perf_counter()
        final_answer = raw_answer
        fallback_required = not validation.is_valid or validation.fallback_required
        validator_fallback_triggered = False
        if fallback_required:
            validator_fallback_triggered = True
            degraded_reasons.append(
                f"ResponseValidator rejected response ({validation.status.value}): "
                f"{', '.join(validation.violations or validation.issues)}"
            )
            if "validator_safety" not in subsystems_degraded:
                subsystems_degraded.append("validator_safety")
            # If the LLM response violated grounding or warning constraints,
            # fall back immediately to the deterministic grounded advisory
            final_answer = self.llm._generate_fallback(
                nlu=nlu,
                weather=weather,
                reasoning=reasoning,
                advisory=advisory,
                target_language=target_lang,
            )
        t_fallback = (time.perf_counter() - t_fb) * 1000

        # 11. Final Response Assembly & Degradation Classification
        t_fr = time.perf_counter()

        # Structured Degradation State Classification (Phase 16)
        if weather is None and not reasoning.active_warnings:
            degraded_state = DegradedStateEnum.DATA_UNAVAILABLE
        elif validator_fallback_triggered:
            degraded_state = DegradedStateEnum.SAFETY_FALLBACK
        elif llm_fallback_triggered or "llm" in subsystems_degraded:
            degraded_state = DegradedStateEnum.DEGRADED_LLM
        elif "rag" in subsystems_degraded:
            degraded_state = DegradedStateEnum.DEGRADED_RAG
        elif "voice" in subsystems_degraded:
            degraded_state = DegradedStateEnum.DEGRADED_VOICE
        else:
            degraded_state = DegradedStateEnum.NORMAL

        fallback_used = (fallback_required or raw_answer != final_answer or llm_fallback_triggered)
        safety_telemetry = {
            "warning_present": len(reasoning.active_warnings) > 0,
            "hazard_present": len(reasoning.detected_hazards) > 0,
            "advisory_priority": advisory.priority.value if hasattr(advisory, "priority") else "normal",
            "validation_status": validation.status.value,
            "fallback_used": fallback_used,
            "degraded_state": degraded_state.value,
        }

        # Build Unified Structured Sub-Models (Step 20 Response Contract)
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

        t_final = (time.perf_counter() - t_fr) * 1000
        t_total = (time.perf_counter() - t_start) * 1000

        stage_latencies = {
            # Backward compatible keys:
            "nlu_ms": round(t_nlu, 2),
            "reasoner_ms": round(t_reasoner, 2),
            "advisory_ms": round(t_advisory, 2),
            "rag_ms": round(t_rag, 2),
            "llm_ms": round(t_llm, 2),
            "validator_ms": round(t_validator, 2),
            "total_pipeline_ms": round(t_total, 2),
            # Granular Phase 16 stage keys:
            "input_normalization_ms": round(t_norm, 2),
            "memory_resolution_ms": round(t_memory, 2),
            "weather_reasoning_ms": round(t_reasoner, 2),
            "hazard_detection_ms": round(t_hazard, 2),
            "advisory_engine_ms": round(t_advisory, 2),
            "llm_generation_ms": round(t_llm, 2),
            "validation_ms": round(t_validator, 2),
            "fallback_ms": round(t_fallback, 2),
            "final_response_ms": round(t_final, 2),
        }

        # Phase 19: Build structured, audit-ready EvidenceLinks and DecisionTrace
        evidence_links: List[EvidenceLink] = []
        if weather:
            evidence_links.append(
                EvidenceLink(
                    field_or_entity="weather.temperature",
                    observed_or_rule_value=f"{weather.temperature}°C",
                    source=weather.source,
                    temporal_scope="current",
                    decision_impact="Shapes thermal hazard assessment and persona comfort guidelines",
                )
            )
            if weather.humidity is not None:
                evidence_links.append(
                    EvidenceLink(
                        field_or_entity="weather.humidity",
                        observed_or_rule_value=f"{weather.humidity}%",
                        source=weather.source,
                        temporal_scope="current",
                        decision_impact="Contributes to heat index and fog/precipitation likelihood",
                    )
                )
            if weather.wind_speed is not None:
                evidence_links.append(
                    EvidenceLink(
                        field_or_entity="weather.wind_speed",
                        observed_or_rule_value=f"{weather.wind_speed} km/h",
                        source=weather.source,
                        temporal_scope="current",
                        decision_impact="Evaluated against high wind / squall safety thresholds",
                    )
                )

        for w in reasoning.active_warnings:
            w_type = getattr(w, "type", getattr(w, "warning_type", "weather_alert"))
            w_type_str = w_type.value if hasattr(w_type, "value") else str(w_type)
            w_sev = w.severity.value if hasattr(w.severity, "value") else str(w.severity)
            evidence_links.append(
                EvidenceLink(
                    field_or_entity=f"warning.{w_type_str}",
                    observed_or_rule_value=f"Severity: {w_sev}",
                    source=getattr(w, "source", "IMD"),
                    temporal_scope="active_warning",
                    decision_impact="Mandatory safety override - warning precautions prioritized over general advice",
                )
            )

        for h in reasoning.detected_hazards:
            h_type = h.hazard_type.value if hasattr(h.hazard_type, "value") else str(h.hazard_type)
            h_sev = h.severity.value if hasattr(h.severity, "value") else str(h.severity)
            h_details = getattr(h, "details", "Hazard detected")
            evidence_links.append(
                EvidenceLink(
                    field_or_entity=f"hazard.{h_type}",
                    observed_or_rule_value=f"Severity: {h_sev}",
                    source="WeatherReasoner.HazardEngine",
                    temporal_scope=getattr(h, "current_or_forecast", "current"),
                    decision_impact=f"Triggered deterministic safety rule: {h_details}",
                )
            )

        evidence_basis = [
            f"Observed in {reasoning.location}: {weather_summary}" if weather_summary else f"Evaluation for {reasoning.location}",
            f"Official Warnings: {len(reasoning.active_warnings)} active",
            f"Hazards Detected: {len(reasoning.detected_hazards)}",
            f"Target Persona: {resolved_persona.value}",
        ]

        primary_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_details = None
        if primary_warning:
            pw_type = getattr(primary_warning, "type", getattr(primary_warning, "warning_type", "alert"))
            warning_details = {
                "warning_type": pw_type.value if hasattr(pw_type, "value") else str(pw_type),
                "severity": primary_warning.severity.value if hasattr(primary_warning.severity, "value") else str(primary_warning.severity),
                "source": getattr(primary_warning, "source", "IMD"),
                "headline": getattr(primary_warning, "title", getattr(primary_warning, "headline", "")),
            }

        decision_trace = DecisionTrace(
            trace_id=f"dt_{request_id}",
            evaluated_at=datetime.now(timezone.utc),
            query_summary=(cleaned_msg or message or "")[:120],
            resolved_location=reasoning.location,
            resolved_time_window=getattr(nlu.entities, "time", None) or getattr(nlu.entities, "date", None) or "current",
            detected_intent=nlu.intent.value,
            persona=resolved_persona.value,
            language=target_lang.value,
            data_freshness=reasoning.freshness.value if hasattr(reasoning.freshness, "value") else str(reasoning.freshness),
            data_completeness=reasoning.data_complete,
            source_agreement=reasoning.source_agreement.value if hasattr(reasoning.source_agreement, "value") else str(reasoning.source_agreement),
            official_warning_status="ACTIVE_WARNING" if reasoning.active_warnings else "NONE",
            official_warning_details=warning_details,
            hazards_detected=hazards_list,
            advisory_category=advisory.advisory_type.value if hasattr(advisory, "advisory_type") else "general",
            advisory_action_class=advisory.priority.value if hasattr(advisory, "priority") else "normal",
            evidence_basis=evidence_basis,
            evidence_links=evidence_links,
            validation_status=validation.status.value,
            fallback_used=fallback_used,
            degraded_state=degraded_state.value,
            final_response_status="VALIDATED" if validation.is_valid else "FALLBACK_SUBSTITUTED",
        )

        # Return Canonical Payload conforming to docs/08_Api_Contracts.md & Phase 16/19
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
                "consistency_score": reasoning.consistency_score,
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
                "issues": validation.issues,
            },
            "safety_telemetry": safety_telemetry,
            "fallback_used": fallback_used,
            "stage_latencies_ms": stage_latencies,
            "degraded_state": degraded_state.value,
            "degradation": {
                "state": degraded_state.value,
                "reasons": degraded_reasons,
                "circuit_breaker_open": llm_breaker.is_open or rag_breaker.is_open,
                "subsystems_degraded": subsystems_degraded,
            },
            "decision_trace": decision_trace.to_debug_dict(),
            "decision_trace_model": decision_trace,
        }

    # Canonical entrypoint alias (Phase 15 Step 4)
    run = process_query

