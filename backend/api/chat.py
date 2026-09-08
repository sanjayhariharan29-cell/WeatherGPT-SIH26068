from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.db.models import Conversation, Message, Advisory
from backend.services.weather_manager import WeatherManager
from ai.pipeline import WeatherGPTPipeline
from ai.models import WeatherRecord, LocationInfo, OfficialAlert, RiskLevelEnum, PersonaEnum, ForecastItem

router = APIRouter(tags=["AI Chat"])
weather_mgr = WeatherManager()
ai_pipeline = WeatherGPTPipeline()

class LocationPayload(BaseModel):
    name: str = "Coimbatore"
    latitude: Optional[float] = 11.0168
    longitude: Optional[float] = 76.9558

class ChatRequest(BaseModel):
    message: str
    language: str = "ta"
    persona: str = "student"
    location: Optional[LocationPayload] = None
    conversation_id: Optional[str] = None

@router.post("/chat")
async def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    """Main WeatherGPT Conversational Decision Engine Endpoint."""
    loc_name = req.location.name if req.location else "Coimbatore"
    
    # 1. Fetch live weather & alerts via WeatherManager
    weather_data = await weather_mgr.get_current_weather(
        lat=req.location.latitude if req.location else None,
        lon=req.location.longitude if req.location else None,
        location_name=loc_name
    )

    now_dt = datetime.now(timezone.utc)

    # 2. Build WeatherRecord model for Person 1's AI Pipeline
    loc_info = LocationInfo(
        name=weather_data["location"]["name"],
        latitude=weather_data["location"]["latitude"],
        longitude=weather_data["location"]["longitude"],
        district=weather_data["location"].get("district"),
        state=weather_data["location"].get("state")
    )

    official_alerts: List[OfficialAlert] = []
    for raw_alert in weather_data.get("alerts", []):
        official_alerts.append(
            OfficialAlert(
                type=raw_alert.get("alert_type", "heavy_rain"),
                severity=RiskLevelEnum.HIGH if raw_alert.get("severity") == "high" else RiskLevelEnum.MEDIUM,
                title=raw_alert.get("title", "Weather Warning"),
                description=raw_alert.get("description", ""),
                source=raw_alert.get("source", "IMD"),
                issued_at=now_dt,
                expires_at=now_dt
            )
        )

    primary_obs = WeatherRecord(
        location=loc_info,
        observed_at=now_dt,
        retrieved_at=now_dt,
        temperature=weather_data["weather"]["temperature"],
        humidity=weather_data["weather"]["humidity"],
        rain_probability=weather_data["weather"]["rain_probability"],
        wind_speed=weather_data["weather"]["wind_speed"],
        weather_condition=weather_data["weather"]["condition"],
        source="IMD"
    )

    secondary_obs = WeatherRecord(
        location=loc_info,
        observed_at=now_dt,
        retrieved_at=now_dt,
        temperature=weather_data["comparison"]["secondary_temperature"],
        humidity=70.0,
        rain_probability=weather_data["comparison"]["secondary_rain_probability"],
        wind_speed=16.0,
        weather_condition="Rain",
        source="Open-Meteo"
    )

    persona_enum = None
    if req.persona.lower() in [p.value for p in PersonaEnum]:
        persona_enum = PersonaEnum(req.persona.lower())

    conv_id = req.conversation_id or "default"

    # 3. Process query through Person 1's WeatherGPTPipeline
    pipeline_result = ai_pipeline.process_query(
        message=req.message,
        weather=primary_obs,
        forecast=[],
        active_alerts=official_alerts,
        secondary_weather=secondary_obs,
        persona=persona_enum,
        conversation_id=conv_id
    )

    # 4. Persistence into Database
    if not req.conversation_id:
        conv = Conversation(title=req.message[:30])
        db.add(conv)
        db.commit()
        db.refresh(conv)
        conv_id = conv.id

    # Store User Message
    user_msg = Message(
        conversation_id=conv_id,
        sender="user",
        content=req.message,
        language=pipeline_result["language"],
        created_at=now_dt
    )
    db.add(user_msg)
    db.commit()

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
    db.add(bot_msg)
    db.commit()
    db.refresh(bot_msg)

    # Store Advisory details
    advisory = Advisory(
        message_id=bot_msg.id,
        persona=req.persona,
        target_activity="outdoor_decision",
        risk_level=pipeline_result["risk"]["level"],
        recommendation=pipeline_result["answer"]
    )
    db.add(advisory)
    db.commit()

    # 5. Return JSON matching API contract
    return {
        "conversation_id": conv_id,
        "answer": pipeline_result["answer"],
        "language": pipeline_result["language"],
        "intent": pipeline_result["intent"],
        "location": weather_data["location"]["name"],
        "risk": pipeline_result["risk"],
        "weather_summary": weather_data["weather"],
        "alerts": weather_data["alerts"],
        "source": pipeline_result["source"],
        "data_timestamp": pipeline_result["data_timestamp"]
    }
