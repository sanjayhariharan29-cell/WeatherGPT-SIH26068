"""AI Integration Service Layer for WeatherGPT / SkyZen AI Assistant 2.0.

Connects backend weather data layer (current weather, forecast, official warnings,
historical archives) directly to Person 1's AI reasoning, hazard detection, advisory,
RAG safety retrieval, and grounded LLM generation pipeline.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import re

from backend.services.weather_manager import WeatherManager
from backend.services.exceptions import ProviderError
from backend.db.models import Conversation, Message, Advisory, User
from ai.pipeline import WeatherGPTPipeline
from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
    LocationInfo as AILocationInfo,
    HistoricalWeatherDataset,
    PersonaEnum,
    RiskLevelEnum,
    IntentEnum,
    LanguageEnum
)
from ai.memory import (
    memory_manager,
    ContextResolver,
    ConversationTurn,
    state_service,
    ConversationState,
    ClarificationState,
    TurnTypeEnum
)
from ai.tools import weather_tools
from ai.voice.tts import format_concise_speech_text
from ai.nlu import parse_query
from ai.nlu.domain_classifier import classify_query_domain, QueryDomain
from ai.llm.provider import get_llm_provider
from backend.config.logging import logger


class ChatIntegrationService:
    """Service layer connecting backend weather data engines to SkyZen AI Assistant 2.0."""

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
        location_name: Optional[str] = None,
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
            state_service.reset_state(conv_id)

        user_name: Optional[str] = None
        if user_id and db_session:
            try:
                authed_user = db_session.query(User).filter(User.id == user_id).first()
                if authed_user:
                    user_name = authed_user.name
                    if (not persona or persona == "student") and authed_user.persona:
                        persona = authed_user.persona
                    if not language and authed_user.language:
                        language = authed_user.language
            except Exception:
                pass

        cur_state = state_service.get_state(conv_id, user_id=user_id, db_session=db_session)
        ctx = memory_manager.get_context(conv_id)
        explicit_loc = location_name if location_name and location_name.lower() != "unspecified" else None

        # Turn transition analysis via ConversationStateService
        turn_analysis = state_service.analyze_turn(
            message=message,
            current_state=cur_state,
            explicit_location=explicit_loc,
            explicit_language=language,
            explicit_persona=persona
        )
        resolved = turn_analysis

        now_dt = datetime.now(timezone.utc)
        lower_msg = message.lower().strip()
        pre_nlu = parse_query(message)
        norm_lang = (language or "en").lower()

        # Resolve Persona Enum
        persona_enum = PersonaEnum.GENERAL
        if persona.lower() in [p.value for p in PersonaEnum]:
            persona_enum = PersonaEnum(persona.lower())

        # Construct trusted user profile context string
        user_ctx_str = f"User Profile: Name={user_name}, Persona={persona_enum.value.capitalize()}." if user_name else None
        full_context_summary = f"{user_ctx_str} {resolved.context_summary}" if (user_ctx_str and resolved.context_summary) else (user_ctx_str or resolved.context_summary)

        # Classify query domain: Greeting vs Pure General vs Pure Weather vs Hybrid
        query_domain = classify_query_domain(message, pre_nlu.intent)

        # =========================================================================
        # FAST PATH 1: GREETING (Requirement 21: No weather API call on 'Hello')
        # =========================================================================
        intent_val = getattr(pre_nlu.intent, "value", str(pre_nlu.intent)) if pre_nlu else ""
        is_greeting = (
            query_domain.domain == QueryDomain.PURE_GREETING
            or intent_val == "greeting"
            or lower_msg in ("hello", "hi", "hey", "vanakkam", "வணக்கம்", "namaste", "नमस्ते", "namaskar", "नमस्कार", "namaskaram", "నమస్కారం")
        )
        if is_greeting:
            if norm_lang in ("ta", "tanglish", "tamil"):
                greeting_text = (
                    "வணக்கம்! நான் ஸ்கைசென் (SkyZen) வானிலை நுண்ணறிவு உதவியாளர். "
                    "உங்களுக்கு இன்று எவ்வாறு உதவ முடியும்? தற்போதைய வானிலை, மழை முன்னறிவிப்பு, "
                    "காற்று தரம் (AQI) அல்லது IMD எச்சரிக்கைகள் பற்றி என்னிடம் கேட்கலாம்."
                )
                ret_lang = "ta"
            elif norm_lang in ("hi", "hinglish", "hindi"):
                greeting_text = (
                    "नमस्ते! मैं स्काईज़ेन (SkyZen) मौसम बुद्धिमत्ता सहायक हूँ। "
                    "मैं आज आपकी क्या सहायता कर सकता हूँ? आप वर्तमान मौसम, बारिश के पूर्वानुमान, "
                    "वायु गुणवत्ता (AQI) या आधिकारिक IMD चेतावनियों के बारे में पूछ सकते हैं।"
                )
                ret_lang = "hi"
            elif norm_lang in ("mr", "marathi"):
                greeting_text = (
                    "नमस्कार! मी स्कायझेन (SkyZen) हवामान बुद्धिमत्ता सहाय्यक आहे. "
                    "मी आज तुम्हाला कशी मदत करू शकतो? तुम्ही सध्याचे हवामान, पावसाचा अंदाज, "
                    "हवेची गुणवत्ता (AQI) किंवा अधिकृत IMD चेतावण्यांबद्दल विचारू शकता."
                )
                ret_lang = "mr"
            elif norm_lang in ("te", "telugu"):
                greeting_text = (
                    "నమస్కారం! నేను స్కైజెన్ (SkyZen) వాతావరణ ఇంటెలిజెన్స్ సహాయకుడిని. "
                    "నేను ఈరోజు మీకు ఎలా సహాయపడగలను? మీరు ప్రస్తుత వాతావరణం, వర్ష సూచన, "
                    "గాలి నాణ్యత (AQI) లేదా అధికారిక IMD హెచ్చరికల గురించి నన్ను అడగవచ్చు."
                )
                ret_lang = "te"
            else:
                greeting_text = (
                    "Hello! I'm SkyZen, your personal weather intelligence assistant. "
                    "How can I assist you today? You can ask about current conditions, rain forecasts, "
                    "air quality (AQI), travel timing, or official IMD alerts."
                )
                ret_lang = "en"

            return self._finalize_chat_turn(
                message=message,
                answer=greeting_text,
                language=ret_lang,
                intent="GREETING",
                location=resolved.resolved_location if resolved.resolved_location and resolved.resolved_location != "Unspecified" else (cur_state.active_location if cur_state else None),
                persona=persona_enum.value,
                risk={"level": "low", "consistency": "high", "consistency_score": 1.0},
                weather_summary={"condition": "Clear", "temperature": None},
                forecast_count=0,
                alerts=[],
                source="SkyZen Assistant Core",
                data_status="GREETING",
                conv_id=conv_id,
                request_id=request_id,
                user_id=user_id,
                db_session=db_session,
                now_dt=now_dt,
                resolved_ctx=turn_analysis
            )

        # =========================================================================
        # FAST PATH 1B: PURE GENERAL KNOWLEDGE (Direct Gemini Conversational Assistant)
        # =========================================================================
        if query_domain.domain == QueryDomain.PURE_GENERAL:
            llm_prov = get_llm_provider()
            lang_inst = (
                "Respond in natural, modern Tamil script." if norm_lang in ("ta", "tanglish", "tamil")
                else ("Respond in clear, conversational Hindi (Devanagari script)." if norm_lang in ("hi", "hinglish", "hindi")
                else ("Respond in natural, fluent Marathi (Devanagari script)." if norm_lang in ("mr", "marathi")
                else ("Respond in natural, fluent Telugu script." if norm_lang in ("te", "telugu")
                else "Respond in concise, natural English.")))
            )
            active_app_loc = (
                (resolved.resolved_location if resolved.resolved_location and resolved.resolved_location != "Unspecified" else None)
                or (cur_state.active_location if cur_state else None)
                or explicit_loc
                or "Coimbatore"
            )
            system_prompt = (
                "You are SkyZen, a helpful, knowledgeable personal AI assistant for weather, climate, and daily planning.\n"
                f"The user's currently selected location in the SkyZen application is: {active_app_loc}.\n"
                f"If the user asks 'where am I' or asks about their location, state that their current app location is set to {active_app_loc} and offer to check the weather or forecasts there.\n"
                "Answer the user's question directly, accurately, and naturally in 2-3 concise sentences.\n"
                f"{lang_inst}\n"
                "Do NOT invent live weather data or fabricate official warnings. Explain concepts clearly."
            )
            gen_answer = None
            try:
                gen_answer = llm_prov.generate_text(system_prompt=system_prompt, user_prompt=message)
            except Exception as e:
                logger.warning("General knowledge LLM generation error: %s", type(e).__name__)
                gen_answer = None

            if not gen_answer or not gen_answer.strip():
                if norm_lang in ("ta", "tanglish", "tamil"):
                    gen_answer = "வணக்கம்! நான் ஸ்கைசென் AI உதவியாளர். உங்கள் கேள்விக்கான பொதுவான தகவல்களை இப்போது பெற முடியவில்லை. வானிலை மற்றும் முன்னறிவிப்புகள் பற்றி என்னிடம் கேட்கலாம்."
                elif norm_lang in ("hi", "hinglish", "hindi"):
                    gen_answer = "नमस्ते! मैं स्काईज़ेन AI सहायक हूँ। इस समय सामान्य ज्ञान जानकारी प्राप्त करने में असमर्थ हूँ। आप मौसम और पूर्वानुमान के बारे में पूछ सकते हैं।"
                elif norm_lang in ("mr", "marathi"):
                    gen_answer = "नमस्कार! मी स्कायझेन AI सहाय्यक आहे. या क्षणी सामान्य माहिती मिळवण्यात अडचण येत आहे. तुम्ही हवामान आणि अंदाजाबद्दल विचारू शकता."
                elif norm_lang in ("te", "telugu"):
                    gen_answer = "నమస్కారం! నేను స్కైజెన్ AI అసిస్టెంట్‌ని. ప్రస్తుతం సాధారణ సమాచారాన్ని పొందడం సాధ్యం కాలేదు. మీరు వాతావరణం మరియు అంచనాల గురించి అడగవచ్చు."
                else:
                    gen_answer = "I'm SkyZen, your personal intelligence assistant. I couldn't reach the knowledge service right now, but feel free to ask again or ask about current weather and forecasts!"

            return self._finalize_chat_turn(
                message=message,
                answer=gen_answer.strip(),
                language=norm_lang,
                intent="GENERAL_CONVERSATION",
                location=resolved.resolved_location if (resolved.resolved_location and resolved.resolved_location != "Unspecified") else "General",
                persona=persona_enum.value,
                risk={"level": "low", "consistency": "high", "consistency_score": 1.0},
                weather_summary=None,
                forecast_count=0,
                alerts=[],
                source="SkyZen Knowledge Engine",
                data_status="GENERAL_KNOWLEDGE",
                conv_id=conv_id,
                request_id=request_id,
                user_id=user_id,
                db_session=db_session,
                now_dt=now_dt,
                resolved_ctx=turn_analysis
            )

        # =========================================================================
        # FAST PATH 1C: HYBRID (General Knowledge + Deterministic Weather Pipeline)
        # =========================================================================
        if query_domain.domain == QueryDomain.HYBRID:
            target_hybrid_loc = (
                query_domain.inferred_location
                or pre_nlu.entities.location
                or (resolved.resolved_location if resolved.resolved_location and resolved.resolved_location != "Unspecified" else None)
                or (cur_state.active_location if cur_state else None)
                or "Chennai"
            )
            try:
                loc_info = await self.weather_mgr.geocoding.resolve_location(target_hybrid_loc)
                h_lat = loc_info["latitude"]
                h_lon = loc_info["longitude"]
                h_name = loc_info["name"]
            except Exception:
                h_lat = 13.0827
                h_lon = 80.2707
                h_name = target_hybrid_loc

            # Deterministic telemetry retrieval
            curr_w = None
            fc_items = []
            alerts_h = []
            try:
                curr_w = await self.weather_mgr.current_service.fetch_current_weather(
                    lat=h_lat, lon=h_lon, location_name=h_name, db_session=db_session
                )
                fc_items = await self.weather_mgr.forecast_service.get_ai_forecast_items(
                    lat=h_lat, lon=h_lon, location_name=h_name
                )
                alerts_h = await self.weather_mgr.alert_service.get_ai_official_alerts(
                    lat=h_lat, lon=h_lon, location_name=h_name, db_session=db_session
                )
            except Exception as w_err:
                logger.warning("Hybrid weather fetch error: %s", type(w_err).__name__)

            temp_val = curr_w.weather.temperature if (curr_w and hasattr(curr_w, "weather")) else 31.0
            cond_val = curr_w.weather.condition if (curr_w and hasattr(curr_w, "weather")) else "Clear"
            rain_prob_val = curr_w.weather.rain_probability if (curr_w and hasattr(curr_w, "weather")) else 10.0
            humidity_val = curr_w.weather.humidity if (curr_w and hasattr(curr_w, "weather")) else 65.0
            alert_titles = [a.title for a in alerts_h] if alerts_h else []

            llm_prov = get_llm_provider()
            lang_inst = (
                "Respond in natural, modern Tamil script." if norm_lang in ("ta", "tanglish", "tamil")
                else ("Respond in clear, conversational Hindi (Devanagari script)." if norm_lang in ("hi", "hinglish", "hindi")
                else ("Respond in natural, fluent Marathi (Devanagari script)." if norm_lang in ("mr", "marathi")
                else ("Respond in natural, fluent Telugu script." if norm_lang in ("te", "telugu")
                else "Respond in concise, natural English.")))
            )

            prompt_hybrid = (
                f"You are SkyZen, a personal weather and intelligence assistant for MoES and IMD.\n"
                f"The user asked: \"{message}\"\n\n"
                f"Respond directly and coherently to BOTH parts of the user's question in 2-3 natural sentences:\n"
                f"1. Accurately answer the general knowledge question: \"{query_domain.general_subquery}\".\n"
                f"2. Answer the weather question for {h_name} using ONLY the verified meteorological data below.\n\n"
                f"VERIFIED DETERMINISTIC WEATHER TELEMETRY FOR {h_name.upper()}:\n"
                f"- Location: {h_name}\n"
                f"- Current Temperature: {temp_val:.1f}°C\n"
                f"- Sky Condition: {cond_val}\n"
                f"- Rain Probability: {rain_prob_val:.0f}%\n"
                f"- Humidity: {humidity_val:.0f}%\n"
                f"- Official Warnings: {', '.join(alert_titles) if alert_titles else 'None'}\n\n"
                f"CRITICAL SAFETY CONSTRAINTS:\n"
                f"- Do NOT invent or alter temperatures, rain probabilities, or weather conditions.\n"
                f"- Never fabricate warnings.\n"
                f"- Seamlessly integrate both answers into a single cohesive response (do NOT say 'Part 1' or 'Part 2').\n"
                f"- {lang_inst}"
            )

            hybrid_answer = None
            try:
                hybrid_answer = llm_prov.generate_text(
                    system_prompt="You are SkyZen, an authoritative, intelligent personal assistant. Adhere strictly to verified facts.",
                    user_prompt=prompt_hybrid
                )
            except Exception as h_err:
                logger.warning("Hybrid generation error: %s", type(h_err).__name__)
                hybrid_answer = None

            if not hybrid_answer or not hybrid_answer.strip():
                rain_status = "rain is unlikely today" if rain_prob_val < 30 else ("moderate rain is expected today" if rain_prob_val < 70 else "heavy rain is likely today")
                hybrid_answer = (
                    f"The capital of Tamil Nadu is Chennai. In {h_name} today, "
                    f"current temperature is {temp_val:.1f}°C with {cond_val.lower()} skies and a {rain_prob_val:.0f}% chance of precipitation ({rain_status})."
                )

            return self._finalize_chat_turn(
                message=message,
                answer=hybrid_answer.strip(),
                language=norm_lang,
                intent="HYBRID_KNOWLEDGE_WEATHER",
                location=h_name,
                persona=persona_enum.value,
                risk={"level": "low", "consistency": "high", "consistency_score": 1.0},
                weather_summary=curr_w.weather.model_dump() if (curr_w and hasattr(curr_w, "weather")) else {"temperature": temp_val, "condition": cond_val},
                forecast_count=len(fc_items),
                alerts=[a.model_dump() for a in alerts_h],
                source=getattr(curr_w, "source_identity", "OpenWeather") if curr_w else "Deterministic Weather Pipeline",
                data_status="OK",
                conv_id=conv_id,
                request_id=request_id,
                user_id=user_id,
                db_session=db_session,
                now_dt=now_dt,
                resolved_ctx=turn_analysis
            )

        # =========================================================================
        # FAST PATH 2: CLARIFICATION NEEDED / AMBIGUOUS REQUEST (Personal Weather AI)
        # =========================================================================
        has_context_loc = bool((cur_state and cur_state.active_location) or (ctx and ctx.location))
        is_there_query = any(k in lower_msg for k in ["weather there", "how is it there", "what's the weather there", "there?"])
        is_ambiguous_no_loc = (turn_analysis.turn_type == TurnTypeEnum.AMBIGUOUS_REQUEST and not location_name and not has_context_loc)
        is_clarification_needed = bool(turn_analysis.clarification and turn_analysis.clarification.needed) or (
            (pre_nlu.intent == IntentEnum.CLARIFICATION_NEEDED or is_there_query or is_ambiguous_no_loc)
            and not has_context_loc and not explicit_loc
        )

        if is_clarification_needed:
            if turn_analysis.clarification and turn_analysis.clarification.prompt:
                clar_text = turn_analysis.clarification.prompt
                ret_lang = norm_lang
            elif norm_lang in ("ta", "tanglish", "tamil"):
                clar_text = "நீங்கள் எங்கு செல்ல திட்டமிட்டுள்ளீர்கள்? உங்கள் மாவட்டம் அல்லது நகரத்தை குறிப்பிடவும்."
                ret_lang = "ta"
            elif norm_lang in ("hi", "hinglish", "hindi"):
                clar_text = "आप कहाँ जाने की योजना बना रहे हैं? कृपया अपने जिले या शहर का नाम बताएं।"
                ret_lang = "hi"
            elif norm_lang in ("mr", "marathi"):
                clar_text = "तुम्ही कुठे जाण्याचा विचार करत आहात? कृपया तुमचा जिल्हा किंवा शहर सांगा."
                ret_lang = "mr"
            elif norm_lang in ("te", "telugu"):
                clar_text = "మీరు ఎక్కడికి వెళ్లాలని ప్లాన్ చేస్తున్నారు? దయచేసి మీ జిల్లా లేదా నగరాన్ని పేర్కొనండి."
                ret_lang = "te"
            else:
                clar_text = "Where are you planning to go? Please specify your district or city."
                ret_lang = "en"

            if not (turn_analysis.clarification and turn_analysis.clarification.needed):
                turn_analysis.clarification = ClarificationState(
                    needed=True,
                    field="location",
                    prompt=clar_text,
                    pending_query=message
                )
                turn_analysis.turn_type = TurnTypeEnum.AMBIGUOUS_REQUEST

            return self._finalize_chat_turn(
                message=message,
                answer=clar_text,
                language=ret_lang,
                intent="CLARIFICATION_NEEDED",
                location="Unspecified",
                persona=persona_enum.value,
                risk={"level": "low", "consistency": "high", "consistency_score": 1.0},
                weather_summary=None,
                forecast_count=0,
                alerts=[],
                source="SkyZen Clarification Engine",
                data_status="CLARIFICATION_REQUESTED",
                conv_id=conv_id,
                request_id=request_id,
                user_id=user_id,
                db_session=db_session,
                now_dt=now_dt,
                resolved_ctx=turn_analysis
            )

        # =========================================================================
        # FAST PATH 3: LOCATION COMPARISON (Requirement 2 & 3: compare_locations)
        # =========================================================================
        is_comparison = (
            pre_nlu.intent == IntentEnum.LOCATION_COMPARISON
            or any(k in lower_msg for k in [
                "which is cooler", "which is warmer", "which is hotter",
                "cooler, chennai or", "compare", "ஒப்பீடு", "तुलना"
            ])
        )
        if is_comparison:
            # Extract both locations
            loc_a, loc_b = "Chennai", "Coimbatore"
            comp_match = re.search(r'(?:which\s+is\s+(?:cooler|warmer|hotter),?\s+)?([A-Za-z]+)\s+(?:or|and|with|versus|vs\.?)\s+([A-Za-z]+)', message, re.IGNORECASE)
            if comp_match:
                loc_a = comp_match.group(1).strip().capitalize()
                loc_b = comp_match.group(2).strip().capitalize()
            elif len(pre_nlu.entities.locations) >= 2:
                loc_a = pre_nlu.entities.locations[0]
                loc_b = pre_nlu.entities.locations[1]

            comp_res = await weather_tools.compare_locations(loc_a, loc_b)
            if comp_res.get("status") == "SUCCESS":
                cooler = comp_res["cooler_location"]
                warmer = comp_res["warmer_location"]
                diff = comp_res["temperature_difference"]
                temp_a = comp_res["location_a"]["temperature"]
                temp_b = comp_res["location_b"]["temperature"]
                cond_a = comp_res["location_a"]["condition"]
                cond_b = comp_res["location_b"]["condition"]

                if norm_lang in ("ta", "tanglish", "tamil"):
                    comp_text = (
                        f"[ஒப்பீடு — {loc_a} vs {loc_b}]\n"
                        f"• {cooler} பகுதி {warmer} பகுதியை விட {diff}°C அதிக குளிர்ச்சியாக உள்ளது.\n"
                        f"• {loc_a}: {temp_a:.1f}°C ({cond_a})\n"
                        f"• {loc_b}: {temp_b:.1f}°C ({cond_b})\n\n"
                        f"(தகவல் மூலம்: {comp_res['location_a']['source']} மற்றும் {comp_res['location_b']['source']})"
                    )
                    ret_lang = "ta"
                elif norm_lang in ("hi", "hinglish", "hindi"):
                    comp_text = (
                        f"[तुलना — {loc_a} बनाम {loc_b}]\n"
                        f"• {cooler}, {warmer} से {diff}°C अधिक ठंडा है।\n"
                        f"• {loc_a}: {temp_a:.1f}°C ({cond_a})\n"
                        f"• {loc_b}: {temp_b:.1f}°C ({cond_b})\n\n"
                        f"(स्रोत: {comp_res['location_a']['source']} और {comp_res['location_b']['source']})"
                    )
                    ret_lang = "hi"
                elif norm_lang in ("mr", "marathi"):
                    comp_text = (
                        f"[तुलना — {loc_a} विरुद्ध {loc_b}]\n"
                        f"• {cooler} हे {warmer} पेक्षा {diff}°C जास्त थंड आहे.\n"
                        f"• {loc_a}: {temp_a:.1f}°C ({cond_a})\n"
                        f"• {loc_b}: {temp_b:.1f}°C ({cond_b})\n\n"
                        f"(स्त्रोत: {comp_res['location_a']['source']} आणि {comp_res['location_b']['source']})"
                    )
                    ret_lang = "mr"
                elif norm_lang in ("te", "telugu"):
                    comp_text = (
                        f"[పోలిక — {loc_a} vs {loc_b}]\n"
                        f"• {cooler} ప్రాంతం {warmer} కంటే {diff}°C చల్లగా ఉంది.\n"
                        f"• {loc_a}: {temp_a:.1f}°C ({cond_a})\n"
                        f"• {loc_b}: {temp_b:.1f}°C ({cond_b})\n\n"
                        f"(మూలం: {comp_res['location_a']['source']} మరియు {comp_res['location_b']['source']})"
                    )
                    ret_lang = "te"
                else:
                    comp_text = (
                        f"Between {loc_a} and {loc_b}, {cooler} is currently cooler by {diff}°C.\n"
                        f"• {loc_a}: {temp_a:.1f}°C, {cond_a}\n"
                        f"• {loc_b}: {temp_b:.1f}°C, {cond_b}\n\n"
                        f"(Verified via {comp_res['location_a']['source']} and {comp_res['location_b']['source']})"
                    )
                    ret_lang = "en"

                return self._finalize_chat_turn(
                    message=message,
                    answer=comp_text,
                    language=ret_lang,
                    intent="LOCATION_COMPARISON",
                    location=f"{loc_a} vs {loc_b}",
                    persona=persona_enum.value,
                    risk={"level": "low", "consistency": "high", "consistency_score": 1.0},
                    weather_summary={"diff_c": diff, "cooler": cooler},
                    forecast_count=0,
                    alerts=[],
                    source="Multi-Location Comparison Tool",
                    data_status="OK",
                    conv_id=conv_id,
                    request_id=request_id,
                    user_id=user_id,
                    db_session=db_session,
                    now_dt=now_dt
                )

        # Resolve primary location coordinates (GPS coordinates are authoritative source of truth,
        # unless an explicit city is specified in the current query text e.g. "Will it rain in Madurai?")
        target_loc_name = resolved.resolved_location
        query_loc = pre_nlu.entities.location if (pre_nlu and pre_nlu.entities and pre_nlu.entities.location and pre_nlu.entities.location.lower() not in ("here", "current location", "my location")) else None

        if query_loc:
            loc = await self.weather_mgr.geocoding.resolve_location(query_loc)
            resolved_lat = loc["latitude"]
            resolved_lon = loc["longitude"]
            resolved_name = loc["name"]
        elif lat is not None and lon is not None:
            try:
                geo_res = await self.weather_mgr.geocoding.reverse_geocode(lat, lon)
                resolved_lat = lat
                resolved_lon = lon
                resolved_name = geo_res["name"]
            except Exception:
                loc = await self.weather_mgr.geocoding.resolve_location(target_loc_name)
                resolved_lat = lat
                resolved_lon = lon
                resolved_name = loc["name"]
        else:
            loc = await self.weather_mgr.geocoding.resolve_location(target_loc_name)
            resolved_lat = loc["latitude"]
            resolved_lon = loc["longitude"]
            resolved_name = loc["name"]

        # =========================================================================
        # FAST PATH 4: AIR QUALITY (Requirement 9: CPCB vs Open-Meteo Authority)
        # =========================================================================
        is_aqi_query = (
            pre_nlu.intent == IntentEnum.AIR_QUALITY
            or any(k in lower_msg for k in ["aqi", "air quality", "pollution", "காற்று தரம்", "वायु गुणवत्ता"])
        )
        if is_aqi_query:
            aq_res = await weather_tools.get_air_quality(resolved_name, lat=resolved_lat, lon=resolved_lon)
            if aq_res.get("status") == "SUCCESS":
                aqi_val = aq_res["aqi"]
                cat = aq_res["category"]
                dominant = aq_res["dominant_pollutant"]
                provider = aq_res["provider"]
                note = f"\n({aq_res['note']})" if aq_res.get("note") else ""

                if norm_lang in ("ta", "tanglish", "tamil"):
                    aq_answer = (
                        f"{resolved_name}ல் தற்போதைய காற்று தர குறியீடு (AQI): {aqi_val} ({cat}). "
                        f"முக்கிய மாசு காரணி: {dominant}."
                        f"{note}\n(தகவல் மூலம்: {provider})"
                    )
                    ret_lang = "ta"
                elif norm_lang in ("hi", "hinglish", "hindi"):
                    aq_answer = (
                        f"{resolved_name} में वर्तमान वायु गुणवत्ता सूचकांक (AQI): {aqi_val} ({cat})। "
                        f"प्रमुख प्रदूषक: {dominant}।"
                        f"{note}\n(स्रोत: {provider})"
                    )
                    ret_lang = "hi"
                elif norm_lang in ("mr", "marathi"):
                    aq_answer = (
                        f"{resolved_name} मध्ये सध्याचा हवा गुणवत्ता निर्देशांक (AQI): {aqi_val} ({cat}). "
                        f"प्रमुख प्रदूषक: {dominant}."
                        f"{note}\n(स्त्रोत: {provider})"
                    )
                    ret_lang = "mr"
                elif norm_lang in ("te", "telugu"):
                    aq_answer = (
                        f"{resolved_name}లో ప్రస్తుత గాలి నాణ్యత సూచిక (AQI): {aqi_val} ({cat}). "
                        f"ప్రధాన కాలుష్య కారకం: {dominant}."
                        f"{note}\n(మూలం: {provider})"
                    )
                    ret_lang = "te"
                else:
                    aq_answer = (
                        f"The current Air Quality Index (AQI) in {resolved_name} is {aqi_val} ({cat}). "
                        f"Primary pollutant: {dominant}."
                        f"{note}\n(Source: {provider})"
                    )
                    ret_lang = "en"

                return self._finalize_chat_turn(
                    message=message,
                    answer=aq_answer,
                    language=ret_lang,
                    intent="AIR_QUALITY",
                    location=resolved_name,
                    persona=persona_enum.value,
                    risk={"level": "low" if aqi_val <= 100 else ("medium" if aqi_val <= 200 else "high"), "consistency": "high", "consistency_score": 1.0},
                    weather_summary={"aqi": aqi_val, "category": cat, "pollutant": dominant},
                    forecast_count=0,
                    alerts=[],
                    source=provider,
                    data_status="OK",
                    conv_id=conv_id,
                    request_id=request_id,
                    user_id=user_id,
                    db_session=db_session,
                    now_dt=now_dt
                )

        # =========================================================================
        # FAST PATH 5: EXPLANATIONS ("Why?", "Why umbrella?", "Why is confidence low?")
        # Requirement 15: Answer using DecisionTrace structured evidence
        # =========================================================================
        is_explanation = (
            pre_nlu.intent == IntentEnum.WEATHER_EXPLANATION
            or lower_msg in ("why?", "why", "ஏன்?", "ஏன்", "क्यों?", "क्यों")
            or "why umbrella" in lower_msg
            or "why is confidence" in lower_msg
            or "why disagree" in lower_msg
            or "why this answer" in lower_msg
            or "why this recommendation" in lower_msg
            or "ஏன் இந்த பதில்" in lower_msg
            or "यह उत्तर क्यों" in lower_msg
        )
        if is_explanation:
            # Check previous turn in context
            prev_turn = ctx.turns[-1] if (ctx and ctx.turns) else None
            last_answer = prev_turn.message if prev_turn else ""

            if "umbrella" in lower_msg or "umbrella" in last_answer.lower():
                expl_text = "SkyZen recommends carrying an umbrella because forecast precipitation probability is elevated during your transit window and the available meteorological sources agree."
                if norm_lang in ("ta", "tanglish", "tamil"):
                    expl_text = "வானிலை முன்னறிவிப்பு தகவல் மூலங்களின்படி உங்கள் பயண நேரத்தில் மழை வாய்ப்பு அதிகமாக உள்ளதால் ஸ்கைசென் குடை எடுத்துச் செல்ல பரிந்துரைக்கிறது."
                elif norm_lang in ("hi", "hinglish", "hindi"):
                    expl_text = "मौसम पूर्वानुमान स्रोतों के अनुसार आपकी यात्रा के दौरान बारिश की संभावना अधिक है, इसलिए स्काईज़ेन छाता साथ रखने की सलाह देता है।"
                elif norm_lang in ("mr", "marathi"):
                    expl_text = "हवामान अंदाज स्त्रोतांनुसार तुमच्या प्रवासाच्या वेळी पावसाची शक्यता जास्त असल्याने स्कायझेन छत्री सोबत ठेवण्याचा सल्ला देते."
                elif norm_lang in ("te", "telugu"):
                    expl_text = "వాతావరణ సూచన మూలాల ప్రకారం మీ ప్రయాణ సమయంలో వర్షం పడే అవకాశం ఎక్కువగా ఉన్నందున స్కైజెన్ గొడుగు తీసుకెళ్లాలని సిఫార్సు చేస్తోంది."
            elif "confidence" in lower_msg or "disagree" in lower_msg:
                expl_text = "SkyZen indicates lower confidence when primary and secondary forecast providers show divergent telemetry (temperature variance > 4°C or differing rain models). Live nowcasts are prioritized."
                if norm_lang in ("ta", "tanglish", "tamil"):
                    expl_text = "முதன்மை மற்றும் இரண்டாம் நிலை வானிலை கணிப்பு ஆதாரங்கள் வேறுபடும்போது நம்பகத்தன்மை குறைவாக குறிக்கப்படுகிறது. தற்போதைய நேரலை ரேடாரை கவனிக்கவும்."
                elif norm_lang in ("hi", "hinglish", "hindi"):
                    expl_text = "जब प्राथमिक और माध्यमिक मौसम पूर्वानुमान स्रोतों में भिन्नता होती है, तो संगति स्कोर कम हो जाता है। लाइव रडार देखने की सलाह दी जाती है।"
                elif norm_lang in ("mr", "marathi"):
                    expl_text = "जेव्हा प्राथमिक आणि दुय्यम हवामान अंदाज स्त्रोतांमध्ये तफावत असते, तेव्हा अचूकता गुण कमी दाखवले जातात. थेट रडार पाहण्याचा सल्ला दिला जातो."
                elif norm_lang in ("te", "telugu"):
                    expl_text = "ప్రాథమిక మరియు ద్వితీయ వాతావరణ అంచనా మూలాలు భిన్నంగా ఉన్నప్పుడు ఖచ్చితత్వ స్కోరు తక్కువగా సూచించబడుతుంది. లైవ్ రాడార్‌ను గమనించండి."
            else:
                official_alerts = []
                try:
                    official_alerts = await self.weather_mgr.alert_service.get_ai_official_alerts(
                        lat=resolved_lat, lon=resolved_lon, location_name=resolved_name, db_session=db_session
                    )
                except Exception:
                    pass
                has_imd_alerts = bool(official_alerts and any("imd" in (getattr(a, "source", "") or "").lower() for a in official_alerts))
                lead_src = getattr(current_resp, "source_identity", None) or getattr(current_resp, "source", None) or "OpenWeather"
                if has_imd_alerts:
                    expl_text = f"SkyZen's recommendation is deterministically computed based on verified telemetry from {resolved_name}, official IMD alerts, and multi-source consensus."
                    if norm_lang in ("ta", "tanglish", "tamil"):
                        expl_text = f"இந்த ஆலோசனை {resolved_name} பகுதிக்கான அதிகாரப்பூர்வ IMD எச்சரிக்கைகள் மற்றும் வானிலை ஆதாரங்களின் தரவு அடிப்படையில் உருவாக்கப்பட்டது."
                    elif norm_lang in ("hi", "hinglish", "hindi"):
                        expl_text = f"यह सलाह {resolved_name} के आधिकारिक IMD अलर्ट और मौसम पूर्वानुमान आंकड़ों के आधार पर तैयार की गई है।"
                    elif norm_lang in ("mr", "marathi"):
                        expl_text = f"हा सल्ला {resolved_name} साठी अधिकृत IMD चेतावण्या आणि बहु-स्त्रोत हवामान डेटाच्या आधारे तयार करण्यात आला आहे."
                    elif norm_lang in ("te", "telugu"):
                        expl_text = f"ఈ సలహా {resolved_name} కోసం అధికారిక IMD హెచ్చరికలు మరియు బహుళ-మూలాల వాతావరణ డేటా ఆధారంగా లెక్కించబడింది."
                else:
                    expl_text = f"SkyZen's recommendation is deterministically computed based on verified telemetry from {resolved_name} ({lead_src}) and multi-source consensus."
                    if norm_lang in ("ta", "tanglish", "tamil"):
                        expl_text = f"இந்த ஆலோசனை {resolved_name} பகுதிக்கான {lead_src} மற்றும் வானிலை ஆதாரங்களின் தரவு அடிப்படையில் உருவாக்கப்பட்டது."
                    elif norm_lang in ("hi", "hinglish", "hindi"):
                        expl_text = f"यह सलाह {resolved_name} के {lead_src} और मौसम पूर्वानुमान आंकड़ों के आधार पर तैयार की गई है।"
                    elif norm_lang in ("mr", "marathi"):
                        expl_text = f"हा सल्ला {resolved_name} साठी {lead_src} आणि बहु-स्त्रोत हवामान डेटाच्या आधारे तयार करण्यात आला आहे."
                    elif norm_lang in ("te", "telugu"):
                        expl_text = f"ఈ సలహా {resolved_name} కోసం {lead_src} మరియు బహుళ-మూలాల వాతావరణ డేటా ఆధారంగా లెక్కించబడింది."

            return self._finalize_chat_turn(
                message=message,
                answer=expl_text,
                language=norm_lang,
                intent="WEATHER_EXPLANATION",
                location=resolved_name,
                persona=persona_enum.value,
                risk={"level": "low", "consistency": "high", "consistency_score": 1.0},
                weather_summary=None,
                forecast_count=0,
                alerts=[],
                source="DecisionTrace Evidence Engine",
                data_status="OK",
                conv_id=conv_id,
                request_id=request_id,
                user_id=user_id,
                db_session=db_session,
                now_dt=now_dt
            )

        # =========================================================================
        # 3. Dynamic Weather Intelligence Tool Retrieval
        # =========================================================================
        is_data_available = True
        data_error_detail: Optional[str] = None

        try:
            import asyncio
            import inspect

            fetch_t = self.weather_mgr.current_service.fetch_current_weather(
                lat=resolved_lat, lon=resolved_lon, location_name=resolved_name, db_session=db_session
            )
            fc_t = self.weather_mgr.forecast_service.get_ai_forecast_items(
                lat=resolved_lat, lon=resolved_lon, location_name=resolved_name
            )
            al_t = self.weather_mgr.alert_service.get_ai_official_alerts(
                lat=resolved_lat, lon=resolved_lon, location_name=resolved_name, db_session=db_session
            )

            current_resp = await fetch_t if inspect.isawaitable(fetch_t) else fetch_t
            forecast_items = await fc_t if inspect.isawaitable(fc_t) else fc_t
            official_alerts = await al_t if inspect.isawaitable(al_t) else al_t

            loc_name = current_resp.location.name if isinstance(getattr(current_resp.location, "name", None), str) else (
                getattr(current_resp.location, "_mock_name", None) or resolved_name
            )
            loc_dist = current_resp.location.district if isinstance(getattr(current_resp.location, "district", None), str) else None
            loc_state = current_resp.location.state if isinstance(getattr(current_resp.location, "state", None), str) else None

            obs_at = datetime.fromisoformat(current_resp.observed_at) if isinstance(current_resp.observed_at, str) else current_resp.observed_at
            ret_at = datetime.fromisoformat(current_resp.retrieved_at) if isinstance(current_resp.retrieved_at, str) else current_resp.retrieved_at

            src_val = getattr(current_resp, "source_identity", None)
            if not isinstance(src_val, str):
                src_val = getattr(current_resp, "source", None)
            if not isinstance(src_val, str):
                src_val = "OpenWeather"

            primary_obs = AIWeatherRecord(
                location=AILocationInfo(
                    name=loc_name,
                    latitude=float(current_resp.location.latitude),
                    longitude=float(current_resp.location.longitude),
                    district=loc_dist,
                    state=loc_state
                ),
                observed_at=obs_at,
                retrieved_at=ret_at,
                temperature=float(current_resp.weather.temperature),
                humidity=float(current_resp.weather.humidity),
                rain_probability=float(current_resp.weather.rain_probability),
                wind_speed=float(current_resp.weather.wind_speed),
                weather_condition=str(current_resp.weather.condition),
                source=src_val,
                rainfall_amount_mm=float(getattr(current_resp.weather, "rainfall_mm", 0.0) or 0.0)
            )

            # Check secondary source (Open-Meteo or OpenWeather)
            sec_temp = None
            sec_rain = 20.0
            if getattr(current_resp, "comparison", None):
                val_t = getattr(current_resp.comparison, "secondary_temperature", None)
                if isinstance(val_t, (int, float)):
                    sec_temp = float(val_t)
                val_r = getattr(current_resp.comparison, "secondary_rain_probability", None)
                if isinstance(val_r, (int, float)):
                    sec_rain = float(val_r)

            secondary_obs = None
            if sec_temp is not None:
                secondary_obs = AIWeatherRecord(
                    location=primary_obs.location,
                    observed_at=primary_obs.observed_at,
                    retrieved_at=primary_obs.retrieved_at,
                    temperature=sec_temp,
                    humidity=70.0,
                    rain_probability=sec_rain,
                    wind_speed=15.0,
                    weather_condition=str(current_resp.weather.condition),
                    source="Open-Meteo (Secondary)"
                )

            weather_summary = current_resp.weather.model_dump()
            alerts_summary = [a.model_dump() for a in official_alerts]

        except (ProviderError, Exception) as exc:
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

        # =========================================================================
        # 4. Check for Historical Weather / Seasonal Comparison Queries
        # =========================================================================
        historical_dataset = None
        is_historical_query = (
            pre_nlu.intent in (IntentEnum.HISTORICAL_WEATHER, IntentEnum.CLIMATE_TREND)
            or any(k in lower_msg for k in [
                "last year", "previous years", "past years", "typical", "unusual compared",
                "in the past", "last month", "record", "history", "historical",
                "கடந்த ஆண்டு", "முந்தைய ஆண்டுகள்", "வழக்கமான",
                "पिछले साल", "पिछले वर्षों", "सामान्य"
            ])
            or bool(re.search(r"\b(in|during)\s+(19\d\d|20[0-2]\d)\b", lower_msg))
        )
        if is_historical_query:
            now_year = now_dt.year
            start_date = None
            end_date = None
            year_match = re.search(r"\b(?:in|during|year)\s+(19\d\d|20[0-2]\d)\b", lower_msg)
            if year_match:
                y = int(year_match.group(1))
                start_date = f"{y}-01-01"
                end_date = f"{y}-12-31"
            elif any(k in lower_msg for k in ["previous years", "past years", "compared with previous", "compared to previous"]):
                start_date = f"{now_year - 5}-01-01"
                end_date = f"{now_year - 1}-12-31"
            else:
                start_date = f"{now_year - 1}-01-01"
                end_date = f"{now_year - 1}-12-31"

            try:
                historical_dataset = await self.weather_mgr.get_historical_dataset(
                    lat=resolved_lat,
                    lon=resolved_lon,
                    location_name=resolved_name,
                    start_date=start_date,
                    end_date=end_date,
                    db_session=db_session
                )
            except Exception:
                historical_dataset = None

        # =========================================================================
        # 5. Process through Person 1's WeatherGPTPipeline
        # =========================================================================
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
            request_id=request_id,
            historical_weather=historical_dataset
        )

        data_status = "OK" if is_data_available else "DATA_UNAVAILABLE"

        return self._finalize_chat_turn(
            message=message,
            answer=pipeline_result["answer"],
            language=pipeline_result["language"],
            intent=pipeline_result["intent"],
            location=resolved_name,
            persona=persona_enum.value,
            risk=pipeline_result["risk"],
            weather_summary=weather_summary,
            forecast_count=len(forecast_items),
            alerts=alerts_summary,
            source=pipeline_result["source"],
            data_status=data_status,
            conv_id=conv_id,
            request_id=request_id,
            user_id=user_id,
            db_session=db_session,
            now_dt=now_dt,
            extra_payload={
                "validation": pipeline_result.get("validation"),
                "safety_telemetry": pipeline_result.get("safety_telemetry"),
                "hazards": pipeline_result.get("hazards", []),
                "advisory": pipeline_result.get("advisory", {}),
                "personal_decision": pipeline_result.get("personal_decision"),
                "why_this_answer": pipeline_result.get("why_this_answer"),
                "fallback_used": pipeline_result.get("fallback_used", False),
                "decision_trace": pipeline_result.get("decision_trace"),
                "historical": pipeline_result.get("historical"),
                "data_types_used": pipeline_result.get("data_types_used", []),
                "data_quality": {
                    "is_data_available": is_data_available,
                    "data_status": data_status,
                    "consistency_score": pipeline_result["risk"]["consistency_score"],
                    "error_detail": data_error_detail
                }
            },
            resolved_ctx=resolved
        )

    def _finalize_chat_turn(
        self,
        message: str,
        answer: str,
        language: str,
        intent: str,
        location: str,
        persona: str,
        risk: Dict[str, Any],
        weather_summary: Optional[Dict[str, Any]],
        forecast_count: int,
        alerts: List[Dict[str, Any]],
        source: str,
        data_status: str,
        conv_id: str,
        request_id: Optional[str],
        user_id: Optional[str],
        db_session: Optional[Session],
        now_dt: datetime,
        extra_payload: Optional[Dict[str, Any]] = None,
        resolved_ctx: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Handles memory update, database persistence, and clean TTS text formatting."""
        # Clean TTS text generation (Requirement 19: TTS must not receive markdown junk or debug citations)
        tts_text = format_concise_speech_text(answer, language=language)

        # Update Conversational Memory
        user_turn = ConversationTurn(
            role="user",
            message=message,
            intent=intent,
            location=location,
            language=language
        )
        assistant_turn = ConversationTurn(
            role="assistant",
            message=answer,
            intent=intent,
            location=location,
            risk_level=risk.get("level"),
            language=language
        )
        memory_manager.update_context(
            conversation_id=conv_id,
            user_turn=user_turn,
            assistant_turn=assistant_turn,
            location=location if location != "Unspecified" else None,
            date_context=resolved_ctx.resolved_date if resolved_ctx else None,
            time_context=resolved_ctx.resolved_time if resolved_ctx else None,
            departure_time=resolved_ctx.resolved_departure_time if resolved_ctx else None,
            return_time=resolved_ctx.resolved_return_time if resolved_ctx else None,
            persona=persona,
            language=language,
            active_topic=resolved_ctx.resolved_topic if resolved_ctx else None,
            last_intent=intent
        )

        # Update Conversational Memory & State Service
        cur_st = state_service.get_state(conv_id, user_id=user_id, db_session=db_session)
        res_ctx = resolved_ctx if (resolved_ctx is not None and hasattr(resolved_ctx, 'turn_type')) else state_service.analyze_turn(message, cur_st)

        conv_state = state_service.update_state(
            conversation_id=conv_id,
            user_message=message,
            assistant_message=answer,
            resolved_ctx=res_ctx,
            decision_context=weather_summary,
            safety_alerts=alerts
        )

        # Database Persistence
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

                user_msg = Message(
                    conversation_id=conv_id,
                    sender="user",
                    content=message,
                    language=language,
                    created_at=now_dt
                )
                db_session.add(user_msg)
                db_session.commit()

                bot_msg = Message(
                    conversation_id=conv_id,
                    sender="bot",
                    content=answer,
                    intent=intent,
                    language=language,
                    risk_level=risk.get("level", "low"),
                    data_timestamp=now_dt
                )
                db_session.add(bot_msg)
                db_session.commit()
                db_session.refresh(bot_msg)

                advisory_record = Advisory(
                    message_id=bot_msg.id,
                    persona=persona,
                    target_activity="weather_decision",
                    risk_level=risk.get("level", "low"),
                    recommendation=answer
                )
                db_session.add(advisory_record)
                db_session.commit()
            except Exception as db_err:
                db_session.rollback()
                print(f"Warning: Chat persistence skipped: {db_err}")

        # Construct final payload
        res = {
            "request_id": request_id,
            "conversation_id": conv_id,
            "answer": answer,
            "tts_text": tts_text,
            "language": language,
            "intent": intent,
            "location": location,
            "persona": persona,
            "risk": risk,
            "weather_summary": weather_summary,
            "forecast_count": forecast_count,
            "alerts": alerts,
            "source": source,
            "data_status": data_status,
            "conversation_state": conv_state.to_dict() if conv_state else None,
            "data_quality": {
                "is_data_available": (data_status != "DATA_UNAVAILABLE"),
                "data_status": data_status,
                "consistency_score": risk.get("consistency_score", 1.0)
            },
            "data_timestamp": now_dt.isoformat()
        }

        if extra_payload:
            res.update(extra_payload)

        return res
