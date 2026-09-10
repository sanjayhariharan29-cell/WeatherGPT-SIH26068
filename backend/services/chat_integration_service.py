"""AI Integration Service Layer for WeatherGPT.

Connects backend weather data layer (current weather, forecast, official warnings,
historical archives) directly to Person 1's AI reasoning, hazard detection, advisory,
RAG safety retrieval, and grounded LLM generation pipeline.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.services.weather_manager import WeatherManager
from backend.services.exceptions import ProviderError
from backend.db.models import Conversation, Message, Advisory, User
from ai.pipeline import WeatherGPTPipeline
from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
    LocationInfo as AILocationInfo,
    PersonaEnum,
    RiskLevelEnum
)
from ai.memory import memory_manager, ContextResolver, ConversationTurn


class ChatIntegrationService:
    """Service layer connecting backend weather data engines to Person 1's AI Pipeline."""

    def __init__(
        self,
        weather_manager: Optional[WeatherManager] = None,
        ai_pipeline: Optional[WeatherGPTPipeline] = None
    ):
        self.weather_mgr = weather_manager or WeatherManager()
        self.ai_pipeline = ai_pipeline or WeatherGPTPipeline()

    def validate_coordinates(self, lat: Optional[float], lon: Optional[float]) -> None:
        """Validates latitude and longitude geographic bounds."""
        if lat is not None:
            if not isinstance(lat, (int, float)) or lat < -90.0 or lat > 90.0:
                raise ValueError(f"Invalid latitude {lat}. Latitude must be between -90 and +90 degrees.")

        if lon is not None:
            if not isinstance(lon, (int, float)) or lon < -180.0 or lon > 180.0:
                raise ValueError(f"Invalid longitude {lon}. Longitude must be between -180 and +180 degrees.")

    async def handle_chat_request(
        self,
        message: str,
        location_name: str = "Coimbatore",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        persona: str = "student",
        language: str = "ta",
        conversation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Orchestrates location resolution, backend weather data retrieval, AI reasoning, and persistence."""
        # 1. Validate Input Coordinates
        self.validate_coordinates(lat, lon)

        # 2. Resolve Geocoding Location & Conversational Context
        conv_id = conversation_id or "default"
        if not conversation_id or ContextResolver.is_reset_query(message):
            memory_manager.reset_context(conv_id)

        user_name: Optional[str] = None
        if user_id and db_session:
            try:
                authed_user = db_session.query(User).filter(User.id == user_id).first()
                if authed_user:
                    user_name = authed_user.name
                    if (not persona or persona == "student") and authed_user.persona:
                        persona = authed_user.persona
                    if (not language or language == "ta") and authed_user.language:
                        language = authed_user.language
            except Exception:
                pass

        ctx = memory_manager.get_context(conv_id)
        explicit_loc = location_name if location_name and location_name.lower() != "coimbatore" else None
        resolved = ContextResolver.resolve_query(
            message=message,
            context=ctx,
            explicit_location=explicit_loc,
            explicit_language=language,
            explicit_persona=persona
        )

        target_loc_name = resolved.resolved_location
        if not lat and not lon and (not location_name or location_name.lower() == "coimbatore"):
            from ai.nlu import parse_query
            nlu_loc = parse_query(message).entities.location
            if nlu_loc:
                target_loc_name = nlu_loc

        loc = await self.weather_mgr.geocoding.resolve_location(target_loc_name)
        resolved_lat = lat if lat is not None else loc["latitude"]
        resolved_lon = lon if lon is not None else loc["longitude"]
        resolved_name = loc["name"]
        now_dt = datetime.now(timezone.utc)

        # 3. Fetch Weather Intelligence (Current, Forecast, Alerts)
        is_data_available = True
        data_error_detail: Optional[str] = None

        try:
            current_resp = await self.weather_mgr.current_service.fetch_current_weather(
                lat=resolved_lat, lon=resolved_lon, location_name=resolved_name, db_session=db_session
            )

            primary_obs = AIWeatherRecord(
                location=AILocationInfo(
                    name=current_resp.location.name,
                    latitude=current_resp.location.latitude,
                    longitude=current_resp.location.longitude,
                    district=current_resp.location.district,
                    state=current_resp.location.state
                ),
                observed_at=datetime.fromisoformat(current_resp.observed_at),
                retrieved_at=datetime.fromisoformat(current_resp.retrieved_at),
                temperature=current_resp.weather.temperature,
                humidity=current_resp.weather.humidity,
                rain_probability=current_resp.weather.rain_probability,
                wind_speed=current_resp.weather.wind_speed,
                weather_condition=current_resp.weather.condition,
                source="IMD (Primary)",
                rainfall_amount_mm=current_resp.weather.rainfall_mm
            )

            secondary_obs = AIWeatherRecord(
                location=primary_obs.location,
                observed_at=primary_obs.observed_at,
                retrieved_at=primary_obs.retrieved_at,
                temperature=current_resp.comparison.secondary_temperature,
                humidity=70.0,
                rain_probability=current_resp.comparison.secondary_rain_probability,
                wind_speed=15.0,
                weather_condition=current_resp.weather.condition,
                source="Open-Meteo (Secondary)"
            )

            forecast_items = await self.weather_mgr.forecast_service.get_ai_forecast_items(
                lat=resolved_lat, lon=resolved_lon, location_name=resolved_name
            )

            official_alerts = await self.weather_mgr.alert_service.get_ai_official_alerts(
                lat=resolved_lat, lon=resolved_lon, location_name=resolved_name
            )

            weather_summary = current_resp.weather.model_dump()
            alerts_summary = [a.model_dump() for a in official_alerts]

        except (ProviderError, Exception) as exc:
            # Handle Provider Failure / Data Unavailability cleanly
            is_data_available = False
            data_error_detail = str(exc)

            loc_info = AILocationInfo(name=resolved_name, latitude=resolved_lat, longitude=resolved_lon)
            primary_obs = AIWeatherRecord(
                location=loc_info,
                observed_at=now_dt,
                retrieved_at=now_dt,
                temperature=0.0,
                humidity=0.0,
                rain_probability=0.0,
                wind_speed=0.0,
                weather_condition="Data Unavailable",
                source="DATA_UNAVAILABLE"
            )
            secondary_obs = None
            forecast_items = []
            official_alerts = []
            weather_summary = {
                "temperature": None,
                "humidity": None,
                "rain_probability": None,
                "wind_speed": None,
                "condition": "Data Unavailable"
            }
            alerts_summary = []

        # 4. Resolve Persona Enum
        persona_enum = None
        if persona.lower() in [p.value for p in PersonaEnum]:
            persona_enum = PersonaEnum(persona.lower())
        else:
            persona_enum = PersonaEnum.GENERAL

        conv_id = conversation_id or "default"

        # Construct trusted user profile context string
        user_ctx_str = f"User Profile: Name={user_name}, Persona={persona_enum.value.capitalize()}." if user_name else None
        full_context_summary = f"{user_ctx_str} {resolved.context_summary}" if (user_ctx_str and resolved.context_summary) else (user_ctx_str or resolved.context_summary)

        # 5. Process through Person 1's WeatherGPTPipeline
        pipeline_result = self.ai_pipeline.process_query(
            message=resolved.resolved_message,
            weather=primary_obs,
            forecast=forecast_items,
            active_alerts=official_alerts,
            secondary_weather=secondary_obs,
            persona=persona_enum,
            conversation_id=conv_id,
            target_language=language,
            context_summary=full_context_summary,
            request_id=request_id
        )

        # Update Short-Term Conversational Memory
        user_turn = ConversationTurn(
            role="user",
            message=message,
            intent=pipeline_result.get("intent"),
            location=resolved_name,
            language=pipeline_result.get("language")
        )
        assistant_turn = ConversationTurn(
            role="assistant",
            message=pipeline_result.get("answer", ""),
            intent=pipeline_result.get("intent"),
            location=resolved_name,
            risk_level=pipeline_result.get("risk", {}).get("level"),
            language=pipeline_result.get("language")
        )
        memory_manager.update_context(
            conversation_id=conv_id,
            user_turn=user_turn,
            assistant_turn=assistant_turn,
            location=resolved_name,
            date_context=resolved.resolved_date,
            time_context=resolved.resolved_time,
            persona=persona_enum.value,
            language=pipeline_result.get("language"),
            active_topic=resolved.resolved_topic,
            last_intent=pipeline_result.get("intent")
        )

        # Explicitly distinguish DATA_UNAVAILABLE from NO_HAZARD_DETECTED
        data_status = "OK" if is_data_available else "DATA_UNAVAILABLE"

        # 6. Database Persistence
        if db_session is not None:
            try:
                existing_conv = db_session.query(Conversation).filter(Conversation.id == conv_id).first()
                if not existing_conv:
                    conv = Conversation(id=conv_id, title=message[:30], user_id=user_id)
                    db_session.add(conv)
                    db_session.commit()
                elif user_id and not existing_conv.user_id:
                    existing_conv.user_id = user_id
                    db_session.commit()

                # Store User Message
                user_msg = Message(
                    conversation_id=conv_id,
                    sender="user",
                    content=message,
                    language=pipeline_result["language"],
                    created_at=now_dt
                )
                db_session.add(user_msg)
                db_session.commit()

                # Store Bot Message
                bot_msg = Message(
                    conversation_id=conv_id,
                    sender="bot",
                    content=pipeline_result["answer"],
                    intent=pipeline_result["intent"],
                    language=pipeline_result["language"],
                    risk_level=pipeline_result["risk"]["level"],
                    data_timestamp=now_dt
                )
                db_session.add(bot_msg)
                db_session.commit()
                db_session.refresh(bot_msg)

                # Store Advisory details
                advisory_record = Advisory(
                    message_id=bot_msg.id,
                    persona=persona,
                    target_activity="weather_decision",
                    risk_level=pipeline_result["risk"]["level"],
                    recommendation=pipeline_result["answer"]
                )
                db_session.add(advisory_record)
                db_session.commit()
            except Exception as db_err:
                db_session.rollback()
                print(f"Warning: Chat persistence skipped due to DB error: {db_err}")

        # 7. Construct Final Response Payload
        return {
            "request_id": request_id,
            "conversation_id": conv_id,
            "answer": pipeline_result["answer"],
            "language": pipeline_result["language"],
            "intent": pipeline_result["intent"],
            "location": resolved_name,
            "persona": persona_enum.value,
            "risk": pipeline_result["risk"],
            "weather_summary": weather_summary,
            "forecast_count": len(forecast_items),
            "alerts": alerts_summary,
            "source": pipeline_result["source"],
            "data_quality": {
                "is_data_available": is_data_available,
                "data_status": data_status,
                "consistency_score": pipeline_result["risk"]["consistency_score"],
                "error_detail": data_error_detail
            },
            "data_timestamp": pipeline_result["data_timestamp"],
            "validation": pipeline_result["validation"],
            "safety_telemetry": pipeline_result.get("safety_telemetry"),
            "hazards": pipeline_result.get("hazards", []),
            "advisory": pipeline_result.get("advisory", {}),
            "fallback_used": pipeline_result.get("fallback_used", False),
            "decision_trace": pipeline_result.get("decision_trace"),
        }
