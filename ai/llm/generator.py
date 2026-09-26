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

        # Check if live observation is missing for an observation query
        is_live_obs_query = False
        if nlu:
            intent_val = (nlu.intent.value if hasattr(nlu.intent, "value") else str(nlu.intent)).lower()
            if intent_val in ("current_weather", "rain_query", "temperature_query", "location_specific_weather"):
                is_live_obs_query = True
            elif any(k in nlu.original_text.lower() for k in ["right now", "current", "currently", "raining"]):
                is_live_obs_query = True

        data_unavail = False
        if reasoning and any("unavailable" in str(c).lower() for c in reasoning.contradictions):
            data_unavail = True
        elif reasoning and reasoning.data_complete is False and not weather:
            data_unavail = True

        # Attempt generation via configured provider (with routing & fallback)
        if self.provider and not (weather is None and (is_live_obs_query or data_unavail)):
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
                normal_rain = hf.get("rainfall_normal_mm")
                normal_temp = hf.get("temp_normal_c")

                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    return f"{h_loc}ல் வரலாற்று சராசரி வெப்பநிலை {temp_val:.1f}°C மற்றும் ஆண்டு மழை அளவு {rain_val:.1f} மி.மீ. இன்றைய முடிவுகளுக்கு நேரலை முன்னறிவிப்புகளைப் பார்க்கவும்."
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    return f"{h_loc} में ऐतिहासिक औसत तापमान {temp_val:.1f}°C और वार्षिक वर्षा {rain_val:.1f} मिमी दर्ज की गई है। आज की स्थिति के लिए लाइव पूर्वानुमान देखें।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{h_loc} मध्ये ऐतिहासिक सरासरी तापमान {temp_val:.1f}°C आणि वार्षिक पाऊस {rain_val:.1f} मिमी नोंदवला गेला आहे. आजच्या स्थितीसाठी थेट अंदाज पहा."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{h_loc}లో చారిత్రక సగటు ఉష్ణోగ్రత {temp_val:.1f}°C మరియు వార్షిక వర్షపాతం {rain_val:.1f} మిమీ నమోదైంది. నేటి పరిస్థితి కోసం లైవ్ సూచనలను చూడండి."
                else:
                    return f"Historically in {h_loc} ({start_d} to {end_d}), average temperature was {temp_val:.1f}°C (typical baseline: {normal_temp or temp_val:.1f}°C) with {rain_val:.1f} mm total rainfall compared to normal baseline of {normal_rain or 1200.0:.1f} mm. Today's trip should be guided by live forecasts."
            elif hf and hf.get("status") == "UNAVAILABLE":
                h_loc = hf.get("location", loc)
                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    return f"{h_loc}க்கான வரலாற்று வானிலை பதிவுகள் தற்போது அதிகாரப்பூர்வ காப்பகத்தில் கிடைக்கவில்லை. SkyZen does not fabricate historical statistics."
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    return f"{h_loc} के लिए ऐतिहासिक मौसम रिकॉर्ड वर्तमान में आधिकारिक संग्रह में उपलब्ध नहीं हैं। SkyZen does not fabricate historical statistics."
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{h_loc} साठी ऐतिहासिक हवामान नोंदी सध्या अधिकृत संग्रहात उपलब्ध नाहीत. SkyZen does not fabricate historical statistics."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{h_loc} కోసం చారిత్రక వాతావరణ రికార్డులు ప్రస్తుతం అధికారిక ఆర్కైవ్‌లలో అందుబాటులో లేవు. SkyZen does not fabricate historical statistics."
                else:
                    return f"Historical weather records for {h_loc} are currently unavailable in official archives. SkyZen does not fabricate historical statistics."

        # -----------------------------------------------------------------
        # 2. Priority Safety Case: Active Official IMD Alert
        # -----------------------------------------------------------------
        if reasoning.active_warnings:
            alert = reasoning.active_warnings[0]
            sev = alert.severity.value.upper() if hasattr(alert.severity, "value") else str(alert.severity).upper()
            affected = ", ".join(alert.affected_locations) if alert.affected_locations else loc
            precaution = advisory.key_precautions[0] if advisory.key_precautions else "Stay indoors and follow official safety directives."

            personal_dec = getattr(advisory, "personal_decision", None)

            if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                dec_ans = personal_dec.get("concise_answer_ta") if personal_dec else ""
                if dec_ans and (personal_dec.get("decision_type") in ("fishing_marine", "marine_safety") or alert.title in dec_ans):
                    return f"{user_prefix}{dec_ans}"
                return f"⚠️ [அதிகாரப்பூர்வ IMD {sev} எச்சரிக்கை: {alert.title}] {affected} பகுதியில் செயலில் உள்ளது. {dec_ans or precaution}"
            elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                dec_ans = personal_dec.get("concise_answer_hi") if personal_dec else ""
                if dec_ans and (personal_dec.get("decision_type") in ("fishing_marine", "marine_safety") or alert.title in dec_ans):
                    return f"{user_prefix}{dec_ans}"
                return f"⚠️ [आधिकारिक IMD {sev} चेतावनी: {alert.title}] {affected} में सक्रिय है। {dec_ans or precaution}"
            elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                dec_ans = personal_dec.get("concise_answer_mr") if personal_dec else ""
                if dec_ans and (personal_dec.get("decision_type") in ("fishing_marine", "marine_safety") or alert.title in dec_ans):
                    return f"{user_prefix}{dec_ans}"
                return f"⚠️ [अधिकृत IMD {sev} चेतावणी: {alert.title}] {affected} मध्ये सक्रिय आहे. {dec_ans or precaution}"
            elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                dec_ans = personal_dec.get("concise_answer_te") if personal_dec else ""
                if dec_ans and (personal_dec.get("decision_type") in ("fishing_marine", "marine_safety") or alert.title in dec_ans):
                    return f"{user_prefix}{dec_ans}"
                return f"⚠️ [అధికారిక IMD {sev} హెచ్చరిక: {alert.title}] {affected} లో సక్రియంగా ఉంది. {dec_ans or precaution}"
            else:
                dec_ans = personal_dec.get("concise_answer") if personal_dec else ""
                if dec_ans and (personal_dec.get("decision_type") in ("fishing_marine", "marine_safety") or alert.title.lower() in dec_ans.lower()):
                    if personal_dec.get("decision_type") in ("fishing_marine", "marine_safety"):
                        return f"{user_prefix}{dec_ans} Fishermen should strictly avoid venturing into the sea."
                    return f"{user_prefix}{dec_ans}"
                
                sev_tag = "CRITICAL" if "CRITICAL" in sev else ("EXTREME" if "EXTREME" in sev else sev)
                action_text = dec_ans or precaution
                explanation_text = alert.description or "Severe weather alert in effect."
                adv_text = advisory.advisory_text if (advisory and advisory.advisory_text) else action_text
                precs = advisory.key_precautions if (advisory and advisory.key_precautions) else [action_text]
                precs_str = "\n".join(f"- {p}" for p in precs[:3])
                return (
                    f"⚠️ [OFFICIAL IMD WARNING] {alert.title} ({sev_tag})\n"
                    f"Affected Area: {affected}\n"
                    f"Critical Safety Instruction: {action_text}\n"
                    f"Explanation: {explanation_text}\n"
                    f"Advisory: {adv_text}\n"
                    f"Recommended Precautions:\n{precs_str}"
                )

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

        # Consistency / multi-source agreement inquiry
        cf_summary = (reasoning.consistency_factors.get("summary") if (reasoning and reasoning.consistency_factors and isinstance(reasoning.consistency_factors, dict)) else "")
        if cf_summary and ("consistency" in user_text or "disagree" in user_text):
            return f"{user_prefix}{cf_summary}"

        # If user asks specific weather inquiry (e.g. 'Will it rain?'), answer it directly
        # unless user asked a specific activity decision (college, bike, umbrella, sports, etc.)
        if is_rain_q and p_type in ("general_go", "outdoor_activity", None):
            if not weather or getattr(weather, "rain_probability", None) is None or (reasoning and any("unavailable" in str(c).lower() for c in reasoning.contradictions)):
                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    return f"{user_prefix}{loc}ல் தற்போதைய மழை விவரங்கள் சரிபார்க்கப்படவில்லை (could not be verified); வானிலை தகவல் தற்போது கிடைக்கவில்லை (unavailable)."
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    return f"{user_prefix}{loc} में वर्तमान बारिश की स्थिति की पुष्टि नहीं की जा सकी (could not be verified); मौसम डेटा अनुपलब्ध (unavailable) है।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} मध्ये सध्याच्या पावसाच्या स्थितीची पुष्टी होऊ शकली नाही (could not be verified); हवामान डेटा अनुपलब्ध (unavailable) आहे."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc}లో ప్రస్తుత వర్షం వివరాలను ధృవీకరించడం సాధ్యపడలేదు (could not be verified); వాతావరణ సమాచారం అందుబాటులో లేదు (unavailable)."
                else:
                    return f"{user_prefix}Current conditions could not be verified for {loc}; real-time rainfall data is currently unavailable."

            rain_prob = float(weather.rain_probability)
            temp_note = f" ({weather.temperature:.0f}°C)" if (weather.temperature is not None) else ""
            if rain_prob >= 40.0:
                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    return f"{user_prefix}{loc}ல் இன்று{temp_note} மழை பெய்ய வாய்ப்புள்ளது ({rain_prob:.0f}% வாய்ப்பு). வெளியே செல்லும்போது குடை எடுத்துச் செல்லவும்."
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    return f"{user_prefix}{loc} में आज{temp_note} बारिश की संभावना है ({rain_prob:.0f}% संभावना)। बाहर जाते समय छाता साथ रखें।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} मध्ये आज{temp_note} पावसाची शक्यता आहे ({rain_prob:.0f}% शक्यता). बाहेर जाताना छत्री सोबत ठेवा."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc}లో ఈరోజు{temp_note} వర్షం పడే అవకాశం ఉంది ({rain_prob:.0f}% అవకాశం). బయటకు వెళ్లేటప్పుడు గొడుగు తీసుకెళ్లండి."
                else:
                    return f"{user_prefix}Rain is likely in {loc} today with a {rain_prob:.0f}% chance{temp_note}. I'd recommend carrying an umbrella."
            elif rain_prob >= 20.0:
                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    return f"{user_prefix}{loc}ல் காலையில் மழை வாய்ப்பு குறைவு{temp_note}, ஆனால் மாலையில் வாய்ப்பு சிறிது அதிகரிக்கலாம் ({rain_prob:.0f}%)."
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    return f"{user_prefix}{loc} में सुबह बारिश की संभावना कम है{temp_note}, लेकिन शाम को हल्की संभावना ({rain_prob:.0f}%) हो सकती है।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} मध्ये सकाळी पावसाची शक्यता कमी आहे{temp_note}, परंतु संध्याकाळी शक्यता किंचित वाढू शकते ({rain_prob:.0f}%)."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc}లో ఉదయం వర్షం పడే అవకాశం తక్కువ{temp_note}, కానీ సాయంత్రం అవకాశం కొద్దిగా పెరగవచ్చు ({rain_prob:.0f}%)."
                else:
                    return f"{user_prefix}Rain is unlikely this morning in {loc}{temp_note}, but the chance increases later today ({rain_prob:.0f}% chance)."
            else:
                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    return f"{user_prefix}{loc}ல் இன்று மழை பெய்ய வாய்ப்பில்லை ({rain_prob:.0f}%){temp_note}. வானிலை தெளிவாக இருக்கும்."
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    return f"{user_prefix}{loc} में आज बारिश की संभावना नहीं है ({rain_prob:.0f}%){temp_note}। मौसम साफ रहेगा।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} मध्ये आज पावसाची शक्यता नाही ({rain_prob:.0f}%){temp_note}. हवामान निरभ्र राहील."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc}లో ఈరోజు వర్షం పడే అవకాశం లేదు ({rain_prob:.0f}%){temp_note}. వాతావరణం నిర్మలంగా ఉంటుంది."
                else:
                    return f"{user_prefix}Rain is unlikely in {loc} today with only a {rain_prob:.0f}% chance{temp_note}. Skies remain mostly clear."

        if is_temp_q and p_type in ("general_go", "outdoor_activity", None):
            if not weather or weather.temperature is None:
                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    return f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை தரவு கிடைக்கவில்லை (Unavailable)."
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    return f"{user_prefix}{loc} में वर्तमान तापमान डेटा उपलब्ध नहीं है (Unavailable)।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} मध्ये वर्तमान तापमान डेटा उपलब्ध नाही (Unavailable)."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc}లో ప్రస్తుత ఉష్ణోగ్రత డేటా అందుబాటులో లేదు (Unavailable)."
                else:
                    return f"{user_prefix}Current temperature data for {loc} is currently unavailable."
            temp_val = weather.temperature
            cond_raw = weather.weather_condition if weather else "Clear"
            if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                cond_ta = translate_condition(cond_raw, LanguageEnum.TA)
                return f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை {temp_val:.0f}°C மற்றும் வானிலை {cond_ta} ஆக உள்ளது."
            elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                cond_hi = translate_condition(cond_raw, LanguageEnum.HI)
                return f"{user_prefix}{loc} में वर्तमान तापमान {temp_val:.0f}°C है और मौसम {cond_hi} बना हुआ है।"
            elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                cond_mr = translate_condition(cond_raw, LanguageEnum.MR)
                return f"{user_prefix}{loc} मध्ये सध्याचे तापमान {temp_val:.0f}°C असून हवामान {cond_mr} आहे."
            elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                cond_te = translate_condition(cond_raw, LanguageEnum.TE)
                return f"{user_prefix}{loc}లో ప్రస్తుత ఉష్ణోగ్రత {temp_val:.0f}°C మరియు వాతావరణం {cond_te}గా ఉంది."
            else:
                return f"{user_prefix}It is currently {temp_val:.0f}°C in {loc} with {cond_raw} conditions."

        # If personal decision available for the activity
        if personal_dec:
            is_general_q = ("weather" in user_text or "update" in user_text or p_type == "general_go")
            if (not weather or weather.temperature is None) and is_general_q:
                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    return f"{user_prefix}{loc}க்கான நேரலை வானிலை தகவல் தற்போது கிடைக்கவில்லை (Unavailable). பயணத்திற்கு முன் அதிகாரப்பூர்வ IMD அறிக்கைகளைச் சரிபார்க்கவும்."
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    return f"{user_prefix}{loc} के लिए लाइव मौसम डेटा उपलब्ध नहीं है (Unavailable)। यात्रा से पहले आधिकारिक IMD बुलेटिन देखें।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} साठी थेट हवामान डेटा सध्या उपलब्ध नाही (Unavailable). प्रवासापूर्वी अधिकृत IMD बुलेटिन तपासा."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc} కోసం లైవ్ వాతావరణ సమాచారం ప్రస్తుతం అందుబాటులో లేదు (Unavailable). ప్రయాణానికి ముందు అధికారిక IMD బులెటిన్‌లను తనిఖీ చేయండి."
                else:
                    return f"{user_prefix}Live weather data for {loc} is currently unavailable. Please check official IMD bulletins before traveling."
            temp_str = f" Current temperature is {weather.temperature:.0f}°C." if (weather and weather.temperature is not None and is_general_q) else ""
            if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                ans = personal_dec.get("concise_answer_ta") or personal_dec.get("concise_answer")
                if ans:
                    if is_general_q and weather and weather.temperature is not None and "°C" not in ans:
                        ans = f"{ans} தற்போதைய வெப்பநிலை {weather.temperature:.0f}°C."
                    return f"{user_prefix}{ans}"
            elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                ans = personal_dec.get("concise_answer_hi") or personal_dec.get("concise_answer")
                if ans:
                    if is_general_q and weather and weather.temperature is not None and "°C" not in ans:
                        ans = f"{ans} वर्तमान तापमान {weather.temperature:.0f}°C है।"
                    return f"{user_prefix}{ans}"
            elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                ans = personal_dec.get("concise_answer_mr") or personal_dec.get("concise_answer")
                if ans:
                    if is_general_q and weather and weather.temperature is not None and "°C" not in ans:
                        ans = f"{ans} सध्याचे तापमान {weather.temperature:.0f}°C आहे."
                    return f"{user_prefix}{ans}"
            elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                ans = personal_dec.get("concise_answer_te") or personal_dec.get("concise_answer")
                if ans:
                    if is_general_q and weather and weather.temperature is not None and "°C" not in ans:
                        ans = f"{ans} ప్రస్తుత ఉష్ణోగ్రత {weather.temperature:.0f}°C."
                    return f"{user_prefix}{ans}"
            else:
                ans = personal_dec.get("concise_answer")
                if ans:
                    if temp_str and "°C" not in ans:
                        ans = f"{ans}{temp_str}"
                    if (str(p_type).lower() in ("fishing_marine", "decisiontypeenum.fishing_marine")) and (str(personal_dec.get("verdict")).lower() in ("no_go", "decisionverdictenum.no_go")):
                        ans = f"{ans} Fishermen should strictly avoid venturing into the sea."
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

            if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                if rec_umb:
                    return f"{user_prefix}காலை {dep_t} பயணம் பொதுவாக சீராக இருக்கும். மாலை {ret_t} நேரத்தில் மழை வாய்ப்பு ({ret_prob:.0f}%) உள்ளதால் குடை எடுத்துச் செல்லவும்."
                else:
                    return f"{user_prefix}உங்கள் காலை {dep_t} மற்றும் மாலை {ret_t} பயணத்திற்கு வானிலை சாதகமாக உள்ளது. குடை தேவையில்லை."
            elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                if rec_umb:
                    return f"{user_prefix}सुबह {dep_t} की यात्रा ठीक रहेगी। शाम {ret_t} को बारिश की संभावना ({ret_prob:.0f}%) अधिक है, इसलिए छाता साथ रखें।"
                else:
                    return f"{user_prefix}आपकी सुबह {dep_t} और शाम {ret_t} की यात्रा के लिए मौसम अनुकूल है।"
            elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                if rec_umb:
                    return f"{user_prefix}सकाळी {dep_t} वाजता प्रवास सुरळीत राहील. संध्याकाळी {ret_t} च्या सुमारास पावसाची शक्यता ({ret_prob:.0f}%) असल्याने छत्री सोबत ठेवा."
                else:
                    return f"{user_prefix}तुमच्या सकाळच्या {dep_t} आणि संध्याकाळच्या {ret_t} प्रवासासाठी हवामान अनुकूल आहे. छत्रीची गरज नाही."
            elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                if rec_umb:
                    return f"{user_prefix}ఉదయం {dep_t} ప్రయాణం సాఫీగా ఉంటుంది. సాయంత్రం {ret_t} సమయంలో వర్షం పడే అవకాశం ({ret_prob:.0f}%) ఉన్నందున గొడుగు తీసుకెళ్లండి."
                else:
                    return f"{user_prefix}మీ ఉదయం {dep_t} మరియు సాయంత్రం {ret_t} ప్రయాణానికి వాతావరణం అనుకూలంగా ఉంది. గొడుగు అవసరం లేదు."
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
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} साठी सध्याचा तापमान डेटा उपलब्ध नाही (Unavailable)."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc} కోసం ప్రస్తుత ఉష్ణోగ్రత డేటా అందుబాటులో లేదు (Unavailable)."
                else:
                    return f"{user_prefix}Current temperature data for {loc} is currently unavailable."
            if target_lang == LanguageEnum.TA:
                return f"{user_prefix}{loc}க்கான நேரலை வானிலை தகவல் தற்போது கிடைக்கவில்லை (Unavailable). பயணத்திற்கு முன் அதிகாரப்பூர்வ IMD அறிக்கைகளைச் சரிபார்க்கவும்."
            elif target_lang == LanguageEnum.HI:
                return f"{user_prefix}{loc} के लिए लाइव मौसम डेटा उपलब्ध नहीं है (Unavailable)। यात्रा से पहले आधिकारिक IMD बुलेटिन देखें।"
            elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                return f"{user_prefix}{loc} साठी थेट हवामान डेटा सध्या उपलब्ध नाही (Unavailable). प्रवासापूर्वी अधिकृत IMD बुलेटिन तपासा."
            elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                return f"{user_prefix}{loc} కోసం లైవ్ వాతావరణ డేటా ప్రస్తుతం అందుబాటులో లేదు (Unavailable). ప్రయాణానికి ముందు అధికారిక IMD బులెటిన్‌లను తనిఖీ చేయండి."
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
            or any(k in user_text for k in ["rain", "raining", "மழை", "बारिश", "पाऊस", "वर्షం", "bheeg", "nanai"])
        )
        if is_rain_q:
            if rain_prob >= 40.0:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் இன்று மழை பெய்ய வாய்ப்புள்ளது ({rain_prob:.0f}% வாய்ப்பு). வெளியே செல்லும்போது குடை எடுத்துச் செல்லவும்."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में आज बारिश की संभावना है ({rain_prob:.0f}% संभावना)। बाहर जाते समय छाता साथ रखें।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} मध्ये आज पाऊस पडण्याची शक्यता आहे ({rain_prob:.0f}% शक्यता). बाहेर जाताना छत्री सोबत ठेवा."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc}లో ఈరోజు వర్షం పడే అవకాశం ఉంది ({rain_prob:.0f}% అవకాశం). బయటకు వెళ్లేటప్పుడు గొడుగు వెంట తీసుకెళ్లండి."
                else:
                    return f"{user_prefix}Rain is likely in {loc} today with a {rain_prob:.0f}% chance. I'd recommend carrying an umbrella."
            elif rain_prob >= 20.0:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் காலையில் மழை வாய்ப்பு குறைவு, ஆனால் மாலையில் வாய்ப்பு சிறிது அதிகரிக்கலாம் ({rain_prob:.0f}%)."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में सुबह बारिश की संभावना कम है, लेकिन शाम को हल्की संभावना ({rain_prob:.0f}%) हो सकती है।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} मध्ये सकाळी पावसाची शक्यता कमी आहे, परंतु संध्याकाळी शक्यता वाढू शकते ({rain_prob:.0f}%)."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc}లో ఉదయం వర్షం పడే అవకాశం తక్కువ, కానీ సాయంత్రం అవకాశం కొద్దిగా పెరగవచ్చు ({rain_prob:.0f}%)."
                else:
                    return f"{user_prefix}Rain is unlikely this morning in {loc}, but the chance increases later today ({rain_prob:.0f}% chance)."
            else:
                if target_lang == LanguageEnum.TA:
                    return f"{user_prefix}{loc}ல் இன்று மழை பெய்ய வாய்ப்பில்லை ({rain_prob:.0f}%). வானிலை தெளிவாக இருக்கும்."
                elif target_lang == LanguageEnum.HI:
                    return f"{user_prefix}{loc} में आज बारिश की संभावना नहीं है ({rain_prob:.0f}%)। मौसम साफ रहेगा।"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    return f"{user_prefix}{loc} मध्ये आज पाऊस पडण्याची शक्यता नाही ({rain_prob:.0f}%). हवामान निरभ्र राहील."
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    return f"{user_prefix}{loc}లో ఈరోజు వర్షం పడే అవకాశం లేదు ({rain_prob:.0f}%). వాతావరణం నిర్మలంగా ఉంటుంది."
                else:
                    return f"{user_prefix}Rain is unlikely in {loc} today with only a {rain_prob:.0f}% chance. Skies remain mostly clear."

        # 6b. Temperature query
        is_temp_q = (
            intent_val == "temperature_query"
            or any(k in user_text for k in ["temperature", "hot", "cold", "வெப்பநிலை", "तापमान", "ఉష్ణోగ్రత"])
        )
        if is_temp_q:
            if target_lang == LanguageEnum.TA:
                cond_ta = translate_condition(cond_raw, LanguageEnum.TA)
                return f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை {temp_val:.0f}°C மற்றும் வானிலை {cond_ta} ஆக உள்ளது."
            elif target_lang == LanguageEnum.HI:
                cond_hi = translate_condition(cond_raw, LanguageEnum.HI)
                return f"{user_prefix}{loc} में वर्तमान तापमान {temp_val:.0f}°C है और मौसम {cond_hi} बना हुआ है।"
            elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                cond_mr = translate_condition(cond_raw, LanguageEnum.MR)
                return f"{user_prefix}{loc} मध्ये सध्याचे तापमान {temp_val:.0f}°C असून हवामान {cond_mr} आहे."
            elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                cond_te = translate_condition(cond_raw, LanguageEnum.TE)
                return f"{user_prefix}{loc}లో ప్రస్తుత ఉష్ణోగ్రత {temp_val:.0f}°C మరియు వాతావరణం {cond_te}గా ఉంది."
            else:
                return f"{user_prefix}It is currently {temp_val:.0f}°C in {loc} with {cond_raw} conditions."

        # 6c. General weather response
        if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
            cond_ta = translate_condition(cond_raw, LanguageEnum.TA)
            base_ans = f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை {temp_val:.0f}°C மற்றும் வானிலை {cond_ta} ({rain_prob:.0f}% மழை வாய்ப்பு)."
        elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
            cond_hi = translate_condition(cond_raw, LanguageEnum.HI)
            base_ans = f"{user_prefix}{loc} में वर्तमान तापमान {temp_val:.0f}°C और मौसम {cond_hi} है ({rain_prob:.0f}% बारिश की संभावना)।"
        elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
            cond_mr = translate_condition(cond_raw, LanguageEnum.MR)
            base_ans = f"{user_prefix}{loc} मध्ये सध्याचे तापमान {temp_val:.0f}°C आणि हवामान {cond_mr} आहे ({rain_prob:.0f}% पावसाची शक्यता)."
        elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
            cond_te = translate_condition(cond_raw, LanguageEnum.TE)
            base_ans = f"{user_prefix}{loc}లో ప్రస్తుత ఉష్ణోగ్రత {temp_val:.0f}°C మరియు వాతావరణం {cond_te} ({rain_prob:.0f}% వర్ష సూచన)."
        else:
            base_ans = f"{user_prefix}In {loc}, the current temperature is {temp_val:.0f}°C and {cond_raw} with a {rain_prob:.0f}% chance of rain."

        # Actionable advisory recommendation
        if advisory:
            adv_snippet = advisory.advisory_text or advisory.headline or ""
            if adv_snippet and adv_snippet not in base_ans:
                if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                    base_ans += f"\nஅறிவுரை: {adv_snippet}"
                elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                    base_ans += f"\nसलाह: {adv_snippet}"
                elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
                    base_ans += f"\nसल्ला: {adv_snippet}"
                elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
                    base_ans += f"\nసలహా: {adv_snippet}"
                else:
                    base_ans += f"\nAdvisory: {adv_snippet}"

        # Source and data quality / consistency score footer
        score_val = getattr(reasoning, "consistency_score", None) if reasoning else 85
        if score_val is None:
            score_val = 85
        src_val = (weather.source if weather and weather.source else "IMD")

        if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
            meta_str = f"(ஆதாரம்: {src_val} | தர நம்பகத்தன்மை: முன்னறிவிப்பு நிலைத்தன்மை: {score_val}/100)"
        elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
            meta_str = f"(स्रोत: {src_val} | डेटा गुणवत्ता स्कोर: पूर्वानुमान संगति स्कोर: {score_val}/100)"
        elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
            meta_str = f"(स्रोत: {src_val} | डेटा गुणवत्ता स्कोअर: अंदाज सुसंगतता स्कोअर: {score_val}/100)"
        elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
            meta_str = f"(మూలం: {src_val} | డేటా నాణ్యత స్కోరు: సూచన స్థిరత్వ స్కోరు: {score_val}/100)"
        else:
            meta_str = f"(Source: {src_val} | Data Quality Score: Forecast Consistency Score: {score_val}/100)"

        return f"{base_ans}\n{meta_str}"
