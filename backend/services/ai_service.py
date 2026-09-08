"""Conversational AI Service Layer.

Bridges FastAPI chat routes with Person 1's WeatherGPTPipeline,
orchestrating location resolution, weather and forecast ingestion,
multi-source consensus, database persistence, and resilient error handling.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.config.logging import logger
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.services.weather_manager import WeatherManager
from backend.services.exceptions import ProviderError
from backend.db.models import Conversation, Message, Advisory
from ai.pipeline import WeatherGPTPipeline
from ai.nlu import parse_query
from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    LocationInfo as AILocationInfo
)
from ai.memory import memory_manager, ContextResolver, ConversationTurn


class AIService:
    """Service boundary orchestrating conversational AI requests."""

    def __init__(
        self,
        pipeline: Optional[WeatherGPTPipeline] = None,
        weather_manager: Optional[WeatherManager] = None
    ):
        self.pipeline = pipeline or WeatherGPTPipeline()
        self.weather_mgr = weather_manager or WeatherManager()

    async def process_chat(
        self,
        req: ChatRequest,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Processes a chat request through NLU, weather retrieval, reasoning, generation, and validation."""
        start_time = time.perf_counter()
        req_id = str(uuid.uuid4())[:8]

        logger.info(
            f"[{req_id}] Chat request initiated: message_len={len(req.message)}, "
            f"persona={req.persona}, language={req.language}"
        )

        # 1. Resolve Conversation ID and Session Context
        conv_id = req.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

        # 2. Check for explicit conversation reset triggers
        if ContextResolver.is_reset_query(req.message):
            logger.info(f"[{req_id}] Conversation reset requested for {conv_id}")
            memory_manager.reset_context(conv_id)

        # 3. Retrieve or initialize short-term conversation context
        context = memory_manager.get_context(conv_id)

        # 4. Resolve Follow-up query, References, Entity Inheritance, and Ambiguity
        explicit_loc: Optional[str] = None
        if req.location and req.location.name:
            loc_candidate = req.location.name.strip()
            # If payload passed default Coimbatore but query itself didn't specify it, check context
            explicit_loc = loc_candidate

        resolved = ContextResolver.resolve_query(
            message=req.message,
            context=context,
            explicit_location=explicit_loc,
            explicit_language=req.language,
            explicit_persona=req.persona
        )

        # 5. Handle Reference Ambiguity Safely (Never guess among multiple recent locations)
        if resolved.is_ambiguous:
            logger.info(f"[{req_id}] Ambiguous reference detected in query: {resolved.ambiguity_reason}")
            now_iso = datetime.now(timezone.utc).isoformat()
            amb_answer = resolved.ambiguity_reason or f"Multiple locations discussed ({', '.join(context.recent_locations)}). Please specify."
            return {
                "conversation_id": conv_id,
                "answer": amb_answer,
                "language": resolved.resolved_language,
                "intent": "clarification",
                "location": resolved.resolved_location,
                "persona": resolved.resolved_persona,
                "risk": {
                    "level": "low",
                    "consistency": "single_source",
                    "consistency_score": 0.0
                },
                "weather_summary": None,
                "alerts": [],
                "source": "ContextResolver",
                "data_timestamp": now_iso,
                "validation": {
                    "passed": True,
                    "status": "AMBIGUOUS_QUERY_CLARIFIED",
                    "violations": [],
                    "warnings": ["Multiple locations referenced ambiguously"]
                }
            }

        # 6. Location Resolution
        lat: Optional[float] = None
        lon: Optional[float] = None
        location_name = resolved.resolved_location

        if req.location is not None and req.location.latitude is not None and req.location.longitude is not None:
            lat = req.location.latitude
            lon = req.location.longitude

        # 7. Persona Resolution
        persona_enum = PersonaEnum.GENERAL
        if resolved.resolved_persona:
            req_persona_clean = resolved.resolved_persona.strip().lower()
            for p in PersonaEnum:
                if p.value == req_persona_clean:
                    persona_enum = p
                    break

        # 8. Weather & Forecast Ingestion via WeatherManager (FRESH WEATHER TRUTH)
        data_available = True
        try:
            primary_obs, forecast_items, active_alerts = await self.weather_mgr.get_ai_weather_input(
                lat=lat,
                lon=lon,
                location_name=location_name
            )
        except (ProviderError, Exception) as prov_err:
            logger.warning(f"[{req_id}] Weather retrieval failure for {location_name}: {prov_err}")
            data_available = False
            primary_obs = None
            forecast_items = []
            active_alerts = []

        # Graceful degradation if weather data is entirely unavailable
        if not data_available or primary_obs is None:
            if active_alerts:
                logger.warning(f"[{req_id}] Primary observation unavailable, but active official warning present for '{location_name}'. Proceeding through safety pipeline.")
            else:
                logger.warning(f"[{req_id}] Weather data unavailable for '{location_name}'. Returning safe fallback.")
                return self._build_unavailable_response(
                    req=req,
                    location_name=location_name,
                    req_id=req_id,
                    persona=persona_enum.value,
                    duration_ms=(time.perf_counter() - start_time) * 1000
                )

        # 9. Retrieve Secondary Observation for consensus/agreement scoring
        secondary_obs: Optional[AIWeatherRecord] = None
        if primary_obs is not None:
            try:
                loc = await self.weather_mgr.geocoding.resolve_location(location_name)
                sec_lat = lat if lat is not None else loc["latitude"]
                sec_lon = lon if lon is not None else loc["longitude"]
                sec_norm = await self.weather_mgr.open_meteo.get_current_weather(
                    sec_lat, sec_lon, loc["name"]
                )
                secondary_obs = AIWeatherRecord(
                    location=primary_obs.location,
                    observed_at=datetime.fromisoformat(sec_norm.observed_at),
                    retrieved_at=datetime.fromisoformat(sec_norm.retrieved_at),
                    temperature=sec_norm.temperature_c,
                    humidity=sec_norm.humidity_pct,
                    rain_probability=sec_norm.rain_probability_pct,
                    wind_speed=sec_norm.wind_speed_kmh,
                    weather_condition=sec_norm.condition,
                    source=sec_norm.source,
                    rainfall_amount_mm=sec_norm.rainfall_mm
                )
            except Exception as sec_err:
                logger.debug(f"[{req_id}] Secondary weather observation unavailable: {sec_err}")
                secondary_obs = None

        # 10. Execute WeatherGPTPipeline with Grounded Memory Summary
        pipeline_result = self.pipeline.process_query(
            message=resolved.resolved_message,
            weather=primary_obs,
            forecast=forecast_items,
            active_alerts=active_alerts,
            secondary_weather=secondary_obs,
            persona=persona_enum,
            conversation_id=conv_id,
            target_language=resolved.resolved_language,
            context_summary=resolved.context_summary,
            request_id=req_id
        )

        # 11. Update Short-Term Conversational Memory State
        user_turn = ConversationTurn(
            role="user",
            message=req.message,
            intent=pipeline_result.get("intent"),
            location=location_name,
            language=pipeline_result.get("language")
        )
        assistant_turn = ConversationTurn(
            role="assistant",
            message=pipeline_result.get("answer", ""),
            intent=pipeline_result.get("intent"),
            location=location_name,
            risk_level=pipeline_result.get("risk", {}).get("level"),
            language=pipeline_result.get("language")
        )
        memory_manager.update_context(
            conversation_id=conv_id,
            user_turn=user_turn,
            assistant_turn=assistant_turn,
            location=location_name,
            date_context=resolved.resolved_date,
            time_context=resolved.resolved_time,
            persona=persona_enum.value,
            language=pipeline_result.get("language"),
            active_topic=resolved.resolved_topic,
            last_intent=pipeline_result.get("intent")
        )

        now_dt = datetime.now(timezone.utc)

        # 7. Build telemetry summary and alerts list for client responses
        weather_summary = {
            "temperature": primary_obs.temperature,
            "humidity": primary_obs.humidity,
            "rain_probability": primary_obs.rain_probability,
            "wind_speed": primary_obs.wind_speed,
            "condition": primary_obs.weather_condition,
            "rainfall_mm": primary_obs.rainfall_amount_mm or 0.0
        } if primary_obs else None

        alerts_list: List[Dict[str, Any]] = [
            {
                "alert_type": a.type,
                "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
                "title": a.title,
                "description": a.description,
                "source": a.source,
                "issued_at": a.issued_at.isoformat(),
                "expires_at": a.expires_at.isoformat(),
                "area": ", ".join(a.affected_locations) if a.affected_locations else primary_obs.location.name
            }
            for a in active_alerts
        ]

        # 8. Database Persistence (safe transaction boundary)
        if db is not None:
            self._persist_chat_records(
                db=db,
                conv_id=conv_id,
                req=req,
                pipeline_result=pipeline_result,
                persona_val=persona_enum.value,
                now_dt=now_dt
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"[{req_id}] Chat request completed in {elapsed_ms:.2f}ms: "
            f"intent={pipeline_result['intent']}, risk={pipeline_result['risk']['level']}, "
            f"lang={pipeline_result['language']}"
        )

        # 9. Format response matching ChatResponse schema & Step 20
        return {
            "request_id": req_id,
            "conversation_id": conv_id,
            "answer": pipeline_result["answer"],
            "language": pipeline_result["language"],
            "intent": pipeline_result["intent"],
            "location": pipeline_result["location"],
            "persona": pipeline_result.get("persona", persona_enum.value),
            "risk": pipeline_result["risk"],
            "weather_summary": weather_summary,
            "forecast_count": len(forecast_items),
            "alerts": alerts_list,
            "source": pipeline_result["source"],
            "data_quality": pipeline_result.get("data_quality", {
                "is_data_available": True,
                "data_status": "OK",
                "consistency_score": pipeline_result.get("risk", {}).get("consistency_score", 1.0)
            }),
            "data_timestamp": pipeline_result["data_timestamp"],
            "validation": pipeline_result.get("validation"),
            "safety_telemetry": pipeline_result.get("safety_telemetry"),
            "hazards": pipeline_result.get("hazards", []),
            "advisory": pipeline_result.get("advisory", {}),
            "fallback_used": pipeline_result.get("fallback_used", False)
        }

    def _persist_chat_records(
        self,
        db: Session,
        conv_id: str,
        req: ChatRequest,
        pipeline_result: Dict[str, Any],
        persona_val: str,
        now_dt: datetime
    ) -> None:
        """Safely records conversation, messages, and advisory in the database."""
        try:
            # Ensure conversation exists
            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            if not conv:
                conv = Conversation(
                    id=conv_id,
                    title=req.message[:50]
                )
                db.add(conv)
                db.commit()

            # Persist user message
            user_msg = Message(
                conversation_id=conv_id,
                sender="user",
                content=req.message,
                language=pipeline_result.get("language", "ta"),
                created_at=now_dt
            )
            db.add(user_msg)
            db.commit()

            # Persist bot message
            bot_msg = Message(
                conversation_id=conv_id,
                sender="bot",
                content=pipeline_result["answer"],
                intent=pipeline_result["intent"],
                language=pipeline_result["language"],
                risk_level=pipeline_result["risk"]["level"],
                data_timestamp=now_dt,
                created_at=now_dt
            )
            db.add(bot_msg)
            db.commit()
            db.refresh(bot_msg)

            # Persist advisory record
            advisory = Advisory(
                message_id=bot_msg.id,
                persona=persona_val,
                target_activity="weather_decision",
                risk_level=pipeline_result["risk"]["level"],
                recommendation=pipeline_result["answer"],
                created_at=now_dt
            )
            db.add(advisory)
            db.commit()
        except Exception as db_err:
            logger.warning(f"Failed to persist chat message to database: {db_err}")
            db.rollback()

    def _build_unavailable_response(
        self,
        req: ChatRequest,
        location_name: str,
        req_id: str,
        persona: str,
        duration_ms: float
    ) -> Dict[str, Any]:
        """Constructs a safe, non-fabricated response when weather providers are unavailable."""
        lang = (req.language or "ta").lower()
        if lang == "ta":
            answer = f"தற்போது {location_name} பகுதிக்கான வானிலை தகவல்கள் கிடைக்கப்பெறவில்லை. தயவுசெய்து சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்."
        elif lang == "hi":
            answer = f"वर्तमान में {location_name} के लिए मौसम डेटा उपलब्ध नहीं है। कृपया कुछ समय बाद पुनः प्रयास करें।"
        else:
            answer = f"Live weather data is currently unavailable for {location_name}. Please check official IMD bulletins or try again shortly."

        now_iso = datetime.now(timezone.utc).isoformat()
        conv_id = req.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

        return {
            "conversation_id": conv_id,
            "answer": answer,
            "language": lang,
            "intent": "current_weather",
            "location": location_name,
            "persona": persona,
            "risk": {
                "level": "low",
                "consistency": "single_source",
                "consistency_score": 0.0
            },
            "weather_summary": None,
            "alerts": [],
            "source": "Unavailable",
            "data_timestamp": now_iso,
            "validation": {
                "passed": True,
                "status": "DATA_UNAVAILABLE",
                "violations": [],
                "warnings": ["Live weather data provider unavailable"],
                "checked_fields": None,
                "issues": None
            }
        }
