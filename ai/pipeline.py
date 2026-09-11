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
    HistoricalWeatherDataset,
    WeatherDataType,
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
        llm_timeout_seconds: Optional[float] = None,
        historical_weather: Optional[HistoricalWeatherDataset] = None,
        secondary_forecast: Optional[List[ForecastItem]] = None
    ) -> Dict[str, Any]:
        """Runs the complete conversational pipeline from user text to validated answer."""
        t_start = time.perf_counter()
        forecast = forecast or []
        raw_alerts = active_alerts
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
        resolved_mem_location = None
        turn_analysis = None
        if conversation_id and conversation_id != "default":
            try:
                from ai.memory import memory_manager, ContextResolver, state_service
                if ContextResolver.is_reset_query(message):
                    memory_manager.reset_context(conversation_id)
                    state_service.reset_state(conversation_id)
                cur_state = state_service.get_state(conversation_id)
                turn_analysis = state_service.analyze_turn(message, cur_state)
                if not resolved_context_summary:
                    resolved_context_summary = turn_analysis.context_summary
                if turn_analysis.resolved_location and turn_analysis.resolved_location != "Unspecified":
                    resolved_mem_location = turn_analysis.resolved_location
                else:
                    ctx = memory_manager.get_context(conversation_id)
                    resolved = ContextResolver.resolve_query(message, context=ctx)
                    if resolved.resolved_location:
                        resolved_mem_location = resolved.resolved_location
                    elif ctx and ctx.location:
                        resolved_mem_location = ctx.location
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

        if turn_analysis:
            if turn_analysis.resolved_departure_time and not getattr(nlu.entities, "departure_time", None):
                nlu.entities.departure_time = turn_analysis.resolved_departure_time
            if turn_analysis.resolved_return_time and not getattr(nlu.entities, "return_time", None):
                nlu.entities.return_time = turn_analysis.resolved_return_time
            if turn_analysis.resolved_location and (not nlu.entities.location or nlu.entities.location == "Unspecified"):
                nlu.entities.location = turn_analysis.resolved_location
            if turn_analysis.resolved_date and not getattr(nlu.entities, "date", None):
                nlu.entities.date = turn_analysis.resolved_date
            if turn_analysis.resolved_time and not getattr(nlu.entities, "time", None):
                nlu.entities.time = turn_analysis.resolved_time
            if turn_analysis.resolved_activity and not getattr(nlu.entities, "activity", None):
                nlu.entities.activity = turn_analysis.resolved_activity
            if turn_analysis.resolved_transport_mode and not getattr(nlu.entities, "transport_mode", None):
                nlu.entities.transport_mode = turn_analysis.resolved_transport_mode
            if turn_analysis.resolved_intent:
                from ai.models import IntentEnum
                try:
                    nlu.intent = IntentEnum(turn_analysis.resolved_intent)
                except Exception:
                    pass

        # Persona resolution: explicit argument overrides query entity
        resolved_persona = persona or nlu.entities.persona or PersonaEnum.GENERAL

        # 4. Weather Reasoning: Freshness, Hazards, Source agreement, Consistency Score
        t1 = time.perf_counter()
        reasoning = WeatherReasoner.evaluate(
            primary_weather=weather,
            secondary_weather=secondary_weather,
            forecast=forecast,
            active_alerts=raw_alerts,
            secondary_forecast=secondary_forecast
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
                historical_weather=historical_weather,
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
                        context_summary=resolved_context_summary,
                        target_language=target_lang,
                        historical_weather=historical_weather,
                    )

                raw_answer = llm_breaker.execute(
                    _call_llm,
                    timeout_seconds=timeout_sec
                )
                if getattr(self.llm, "last_is_fallback", False):
                    llm_fallback_triggered = True
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
                    historical_weather=historical_weather,
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
            historical_weather=historical_weather,
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
                historical_weather=historical_weather,
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
        obs_timestamp = weather.retrieved_at.isoformat() if (weather and hasattr(weather, "retrieved_at") and weather.retrieved_at) else datetime.now(timezone.utc).isoformat()
        if weather:
            evidence_links.append(
                EvidenceLink(
                    field_or_entity="weather.temperature",
                    observed_or_rule_value=f"{weather.temperature}°C",
                    source=weather.source,
                    temporal_scope="current",
                    decision_impact="Shapes thermal hazard assessment and persona comfort guidelines",
                    timestamp=obs_timestamp,
                    reason_code="TELEMETRY_OBSERVED",
                    reference_type="observation",
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
                        timestamp=obs_timestamp,
                        reason_code="TELEMETRY_OBSERVED",
                        reference_type="observation",
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
                        timestamp=obs_timestamp,
                        reason_code="TELEMETRY_OBSERVED",
                        reference_type="observation",
                    )
                )

        if forecast:
            for fc in forecast[:3]:
                fc_dt = getattr(fc, "forecast_time", None) or getattr(fc, "date", "upcoming")
                fc_dt_str = fc_dt.isoformat() if hasattr(fc_dt, "isoformat") else str(fc_dt)
                fc_cond = getattr(fc, "condition", getattr(fc, "summary", "forecast"))
                fc_temp = getattr(fc, "temperature", getattr(fc, "temp_max", None))
                val_str = f"{fc_temp}°C, {fc_cond}" if fc_temp is not None else str(fc_cond)
                evidence_links.append(
                    EvidenceLink(
                        field_or_entity="weather.forecast",
                        observed_or_rule_value=val_str,
                        source=getattr(fc, "source", "IMD"),
                        temporal_scope="forecast",
                        decision_impact="Outlook trend informing planning and multi-hour advisory",
                        timestamp=fc_dt_str,
                        reason_code="FORECAST_OUTLOOK",
                        reference_type="forecast",
                    )
                )

        for w in reasoning.active_warnings:
            w_type = getattr(w, "type", getattr(w, "warning_type", "weather_alert"))
            w_type_str = w_type.value if hasattr(w_type, "value") else str(w_type)
            w_sev = w.severity.value if hasattr(w.severity, "value") else str(w.severity)
            w_ts = getattr(w, "issued_at", None) or getattr(w, "timestamp", None)
            w_ts_str = w_ts.isoformat() if hasattr(w_ts, "isoformat") else (str(w_ts) if w_ts else obs_timestamp)
            evidence_links.append(
                EvidenceLink(
                    field_or_entity=f"warning.{w_type_str}",
                    observed_or_rule_value=f"Severity: {w_sev}",
                    source=getattr(w, "source", "IMD"),
                    temporal_scope="active_warning",
                    decision_impact="Mandatory safety override - warning precautions prioritized over general advice",
                    timestamp=w_ts_str,
                    reason_code="OFFICIAL_WARNING",
                    reference_type="alert",
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
                    timestamp=obs_timestamp,
                    reason_code=f"HAZARD_{h_type.upper()}",
                    reference_type="hazard_rule",
                )
            )

        if advisory:
            adv_cat = advisory.advisory_type.value if hasattr(advisory, "advisory_type") else "general"
            adv_prio = advisory.priority.value if hasattr(advisory, "priority") else "normal"
            evidence_links.append(
                EvidenceLink(
                    field_or_entity=f"advisory.{adv_cat}",
                    observed_or_rule_value=f"Priority: {adv_prio}",
                    source="AdvisoryEngine",
                    temporal_scope="advisory",
                    decision_impact=f"Deterministic actionable guidance for {resolved_persona.value} persona",
                    timestamp=obs_timestamp,
                    reason_code=f"ADVISORY_{adv_cat.upper()}",
                    reference_type="advisory_rule",
                )
            )

        effective_location = reasoning.location if reasoning.location != "Unknown" else (resolved_mem_location or getattr(nlu.entities, "location", None) or "Unknown")

        evidence_basis = [
            f"Observed in {effective_location}: {weather_summary}" if weather_summary else f"Evaluation for {effective_location}",
            f"Official Warnings: {len(reasoning.active_warnings)} active",
            f"Hazards Detected: {len(reasoning.detected_hazards)}",
            f"Target Persona: {resolved_persona.value}",
        ]

        if resolved_context_summary:
            evidence_basis.append(f"Conversational context resolved: {resolved_context_summary}")
            evidence_links.append(
                EvidenceLink(
                    field_or_entity="memory.context",
                    observed_or_rule_value=resolved_context_summary[:120],
                    source="ConversationMemory",
                    temporal_scope="recent_turn",
                    decision_impact="Resolves conversational references, pronouns, or antecedent location/time",
                    timestamp=obs_timestamp,
                    reason_code="CONVERSATION_MEMORY_RESOLVED",
                    reference_type="observation",
                )
            )

        primary_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        if primary_warning:
            pw_type = getattr(primary_warning, "type", getattr(primary_warning, "warning_type", "alert"))
            pw_issued = getattr(primary_warning, "issued_at", None)
            pw_valid_from = getattr(primary_warning, "valid_from", None)
            pw_expires = getattr(primary_warning, "expires_at", None)
            warning_details = {
                "exists": True,
                "source": getattr(primary_warning, "source", "IMD"),
                "id": getattr(primary_warning, "id", None),
                "warning_type": pw_type.value if hasattr(pw_type, "value") else str(pw_type),
                "severity": primary_warning.severity.value if hasattr(primary_warning.severity, "value") else str(primary_warning.severity),
                "title": getattr(primary_warning, "title", getattr(primary_warning, "headline", "")),
                "affected_area": (getattr(primary_warning, "affected_locations", []) or [effective_location])[0],
                "affected_locations": getattr(primary_warning, "affected_locations", [effective_location]),
                "issued_at": pw_issued.isoformat() if hasattr(pw_issued, "isoformat") else str(pw_issued or ""),
                "valid_from": pw_valid_from.isoformat() if hasattr(pw_valid_from, "isoformat") else (str(pw_valid_from) if pw_valid_from else None),
                "expires_at": pw_expires.isoformat() if hasattr(pw_expires, "isoformat") else str(pw_expires or ""),
                "status": getattr(primary_warning, "status", "ACTIVE"),
                "validation_state": "VALID",
                "instructions": getattr(primary_warning, "instructions", None),
                "affected_final_recommendation": True,
            }
        else:
            warning_details = {
                "exists": False,
                "source": "IMD",
                "status": "NONE",
                "validation_state": "NO_ACTIVE_WARNING",
                "affected_final_recommendation": False,
            }

        # Phase 6: Formulate Structured Weather Signals & Signals Dict
        rain_prob = float(getattr(weather, "rain_probability", 0.0) or 0.0) if weather else 0.0
        rain_amt = float(getattr(weather, "rain_amount", 0.0) or 0.0) if weather else 0.0
        weather_cond = str(getattr(weather, "weather_condition", "Clear") or "Clear") if weather else "Unknown"
        forecast_rain_expected = any(float(getattr(fc, "rain_probability", 0) or 0) > 40.0 for fc in forecast) if forecast else False
        is_rain_expected = rain_prob > 40.0 or forecast_rain_expected or any("rain" in getattr(h, "hazard_type", "").lower() for h in reasoning.detected_hazards)

        rainfall_indicators = {
            "probability_percent": rain_prob,
            "amount_mm": rain_amt,
            "condition": weather_cond,
            "rain_expected": is_rain_expected,
        }

        temperature_data = {
            "current_c": getattr(weather, "temperature", None) if weather else None,
            "feels_like_c": getattr(weather, "feels_like", None) or (getattr(weather, "temperature", None) if weather else None),
            "unit": "°C",
        }

        wind_data = {
            "speed_kmh": getattr(weather, "wind_speed", None) if weather else None,
            "gusts_kmh": getattr(weather, "wind_gust", None) if weather else None,
            "unit": "km/h",
        }

        official_warnings_list = []
        for alert in reasoning.active_warnings:
            al_type = getattr(alert, "type", getattr(alert, "warning_type", "alert"))
            al_type_str = al_type.value if hasattr(al_type, "value") else str(al_type)
            al_sev = alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)
            al_iss = getattr(alert, "issued_at", None)
            al_vf = getattr(alert, "valid_from", None)
            al_exp = getattr(alert, "expires_at", None)
            official_warnings_list.append({
                "id": getattr(alert, "id", None),
                "type": al_type_str,
                "severity": al_sev,
                "title": getattr(alert, "title", getattr(alert, "headline", "Weather Warning")),
                "description": getattr(alert, "description", ""),
                "instructions": getattr(alert, "instructions", None),
                "source": getattr(alert, "source", "IMD"),
                "source_url": getattr(alert, "source_url", None),
                "issued_at": al_iss.isoformat() if hasattr(al_iss, "isoformat") else str(al_iss or ""),
                "valid_from": al_vf.isoformat() if hasattr(al_vf, "isoformat") else (str(al_vf) if al_vf else None),
                "expires_at": al_exp.isoformat() if hasattr(al_exp, "isoformat") else str(al_exp or ""),
                "affected_locations": getattr(alert, "affected_locations", []),
                "status": getattr(alert, "status", "ACTIVE"),
                "version": getattr(alert, "version", 1),
            })

        c_score = reasoning.consistency_score if reasoning.consistency_score is not None else 0
        conf_lvl = getattr(reasoning, "confidence_level", None)
        conf_lvl_str = conf_lvl.value if hasattr(conf_lvl, "value") else (str(conf_lvl) if conf_lvl else None)
        if conf_lvl_str:
            confidence_indicator = conf_lvl_str.capitalize()
        elif c_score >= 75:
            confidence_indicator = "High"
            conf_lvl_str = "HIGH"
        elif c_score >= 45:
            confidence_indicator = "Medium"
            conf_lvl_str = "MEDIUM"
        else:
            confidence_indicator = "Low"
            conf_lvl_str = "LOW"

        resolved_period = getattr(nlu.entities, "time", None) or getattr(nlu.entities, "date", None) or "current"
        persona_context = {
            "persona": resolved_persona.value,
            "location": effective_location,
            "forecast_period": resolved_period,
            "intent": nlu.intent.value,
        }
        final_recommendation = getattr(advisory, "headline", None) or (getattr(advisory, "advisory_text", "")[:120] if getattr(advisory, "advisory_text", None) else final_answer[:120])

        # Formulate Deterministic Explanation Points ("Why SkyZen recommends this")
        explanation_points: List[str] = []

        # 1. Rain / Weather Expectation
        if is_rain_expected:
            if rain_prob > 0:
                explanation_points.append(f"Rain expected during your travel period ({rain_prob:.0f}% precipitation probability)")
            else:
                explanation_points.append("Precipitation or wet conditions expected during your travel period")
        else:
            explanation_points.append(f"No significant rain expected for your selected time window ({weather_cond})")

        # 2. Source Agreement
        agreement_val = reasoning.source_agreement.value if hasattr(reasoning.source_agreement, "value") else str(reasoning.source_agreement)
        if agreement_val in ("high", "consistent"):
            sources_str = ", ".join(reasoning.sources_used) if reasoning.sources_used else "IMD & Open-Meteo"
            explanation_points.append(f"Multiple sources agree on forecast consistency ({sources_str})")
        elif agreement_val == "single_source":
            src_name = reasoning.sources_used[0] if reasoning.sources_used else "IMD"
            explanation_points.append(f"Authoritative ground-truth data verified from {src_name}")
        elif agreement_val == "moderate":
            explanation_points.append("Forecast sources show moderate agreement across temperature and precipitation")
        else:
            explanation_points.append("Variance detected across weather providers; advisory tuned with extra safety margin")

        # 3. Official Warning Status
        if reasoning.active_warnings:
            warn_titles = [getattr(w, "title", "Alert") for w in reasoning.active_warnings]
            explanation_points.append(f"Official IMD Warning active: {', '.join(warn_titles[:2])}")
        else:
            explanation_points.append("No active severe warning")

        # 4. Persona Context Guidance
        if resolved_persona.value == "student":
            explanation_points.append("Commute and college travel timing factored into recommendation")
        elif resolved_persona.value == "farmer":
            explanation_points.append("Agricultural spraying, irrigation, and field guidance factored into recommendation")
        elif resolved_persona.value == "fisherman":
            explanation_points.append("Coastal squall and sea-safety criteria factored into recommendation")
        elif resolved_persona.value == "commuter":
            explanation_points.append("Road safety and transit commute factors evaluated")
        elif resolved_persona.value in ("traveller", "traveler"):
            explanation_points.append("Travel route conditions and outdoor planning evaluated")

        # 5. Hazard Signals (if monitored)
        if reasoning.detected_hazards:
            hz_names = [h.hazard_type.replace('_', ' ').title() for h in reasoning.detected_hazards[:2]]
            explanation_points.append(f"Hazard signals monitored: {', '.join(hz_names)}")

        # Build strict Data Type Tags and Historical Context for Trace (Phase 8 Requirement 1)
        data_types_used = []
        if historical_weather:
            data_types_used.append(WeatherDataType.HISTORICAL.value)
        if weather and weather.source != "DATA_UNAVAILABLE":
            data_types_used.append(WeatherDataType.CURRENT.value)
        if forecast:
            data_types_used.append(WeatherDataType.FORECAST.value)
        if active_alerts:
            data_types_used.append(WeatherDataType.OFFICIAL_WARNING.value)

        historical_context_dict = None
        if historical_weather:
            historical_context_dict = {
                "data_type": WeatherDataType.HISTORICAL.value,
                "location": historical_weather.location.name,
                "start_date": historical_weather.start_date,
                "end_date": historical_weather.end_date,
                "average_temperature_c": historical_weather.average_temperature_c,
                "average_annual_rainfall_mm": historical_weather.average_annual_rainfall_mm,
                "max_single_day_rainfall_mm": historical_weather.max_single_day_rainfall_mm,
                "hottest_month": historical_weather.hottest_month,
                "wettest_month": historical_weather.wettest_month,
                "weather_patterns": historical_weather.weather_patterns,
                "recurring_hazards": historical_weather.recurring_hazards,
                "source": historical_weather.source,
                "is_available": historical_weather.is_available,
            }

        query_summary_str = (cleaned_msg or message or "")[:120]
        decision_trace = DecisionTrace(
            trace_id=f"dt_{request_id}",
            evaluated_at=datetime.now(timezone.utc),
            query_summary=query_summary_str,
            resolved_location=effective_location,
            resolved_time_window=resolved_period,
            detected_intent=nlu.intent.value,
            persona=resolved_persona.value,
            language=target_lang.value,
            data_freshness=reasoning.freshness.value if hasattr(reasoning.freshness, "value") else str(reasoning.freshness),
            data_completeness=reasoning.data_complete,
            source_agreement=reasoning.source_agreement.value if hasattr(reasoning.source_agreement, "value") else str(reasoning.source_agreement),
            consistency_score=reasoning.consistency_score,
            official_warning_status="ACTIVE_WARNING" if reasoning.active_warnings else "NONE",
            official_warning_details=warning_details,
            warning_count=len(reasoning.active_warnings),
            hazards_detected=hazards_list,
            overall_risk=reasoning.overall_risk.value if hasattr(reasoning.overall_risk, "value") else str(reasoning.overall_risk),
            advisory_category=advisory.advisory_type.value if hasattr(advisory, "advisory_type") else "general",
            advisory_priority=advisory.priority.value if hasattr(advisory, "priority") else "normal",
            advisory_action_class=advisory.priority.value if hasattr(advisory, "priority") else "normal",
            evidence_basis=evidence_basis,
            evidence_links=evidence_links,
            validation_status=validation.status.value,
            violation_category=", ".join(validation.violation_categories) if getattr(validation, "violation_categories", None) else None,
            fallback_used=fallback_used,
            degraded_state=degraded_state.value,
            degraded_subsystems=subsystems_degraded,
            degradation_reason="; ".join(degraded_reasons) if degraded_reasons else None,
            stage_latencies_ms=stage_latencies,
            final_response_status="VALIDATED" if validation.is_valid else "FALLBACK_SUBSTITUTED",
            # Phase 6 fields
            request=query_summary_str,
            location=effective_location,
            forecast_period=resolved_period,
            confidence_score=reasoning.consistency_score,
            confidence_indicator=confidence_indicator,
            rainfall_indicators=rainfall_indicators,
            temperature=temperature_data,
            wind=wind_data,
            hazard_signals=hazards_list,
            official_warnings=official_warnings_list,
            persona_context=persona_context,
            final_recommendation=final_recommendation,
            explanation_points=explanation_points,
            sources=reasoning.sources_used or ["IMD"],
            confidence_level=conf_lvl_str,
            consistency_factors=getattr(reasoning, "consistency_factors", None),
            historical_context=historical_context_dict,
            data_types_used=data_types_used,
        )

        from ai.decision import build_why_this_answer
        personal_dec_data = getattr(advisory, "personal_decision", None)
        why_this_answer = build_why_this_answer(
            reasoning=reasoning,
            weather=weather,
            forecast=forecast,
            advisory=advisory,
            personal_decision=personal_dec_data,
            language=target_lang,
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
                "confidence_level": conf_lvl_str,
                "confidence_indicator": confidence_indicator,
            },
            "weather": weather_summary,
            "weather_summary": weather_summary,
            "forecast_count": len(forecast),
            "warnings": warnings_list,
            "alerts": warnings_list,
            "hazards": hazards_list,
            "advisory": advisory_dict,
            "personal_decision": personal_dec_data,
            "why_this_answer": why_this_answer,
            "reasoning": reasoning,
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
                # validation.issues is List[str] in the AI layer but the backend
                # ValidationSummary.issues schema expects List[Dict[str, Any]].
                # Convert each string issue to a structured dict at this boundary.
                "issues": [
                    {"type": "issue", "message": issue}
                    for issue in (validation.issues or [])
                ],
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
            "historical": historical_context_dict,
            "data_types_used": data_types_used,
        }

    # Canonical entrypoint alias (Phase 15 Step 4)
    run = process_query

