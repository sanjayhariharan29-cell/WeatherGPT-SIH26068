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
        elif self.config.llm.api_key:
            self.provider = GeminiLLMProvider(self.config.llm)
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
        context = build_grounded_context(
            nlu=nlu,
            weather=weather,
            reasoning=reasoning,
            advisory=advisory,
            forecast=forecast,
            safety_guidance=safety_guidance,
            reference_knowledge=reference_knowledge,
            context_summary=context_summary,
            historical_weather=historical_weather
        )

        from ai.llm.multilingual import resolve_target_language
        target_lang = resolve_target_language(
            nlu.detected_language,
            nlu.original_text,
            explicit_preference=target_language
        )

        system_prompt = SYSTEM_INSTRUCTION.format(
            target_language=target_lang.value,
            persona=advisory.persona.value,
            source=", ".join(reasoning.sources_used)
        )

        # Attempt generation via configured provider
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
                        return GroundedResponse(
                            answer=raw_response.strip(),
                            grounded_facts=[f"{k}: {v}" for k, v in context.observed_facts.items() if v != "UNAVAILABLE"],
                            warnings=[w["title"] for w in context.official_warnings],
                            uncertainties=reasoning.contradictions,
                            sources=reasoning.sources_used,
                            used_grounded_context=True,
                            is_fallback=False
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
            is_fallback=True
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
        """Deterministic, grounded template generator for offline/resilience/guard failure use."""
        from ai.llm.multilingual import resolve_target_language, translate_condition
        if target_language:
            target_lang = target_language
        elif nlu:
            target_lang = resolve_target_language(nlu.detected_language, nlu.original_text)
        else:
            target_lang = LanguageEnum.EN
        loc = reasoning.location

        lines: List[str] = []

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
        # Historical Weather & Risk Intelligence Handler
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
                        "max_single_day_rainfall_mm": historical_weather.max_single_day_rainfall_mm,
                        "hottest_month": historical_weather.hottest_month,
                        "wettest_month": historical_weather.wettest_month,
                        "weather_patterns": historical_weather.weather_patterns,
                        "recurring_hazards": historical_weather.recurring_hazards,
                        "source": historical_weather.source
                    }
                else:
                    hf = {
                        "status": "UNAVAILABLE",
                        "location": historical_weather.location.name,
                        "start_date": historical_weather.start_date,
                        "end_date": historical_weather.end_date,
                        "unavailability_reason": historical_weather.unavailability_reason
                    }

            if hf and hf.get("status") == "AVAILABLE":
                h_loc = hf.get("location", loc)
                start_d = hf.get("start_date", "")
                end_d = hf.get("end_date", "")
                rain_val = hf.get("average_annual_rainfall_mm") or hf.get("total_rainfall_mm")
                temp_val = hf.get("average_temperature_c")
                hottest_m = hf.get("hottest_month", "May")
                wettest_m = hf.get("wettest_month", "November")
                src_name = hf.get("source", "NASA POWER / IMD Historical Archive")

                user_msg = nlu.original_text.lower() if nlu else ""
                is_comparison = any(c in user_msg for c in ["unusual compared", "compared to previous", "compared with previous", "different from previous", "higher than normal", "lower than normal"])

                if target_lang == LanguageEnum.TA:
                    lines.append(f"📊 [வரலாற்று வானிலை தரவு — {h_loc}] (கால அளவு: {start_d} முதல் {end_d} வரை):")
                    if rain_val is not None:
                        lines.append(f"• பதிவு செய்யப்பட்ட சராசரி மழை அளவு: {rain_val:.1f} மி.மீ.")
                    if temp_val is not None:
                        lines.append(f"• வரலாற்று சராசரி வெப்பநிலை: {temp_val:.1f}°C (அதிகபட்ச வெப்ப மாதம்: {hottest_m}, அதிக மழை மாதம்: {wettest_m}).")
                    if is_comparison and weather:
                        curr_rain = weather.rainfall_amount_mm or 0.0
                        comp_text = "வழக்கத்தை விட அதிகம்" if curr_rain > ((rain_val or 950.0) / 52.0) else "வழக்கமான வரம்பிற்குள் உள்ளது"
                        lines.append(f"• ஒப்பீடு: தற்போதைய மழைவீழ்ச்சி ({curr_rain:.1f} மி.மீ) வரலாற்று சராசரியுடன் ஒப்பிடும்போது {comp_text}.")
                    lines.append(f"\nஆலோசனை: {advisory.advisory_text}")
                    lines.append("\n⚠️ [பாதுகாப்பு குறிப்பு]: வரலாற்று தரவுகள் கடந்த கால பதிவுகளை மட்டுமே குறிக்கின்றன. இன்றைய நிலைமையை தற்போதைய முன்னறிவிப்புகள் மற்றும் அதிகாரப்பூர்வ IMD எச்சரிக்கைகள் மூலம் மதிப்பீடு செய்ய வேண்டும்.")
                    lines.append(f"\n(தகவல் மூலம்: {src_name})")
                    return "\n".join(lines)
                elif target_lang == LanguageEnum.HI:
                    lines.append(f"📊 [ऐतिहासिक मौसम डेटा — {h_loc}] (अवधि: {start_d} से {end_d}):")
                    if rain_val is not None:
                        lines.append(f"• दर्ज औसत वार्षिक वर्षा: {rain_val:.1f} मिमी")
                    if temp_val is not None:
                        lines.append(f"• ऐतिहासिक औसत तापमान: {temp_val:.1f}°C (सबसे गर्म महीना: {hottest_m}, सबसे अधिक बारिश: {wettest_m})।")
                    if is_comparison and weather:
                        curr_rain = weather.rainfall_amount_mm or 0.0
                        comp_text = "सामान्य से अधिक" if curr_rain > ((rain_val or 950.0) / 52.0) else "सामान्य सीमा में"
                        lines.append(f"• तुलना: वर्तमान वर्षा ({curr_rain:.1f} मिमी) ऐतिहासिक औसत की तुलना में {comp_text} है।")
                    lines.append(f"\nसलाह: {advisory.advisory_text}")
                    lines.append("\n⚠️ [सुरक्षा नोट]: ऐतिहासिक डेटा केवल पिछले रिकॉर्ड को दर्शाता है। आज की स्थिति का मूल्यांकन वर्तमान पूर्वानुमान और आधिकारिक IMD चेतावनियों के आधार पर किया जाना चाहिए।")
                    lines.append(f"\n(स्रोत: {src_name})")
                    return "\n".join(lines)
                else:
                    lines.append(f"📊 Historical Weather Intelligence for {h_loc} (Period: {start_d} to {end_d}):")
                    if rain_val is not None:
                        lines.append(f"• Recorded Annual Average Precipitation: {rain_val:.1f} mm")
                    if temp_val is not None:
                        lines.append(f"• Historical Average Temperature: {temp_val:.1f}°C (Typical peak summer: {hottest_m}, wettest month: {wettest_m})")
                    if hf.get("max_single_day_rainfall_mm"):
                        lines.append(f"• Extreme Historical Event: Max single-day rainfall of {hf['max_single_day_rainfall_mm']:.1f} mm recorded.")
                    if is_comparison and weather:
                        curr_rain = weather.rainfall_amount_mm or 0.0
                        benchmark = ((rain_val or 950.0) / 52.0)
                        comp_desc = f"elevated above typical weekly baseline ({benchmark:.1f} mm)" if curr_rain > benchmark else "within expected seasonal baseline"
                        lines.append(f"• Seasonal Comparison: Current observed rainfall ({curr_rain:.1f} mm) is {comp_desc}.")
                    lines.append(f"\nAdvisory: {advisory.advisory_text}")
                    lines.append("\n⚠️ Safety Notice: Historical records reflect past climate patterns and must not be confused with current conditions. Today's decisions should be evaluated using live forecasts and official IMD warnings.")
                    lines.append(f"\n(Source: {src_name})")
                    return "\n".join(lines)
            elif hf and hf.get("status") == "UNAVAILABLE":
                h_loc = hf.get("location", loc)
                start_d = hf.get("start_date", "")
                end_d = hf.get("end_date", "")
                lines.append(f"Historical weather records for {h_loc} ({start_d} to {end_d}) are currently unavailable in official meteorological archives.")
                lines.append("SkyZen does not fabricate historical statistics when archive records cannot be retrieved.")
                lines.append(f"\nAdvisory: {advisory.advisory_text}")
                lines.append("\nPlease refer to current live weather observations and official IMD forecast warnings.")
                return "\n".join(lines)

        if target_lang == LanguageEnum.TA:
            temp_str = f"{weather.temperature:.0f}°C" if (weather and weather.temperature is not None) else "கிடைக்கவில்லை"
            rain_str = f"{weather.rain_probability:.0f}%" if (weather and weather.rain_probability is not None) else "கிடைக்கவில்லை"
            cond_str = translate_condition(weather.weather_condition, LanguageEnum.TA) if weather else "கிடைக்கவில்லை"

            if reasoning.active_warnings:
                alert = reasoning.active_warnings[0]
                lines.append(f"⚠️ [அதிகாரப்பூர்வ IMD எச்சரிக்கை] {alert.title}: {alert.description}")

            if weather and weather.temperature is not None and weather.rain_probability is not None:
                lines.append(
                    f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை {temp_str} மற்றும் மழை வாய்ப்பு {rain_str} (வானிலை: {cond_str})."
                )
            else:
                lines.append(
                    f"{user_prefix}{loc}ல் தற்போதைய தரவு முழுமையாக கிடைக்கவில்லை (வெப்பநிலை: {temp_str}, மழை வாய்ப்பு: {rain_str})."
                )

            lines.append(f"\nஆலோசனை: {advisory.advisory_text}")

            if advisory.key_precautions:
                precautions_str = "\n- " + "\n- ".join(advisory.key_precautions)
                lines.append(f"\nமுக்கிய பாதுகாப்பு வழிகாட்டுதல்கள்:{precautions_str}")

            conf_factors = getattr(reasoning, "consistency_factors", {}) or {}
            conf_lvl = getattr(reasoning, "confidence_level", None)
            conf_lvl_str = conf_lvl.value if hasattr(conf_lvl, "value") else (str(conf_lvl) if conf_lvl else "HIGH")
            if conf_lvl_str == "LOW":
                lines.append(f"\nவானிலை முன்னறிவிப்பு நம்பகத்தன்மை குறைவு: கிடைக்கும் வானிலை தகவல் மூலங்கள் வேறுபடுகின்றன.")
            elif conf_lvl_str == "HIGH":
                lines.append(f"\nவானிலை முன்னறிவிப்பு நம்பகத்தன்மை அதிகம்: தகவல் மூலங்கள் ஒத்துப் போகின்றன.")

            lines.append(
                f"\n(தகவல் மூலம்: {', '.join(reasoning.sources_used)} | புதுப்பிக்கப்பட்டது {reasoning.data_age_minutes} நிமிடங்களுக்கு முன் | முன்னறிவிப்பு நிலைத்தன்மை: {reasoning.consistency_score}/100 [{conf_lvl_str}])"
            )
        elif target_lang == LanguageEnum.HI:
            temp_str = f"{weather.temperature:.0f}°C" if (weather and weather.temperature is not None) else "उपलब्ध नहीं"
            rain_str = f"{weather.rain_probability:.0f}%" if (weather and weather.rain_probability is not None) else "उपलब्ध नहीं"
            cond_str = translate_condition(weather.weather_condition, LanguageEnum.HI) if weather else "उपलब्ध नहीं"

            if reasoning.active_warnings:
                alert = reasoning.active_warnings[0]
                lines.append(f"⚠️ [आधिकारिक IMD चेतावनी] {alert.title}: {alert.description}")

            if weather and weather.temperature is not None and weather.rain_probability is not None:
                lines.append(
                    f"{user_prefix}{loc} में वर्तमान तापमान {temp_str} है और बारिश की संभावना {rain_str} है (मौसम: {cond_str})।"
                )
            else:
                lines.append(
                    f"{user_prefix}{loc} में वर्तमान अवलोकन डेटा आंशिक रूप से अनुपलब्ध है (तापमान: {temp_str}, बारिश की संभावना: {rain_str})।"
                )

            lines.append(f"\nसलाह: {advisory.advisory_text}")

            if advisory.key_precautions:
                precautions_str = "\n- " + "\n- ".join(advisory.key_precautions)
                lines.append(f"\nमुख्य सावधानियां:{precautions_str}")

            conf_factors = getattr(reasoning, "consistency_factors", {}) or {}
            conf_lvl = getattr(reasoning, "confidence_level", None)
            conf_lvl_str = conf_lvl.value if hasattr(conf_lvl, "value") else (str(conf_lvl) if conf_lvl else "HIGH")
            if conf_lvl_str == "LOW":
                lines.append(f"\nपूर्वानुमान स्थिरता कम है क्योंकि उपलब्ध स्रोत असहमत हैं।")
            elif conf_lvl_str == "HIGH":
                lines.append(f"\nपूर्वानुमान स्थिरता उच्च है क्योंकि उपलब्ध स्रोत काफी हद तक सहमत हैं।")

            lines.append(
                f"\n(स्रोत: {', '.join(reasoning.sources_used)} | {reasoning.data_age_minutes} मिनट पहले अपडेट किया गया | पूर्वानुमान संगति स्कोर: {reasoning.consistency_score}/100 [{conf_lvl_str}])"
            )
        else:
            temp_str = f"{weather.temperature:.0f}°C" if (weather and weather.temperature is not None) else "unavailable"
            rain_str = f"{weather.rain_probability:.0f}%" if (weather and weather.rain_probability is not None) else "unavailable"
            cond_str = weather.weather_condition if (weather and weather.weather_condition) else "unavailable"

            if reasoning.active_warnings:
                alert = reasoning.active_warnings[0]
                lines.append(f"⚠️ [OFFICIAL IMD WARNING] {alert.title}: {alert.description}")

            if weather and weather.temperature is not None and weather.rain_probability is not None:
                lines.append(
                    f"{user_prefix}in {loc}, current temperature is {temp_str} with a {rain_str} chance of precipitation ({cond_str})." if user_prefix else f"In {loc}, current temperature is {temp_str} with a {rain_str} chance of precipitation ({cond_str})."
                )
            else:
                lines.append(
                    f"{user_prefix}in {loc}, current observation data is partially unavailable (Temperature: {temp_str}, Precipitation probability: {rain_str})." if user_prefix else f"In {loc}, current observation data is partially unavailable (Temperature: {temp_str}, Precipitation probability: {rain_str})."
                )

            # Schedule-aware commute decision assistance (deterministic Phase 7)
            user_text = (nlu.original_text.lower() if nlu and nlu.original_text else "")
            sched = getattr(advisory, "schedule_decision", None) or {}
            has_sched = sched.get("has_schedule", False)
            if has_sched or "umbrella" in user_text or ("8 am" in user_text and "5 pm" in user_text) or "commute" in user_text:
                dep_t = sched.get("departure_time", "8:00 AM")
                ret_t = sched.get("return_time", "5:00 PM")
                rec_umb = sched.get("recommend_umbrella", False)
                if not sched and weather and weather.rain_probability is not None:
                    rec_umb = (weather.rain_probability >= 30.0 or bool(reasoning.active_warnings))
                umbrella_rec = "Yes, carrying an umbrella is recommended" if rec_umb else "Carrying an umbrella is not strictly required for dry morning hours, but recommended if evening clouds build"
                risk_lvl = sched.get("departure_risk", "low")
                dep_prob_val = sched.get("departure_prob", weather.rain_probability if weather and weather.rain_probability is not None else 0.0)
                commute_line = f"{user_prefix}your commute has a {risk_lvl} rain risk around {dep_t}." if user_prefix else f"Your commute has a {risk_lvl} rain risk around {dep_t}."
                lines.append(f"\nCommute Decision ({dep_t} Departure — {ret_t} Return):")
                lines.append(f"- {commute_line}")
                lines.append(f"- Recommendation: {user_prefix}{umbrella_rec.lower() if user_prefix else umbrella_rec}.")
                lines.append(f"- Precipitation Risk: {dep_prob_val:.0f}% precipitation chance during transit window.")

            lines.append(f"\nAdvisory: {advisory.advisory_text}")

            if advisory.key_precautions:
                precautions_str = "\n- " + "\n- ".join(advisory.key_precautions)
                lines.append(f"\nRecommended Precautions:{precautions_str}")

            # Phase 9: Forecast Consistency & Multi-Source Agreement Explanation
            conf_factors = getattr(reasoning, "consistency_factors", {}) or {}
            conf_summary = conf_factors.get("summary")
            conf_lvl = getattr(reasoning, "confidence_level", None)
            conf_lvl_str = conf_lvl.value if hasattr(conf_lvl, "value") else (str(conf_lvl) if conf_lvl else "HIGH")

            if conf_summary:
                lines.append(f"\nForecast Consistency ({conf_lvl_str}): {conf_summary}")
            elif reasoning.source_agreement == SourceAgreementEnum.LOW:
                lines.append(f"\nForecast consistency is low because available sources disagree.")
            elif reasoning.source_agreement == SourceAgreementEnum.HIGH:
                lines.append(f"\nForecast consistency is high as available forecast sources broadly agree.")

            lines.append(
                f"\n(Source: {', '.join(reasoning.sources_used)} | Updated {reasoning.data_age_minutes}m ago | Forecast Consistency Score: {reasoning.consistency_score}/100 [Data Confidence Indicator: {conf_lvl_str}])"
            )

        return "\n".join(lines)
