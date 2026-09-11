"""LLM Generation Engine for WeatherGPT.

Uses provider abstraction (Gemini / Mock) with the Grounded Context Builder,
fast-path Grounding Safety Guard, and resilient deterministic template fallback.
"""

from typing import List, Optional, Any
from ai.config import AIConfig, get_ai_config
from ai.llm.context_builder import GroundedContext, build_grounded_context
from ai.llm.grounding_guard import verify_grounding
from ai.llm.prompts import SYSTEM_INSTRUCTION
from ai.llm.provider import BaseLLMProvider, GeminiLLMProvider, get_llm_provider
from ai.models import (
    DecisionAdvisory,
    ForecastItem,
    GroundedResponse,
    LanguageEnum,
    NLUResult,
    WeatherReasoningResult,
    WeatherRecord,
    HistoricalWeatherDataset,
    IntentEnum,
    SourceAgreementEnum,
)


class GroundedLLMGenerator:
    """Orchestrates grounded response generation using provider abstraction or fallback generator."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[BaseLLMProvider] = None,
        config: Optional[AIConfig] = None
    ):
        self.config = config or get_ai_config()
        if api_key:
            self.config.llm.api_key = api_key

        if provider:
            self.provider = provider
        else:
            self.provider = get_llm_provider(self.config.llm)
        self.last_is_fallback: bool = False

    def generate_response(
        self,
        nlu: NLUResult,
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory,
        forecast: Optional[List[ForecastItem]] = None,
        safety_guidance: Optional[List[str]] = None,
        reference_knowledge: Optional[List[Any]] = None,
        context_summary: Optional[str] = None,
        target_language: Optional[LanguageEnum] = None,
        historical_weather: Optional[HistoricalWeatherDataset] = None
    ) -> GroundedResponse:
        """Generates a verified, grounded natural language answer conforming to GroundedResponse contract."""
        from ai.llm.multilingual import resolve_target_language
        target_lang = resolve_target_language(
            nlu.detected_language,
            nlu.original_text,
            explicit_preference=target_language
        )

        context = build_grounded_context(
            nlu=nlu,
            weather=weather,
            reasoning=reasoning,
            advisory=advisory,
            forecast=forecast,
            safety_guidance=safety_guidance,
            reference_knowledge=reference_knowledge,
            context_summary=context_summary,
            historical_weather=historical_weather,
            target_language=target_lang
        )

        system_prompt = SYSTEM_INSTRUCTION.format(
            target_language=target_lang.value,
            persona=advisory.persona.value,
            source=", ".join(reasoning.sources_used)
        )

        # Attempt generation via configured provider (with routing & fallback)
        if self.provider:
            try:
                raw_response = self.provider.generate_text(
                    system_prompt=system_prompt,
                    user_prompt=context.formatted_prompt
                )
                if raw_response and raw_response.strip():
                    is_grounded, issues = verify_grounding(raw_response, context)
                    if is_grounded:
                        self.last_is_fallback = False
                        provider_name = getattr(self.provider, "last_provider_used", None) or getattr(self.provider, "name", "llm")
                        return GroundedResponse(
                            answer=raw_response.strip(),
                            grounded_facts=[f"{k}: {v}" for k, v in context.observed_facts.items() if v != "UNAVAILABLE"],
                            warnings=[w["title"] for w in context.official_warnings],
                            uncertainties=reasoning.contradictions,
                            sources=reasoning.sources_used,
                            used_grounded_context=True,
                            is_fallback=False,
                            provider_used=provider_name
                        )
            except Exception:
                # Catch timeouts, connection errors, or simulated provider exceptions
                pass

        # Fallback triggered (due to provider failure, timeout, or failed grounding check)
        self.last_is_fallback = True
        fallback_answer = self._generate_fallback(
            nlu, weather, reasoning, advisory, context, target_language=target_lang, historical_weather=historical_weather
        )
        return GroundedResponse(
            answer=fallback_answer,
            grounded_facts=[f"{k}: {v}" for k, v in context.observed_facts.items() if v != "UNAVAILABLE"],
            warnings=[w["title"] for w in context.official_warnings],
            uncertainties=reasoning.contradictions,
            sources=reasoning.sources_used,
            used_grounded_context=True,
            is_fallback=True,
            provider_used="deterministic_fallback"
        )

    def generate(
        self,
        nlu: NLUResult,
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory,
        forecast: Optional[List[ForecastItem]] = None,
        safety_guidance: Optional[List[str]] = None,
        reference_knowledge: Optional[List[Any]] = None,
        context_summary: Optional[str] = None,
        target_language: Optional[LanguageEnum] = None,
        historical_weather: Optional[HistoricalWeatherDataset] = None
    ) -> str:
        """String generation interface preserving complete backward compatibility."""
        return self.generate_response(
            nlu=nlu,
            weather=weather,
            reasoning=reasoning,
            advisory=advisory,
            forecast=forecast,
            safety_guidance=safety_guidance,
            reference_knowledge=reference_knowledge,
            context_summary=context_summary,
            target_language=target_language,
            historical_weather=historical_weather
        ).answer

    def _generate_fallback(
        self,
        nlu: Optional[NLUResult],
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory,
        context: Optional[GroundedContext] = None,
        target_language: Optional[LanguageEnum] = None,
        historical_weather: Optional[HistoricalWeatherDataset] = None
    ) -> str:
        """Deterministic personal assistant generator for offline/resilience/guard failure use.

        Follows SkyZen Personal Assistant rules:
        - 1–3 short sentences.
        - Action first answering the user's actual question.
        - Only include weather variables relevant to the question.
        - Never dump decision traces, raw JSON, or telemetry tables into main answer.
        - Prominently acknowledge official warnings when active.
        """
        from ai.llm.multilingual import resolve_target_language, translate_condition
        if target_language:
            target_lang = target_language
        elif nlu:
            target_lang = resolve_target_language(nlu.detected_language, nlu.original_text)
        else:
            target_lang = LanguageEnum.EN
        loc = reasoning.location if (reasoning and reasoning.location != "Unknown") else (getattr(nlu.entities, "location", None) if nlu and nlu.entities and nlu.entities.location else "your area")

        user_prefix = ""
        prompt_text = context.formatted_prompt if (context and hasattr(context, "formatted_prompt")) else ""
        if "User Profile: Name=" in prompt_text:
            import re
            name_match = re.search(r"User Profile:\s*Name=([A-Za-z0-9_ -]+?)(?:,|$|\.)", prompt_text)
            if name_match:
                fname = name_match.group(1).strip().split()[0]
                if fname:
                    user_prefix = f"{fname}, "

        # -----------------------------------------------------------------
        # 1. Historical Weather Handler (Concise 1-2 Sentences)
        # -----------------------------------------------------------------
        is_historical = False
        if nlu and nlu.intent in (IntentEnum.HISTORICAL_WEATHER, IntentEnum.CLIMATE_TREND):
            is_historical = True
        elif context and context.historical_facts and context.historical_facts.get("status") in ("AVAILABLE", "UNAVAILABLE"):
            is_historical = True
        elif historical_weather is not None:
            is_historical = True
        elif nlu and any(k in nlu.original_text.lower() for k in ["last year", "previous years", "typical", "unusual compared", "history", "historical"]):
            is_historical = True

        if is_historical:
            hf = (context.historical_facts if context else None)
            if not hf and historical_weather:
                if historical_weather.is_available:
                    hf = {
                        "status": "AVAILABLE",
                        "location": historical_weather.location.name,
                        "start_date": historical_weather.start_date,
                        "end_date": historical_weather.end_date,
                        "average_temperature_c": historical_weather.average_temperature_c,
                        "average_annual_rainfall_mm": historical_weather.average_annual_rainfall_mm,
                        "total_rainfall_mm": historical_weather.total_rainfall_mm,
                    }
                else:
                    hf = {
                        "status": "UNAVAILABLE",
                        "location": historical_weather.location.name,
                        "start_date": historical_weather.start_date,
                        "end_date": historical_weather.end_date,
                    }

            if hf and hf.get("status") == "AVAILABLE":
                h_loc = hf.get("location", loc)
                start_d = hf.get("start_date", "")
                end_d = hf.get("end_date", "")
                rain_val = hf.get("average_annual_rainfall_mm") or hf.get("total_rainfall_mm")
                temp_val = hf.get("average_temperature_c")

                if target_lang == LanguageEnum.TA:
                    return f"{h_loc}ல் வரலாற்று சராசரி வெப்பநிலை {temp_val:.1f}°C மற்றும் ஆண்டு மழை அளவு {rain_val:.1f} மி.மீ. இன்றைய முடிவுகளுக்கு நேரலை முன்னறிவிப்புகளைப் பார்க்கவும்."
                elif target_lang == LanguageEnum.HI:
                    return f"{h_loc} में ऐतिहासिक औसत तापमान {temp_val:.1f}°C और वार्षिक वर्षा {rain_val:.1f} मिमी दर्ज की गई है। आज की स्थिति के लिए लाइव पूर्वानुमान देखें।"
                else:
                    return f"Historically in {h_loc} ({start_d} to {end_d}), average temperature was {temp_val:.1f}°C with {rain_val:.1f} mm average annual rainfall. Today's trip should be guided by live forecasts."
            elif hf and hf.get("status") == "UNAVAILABLE":
                h_loc = hf.get("location", loc)
                if target_lang == LanguageEnum.TA:
                    return f"{h_loc}க்கான வரலாற்று வானிலை பதிவுகள் தற்போது அதிகாரப்பூர்வ காப்பகத்தில் கிடைக்கவில்லை."
                elif target_lang == LanguageEnum.HI:
                    return f"{h_loc} के लिए ऐतिहासिक मौसम रिकॉर्ड वर्तमान में आधिकारिक संग्रह में उपलब्ध नहीं हैं।"
                else:
                    return f"Historical weather records for {h_loc} are currently unavailable in official archives."

        # -----------------------------------------------------------------
        # 2. Priority Safety Case: Active Official IMD Alert
        # -----------------------------------------------------------------
        if reasoning.active_warnings:
            alert = reasoning.active_warnings[0]
            sev = alert.severity.value.upper() if hasattr(alert.severity, "value") else str(alert.severity).upper()
            affected = ", ".join(alert.affected_locations) if alert.affected_locations else loc
            precaution = advisory.key_precautions[0] if advisory.key_precautions else "Stay indoors and follow official safety directives."

            personal_dec = getattr(advisory, "personal_decision", None)

            if target_lang == LanguageEnum.TA:
                dec_ans = personal_dec.get("concise_answer_ta") if personal_dec else ""
                if dec_ans and (personal_dec.get("decision_type") in ("fishing_marine", "marine_safety") or alert.title in dec_ans):
                    return f"{user_prefix}{dec_ans}"
                return f"⚠️ [அதிகாரப்பூர்வ IMD {sev} எச்சரிக்கை: {alert.title}] {affected} பகுதியில் செயலில் உள்ளது. {dec_ans or precaution}"
            elif target_lang == LanguageEnum.HI:
                dec_ans = personal_dec.get("concise_answer_hi") if personal_dec else ""
                if dec_ans and (personal_dec.get("decision_type") in ("fishing_marine", "marine_safety") or alert.title in dec_ans):
                    return f"{user_prefix}{dec_ans}"
                return f"⚠️ [आधिकारिक IMD {sev} चेतावनी: {alert.title}] {affected} में सक्रिय है। {dec_ans or precaution}"
            else:
                dec_ans = personal_dec.get("concise_answer") if personal_dec else ""
                if dec_ans and (personal_dec.get("decision_type") in ("fishing_marine", "marine_safety") or alert.title.lower() in dec_ans.lower()):
                    return f"{user_prefix}{dec_ans}"
                return f"An official IMD {sev} alert is active for {affected} ({alert.title}). {dec_ans or precaution}"

        # -----------------------------------------------------------------
        # 3. Specific Inquiries (Rain / Temperature) or Personal Decisions
        # -----------------------------------------------------------------
        user_text = (nlu.original_text.lower() if nlu and nlu.original_text else "")
        intent_val = (nlu.intent.value if (nlu and hasattr(nlu.intent, "value")) else str(nlu.intent if nlu else "")).lower()

        is_rain_q = (
            intent_val in ("rain_query", "rain_forecast")
            or ("rain" in user_text and not any(k in user_text for k in ["umbrella", "bike", "college", "school", "cricket", "play"]))
        )
        is_temp_q = (
            intent_val in ("temperature_query", "temperature")
            or any(k in user_text for k in ["temperature", "hot", "cold", "வெப்பநிலை", "तापमान"])
        )

        personal_dec = getattr(advisory, "personal_decision", None)
        p_type = personal_dec.get("decision_type") if personal_dec else None

        # If user asks specific weather inquiry (e.g. 'Will it rain?'), answer it directly
        # unless user asked a specific activity decision (college, bike, umbrella, sports, etc.)
        if is_rain_q and p_type in ("general_go", "outdoor_activity", None):
            rain_prob = float(weather.rain_probability if (weather and weather.rain_probability is not None) else 0.0)
            temp_note = f" ({weather.temperature:.0f}°C)" if (weather and weather.temperature is not None) else ""
            if rain_prob >= 40.0:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் இன்று{temp_note} மழை பெய்ய வாய்ப்புள்ளது ({rain_prob:.0f}% வாய்ப்பு). வெளியே செல்லும்போது குடை எடுத்துச் செல்லவும்."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में आज{temp_note} बारिश की संभावना है ({rain_prob:.0f}% संभावना)। बाहर जाते समय छाता साथ रखें।"
                else:
                    return f"{user_prefix}Rain is likely in {loc} today with a {rain_prob:.0f}% chance{temp_note}. I'd recommend carrying an umbrella."
            elif rain_prob >= 20.0:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் காலையில் மழை வாய்ப்பு குறைவு{temp_note}, ஆனால் மாலையில் வாய்ப்பு சிறிது அதிகரிக்கலாம் ({rain_prob:.0f}%)."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में सुबह बारिश की संभावना कम है{temp_note}, लेकिन शाम को हल्की संभावना ({rain_prob:.0f}%) हो सकती है।"
                else:
                    return f"{user_prefix}Rain is unlikely this morning in {loc}{temp_note}, but the chance increases later today ({rain_prob:.0f}% chance)."
            else:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் இன்று மழை பெய்ய வாய்ப்பில்லை ({rain_prob:.0f}%){temp_note}. வானிலை தெளிவாக இருக்கும்."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में आज बारिश की संभावना नहीं है ({rain_prob:.0f}%){temp_note}। मौसम साफ रहेगा।"
                else:
                    return f"{user_prefix}Rain is unlikely in {loc} today with only a {rain_prob:.0f}% chance{temp_note}. Skies remain mostly clear."

        if is_temp_q and p_type in ("general_go", "outdoor_activity", None):
            if not weather or weather.temperature is None:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை தரவு கிடைக்கவில்லை (Unavailable)."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में वर्तमान तापमान डेटा उपलब्ध नहीं है (Unavailable)।"
                else:
                    return f"{user_prefix}Current temperature data for {loc} is currently unavailable."
            temp_val = weather.temperature
            cond_raw = weather.weather_condition if weather else "Clear"
            if target_lang == LanguageEnum.TA:
                cond_ta = translate_condition(cond_raw, LanguageEnum.TA)
                return f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை {temp_val:.0f}°C மற்றும் வானிலை {cond_ta} ஆக உள்ளது."
            elif target_lang == LanguageEnum.HI:
                cond_hi = translate_condition(cond_raw, LanguageEnum.HI)
                return f"{user_prefix}{loc} में वर्तमान तापमान {temp_val:.0f}°C है और मौसम {cond_hi} बना हुआ है।"
            else:
                return f"{user_prefix}It is currently {temp_val:.0f}°C in {loc} with {cond_raw} conditions."

        # If personal decision available for the activity
        if personal_dec:
            is_general_q = ("weather" in user_text or "update" in user_text or p_type == "general_go")
            temp_str = f" Currently {weather.temperature:.0f}°C." if (weather and weather.temperature is not None and is_general_q) else ""
            if target_lang == LanguageEnum.TA:
                ans = personal_dec.get("concise_answer_ta") or personal_dec.get("concise_answer")
                if ans:
                    if is_general_q and weather and weather.temperature is not None and "°C" not in ans:
                        ans = f"{ans} தற்போதைய வெப்பநிலை {weather.temperature:.0f}°C."
                    return f"{user_prefix}{ans}"
            elif target_lang == LanguageEnum.HI:
                ans = personal_dec.get("concise_answer_hi") or personal_dec.get("concise_answer")
                if ans:
                    if is_general_q and weather and weather.temperature is not None and "°C" not in ans:
                        ans = f"{ans} वर्तमान तापमान {weather.temperature:.0f}°C है।"
                    return f"{user_prefix}{ans}"
            else:
                ans = personal_dec.get("concise_answer")
                if ans:
                    if temp_str and "°C" not in ans:
                        ans = f"{ans}{temp_str}"
                    return f"{user_prefix}{ans}"

        # -----------------------------------------------------------------
        # 4. Schedule-aware Commute Decision (if present in advisory)
        # -----------------------------------------------------------------
        sched = getattr(advisory, "schedule_decision", None) or {}
        if sched.get("has_schedule"):
            dep_t = sched.get("departure_time", "8:00 AM")
            ret_t = sched.get("return_time", "5:00 PM")
            ret_prob = float(sched.get("return_prob", 0.0) or 0.0)
            rec_umb = sched.get("recommend_umbrella", False)

            if target_lang == LanguageEnum.TA:
                if rec_umb:
                    return f"{user_prefix}காலை {dep_t} பயணம் பொதுவாக சீராக இருக்கும். மாலை {ret_t} நேரத்தில் மழை வாய்ப்பு ({ret_prob:.0f}%) உள்ளதால் குடை எடுத்துச் செல்லவும்."
                else:
                    return f"{user_prefix}உங்கள் காலை {dep_t} மற்றும் மாலை {ret_t} பயணத்திற்கு வானிலை சாதகமாக உள்ளது. குடை தேவையில்லை."
            elif target_lang == LanguageEnum.HI:
                if rec_umb:
                    return f"{user_prefix}सुबह {dep_t} की यात्रा ठीक रहेगी। शाम {ret_t} को बारिश की संभावना ({ret_prob:.0f}%) अधिक है, इसलिए छाता साथ रखें।"
                else:
                    return f"{user_prefix}आपकी सुबह {dep_t} और शाम {ret_t} की यात्रा के लिए मौसम अनुकूल है।"
            else:
                if rec_umb:
                    return f"{user_prefix}Your morning trip around {dep_t} looks fine. Rain risk is higher around your {ret_t} return ({ret_prob:.0f}% chance), so I'd carry an umbrella."
                else:
                    return f"{user_prefix}Your commute around {dep_t} and return at {ret_t} looks clear and comfortable."

        # -----------------------------------------------------------------
        # 5. Missing Live Telemetry Case
        # -----------------------------------------------------------------
        if not weather or weather.temperature is None:
            if is_temp_q or "temperature" in user_text:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை தரவு கிடைக்கவில்லை (Unavailable)."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में वर्तमान तापमान डेटा उपलब्ध नहीं है (Unavailable)।"
                else:
                    return f"{user_prefix}Current temperature data for {loc} is currently unavailable."
            if target_lang == LanguageEnum.TA:
                return f"{user_prefix}{loc}க்கான நேரலை வானிலை தகவல் தற்போது கிடைக்கவில்லை (Unavailable). பயணத்திற்கு முன் அதிகாரப்பூர்வ IMD அறிக்கைகளைச் சரிபார்க்கவும்."
            elif target_lang == LanguageEnum.HI:
                return f"{user_prefix}{loc} के लिए लाइव मौसम डेटा उपलब्ध नहीं है (Unavailable)। यात्रा से पहले आधिकारिक IMD बुलेटिन देखें।"
            else:
                return f"{user_prefix}Live weather data for {loc} is currently unavailable. Please check official IMD bulletins before traveling."

        # -----------------------------------------------------------------
        # 6. Specific Weather Inquiry Matching (Rain, Temp, General)
        # -----------------------------------------------------------------
        temp_val = weather.temperature
        rain_prob = float(weather.rain_probability if weather.rain_probability is not None else 0.0)
        cond_raw = weather.weather_condition or "Clear"

        user_text = (nlu.original_text.lower() if nlu and nlu.original_text else "")
        intent_val = (nlu.intent.value if (nlu and hasattr(nlu.intent, "value")) else str(nlu.intent if nlu else "")).lower()

        # 6a. Rain query ("Will it rain?")
        is_rain_q = (
            intent_val in ("rain_query", "umbrella_decision")
            or any(k in user_text for k in ["rain", "raining", "மழை", "बारिश", "bheeg", "nanai"])
        )
        if is_rain_q:
            if rain_prob >= 40.0:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் இன்று மழை பெய்ய வாய்ப்புள்ளது ({rain_prob:.0f}% வாய்ப்பு). வெளியே செல்லும்போது குடை எடுத்துச் செல்லவும்."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में आज बारिश की संभावना है ({rain_prob:.0f}% संभावना)। बाहर जाते समय छाता साथ रखें।"
                else:
                    return f"{user_prefix}Rain is likely in {loc} today with a {rain_prob:.0f}% chance. I'd recommend carrying an umbrella."
            elif rain_prob >= 20.0:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் காலையில் மழை வாய்ப்பு குறைவு, ஆனால் மாலையில் வாய்ப்பு சிறிது அதிகரிக்கலாம் ({rain_prob:.0f}%)."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में सुबह बारिश की संभावना कम है, लेकिन शाम को हल्की संभावना ({rain_prob:.0f}%) हो सकती है।"
                else:
                    return f"{user_prefix}Rain is unlikely this morning in {loc}, but the chance increases later today ({rain_prob:.0f}% chance)."
            else:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் இன்று மழை பெய்ய வாய்ப்பில்லை ({rain_prob:.0f}%). வானிலை தெளிவாக இருக்கும்."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में आज बारिश की संभावना नहीं है ({rain_prob:.0f}%)। मौसम साफ रहेगा।"
                else:
                    return f"{user_prefix}Rain is unlikely in {loc} today with only a {rain_prob:.0f}% chance. Skies remain mostly clear."

        # 6b. Temperature query
        is_temp_q = (
            intent_val == "temperature_query"
            or any(k in user_text for k in ["temperature", "hot", "cold", "வெப்பநிலை", "तापमान"])
        )
        if is_temp_q:
            if target_lang == LanguageEnum.TA:
                cond_ta = translate_condition(cond_raw, LanguageEnum.TA)
                return f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை {temp_val:.0f}°C மற்றும் வானிலை {cond_ta} ஆக உள்ளது."
            elif target_lang == LanguageEnum.HI:
                cond_hi = translate_condition(cond_raw, LanguageEnum.HI)
                return f"{user_prefix}{loc} में वर्तमान तापमान {temp_val:.0f}°C है और मौसम {cond_hi} बना हुआ है।"
            else:
                return f"{user_prefix}It is currently {temp_val:.0f}°C in {loc} with {cond_raw} conditions."

        # 6c. General weather response
        if target_lang == LanguageEnum.TA:
            cond_ta = translate_condition(cond_raw, LanguageEnum.TA)
            return f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை {temp_val:.0f}°C மற்றும் வானிலை {cond_ta} ({rain_prob:.0f}% மழை வாய்ப்பு)."
        elif target_lang == LanguageEnum.HI:
            cond_hi = translate_condition(cond_raw, LanguageEnum.HI)
            return f"{user_prefix}{loc} में वर्तमान तापमान {temp_val:.0f}°C और मौसम {cond_hi} है ({rain_prob:.0f}% बारिश की संभावना)।"
        else:
            return f"{user_prefix}In {loc}, it is currently {temp_val:.0f}°C and {cond_raw} with a {rain_prob:.0f}% chance of rain."
