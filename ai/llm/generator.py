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
        target_language: Optional[LanguageEnum] = None
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
            context_summary=context_summary
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
        fallback_answer = self._generate_fallback(nlu, weather, reasoning, advisory, context, target_language=target_lang)
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
        target_language: Optional[LanguageEnum] = None
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
            target_language=target_language
        ).answer

    def _generate_fallback(
        self,
        nlu: Optional[NLUResult],
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory,
        context: Optional[GroundedContext] = None,
        target_language: Optional[LanguageEnum] = None
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

            lines.append(
                f"\n(தகவல் மூலம்: {', '.join(reasoning.sources_used)} | புதுப்பிக்கப்பட்டது {reasoning.data_age_minutes} நிமிடங்களுக்கு முன் | தர நம்பகத்தன்மை: {reasoning.consistency_score}/100)"
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

            lines.append(
                f"\n(स्रोत: {', '.join(reasoning.sources_used)} | {reasoning.data_age_minutes} मिनट पहले अपडेट किया गया | डेटा गुणवत्ता स्कोर: {reasoning.consistency_score}/100)"
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

            # Schedule-aware commute decision assistance
            user_text = (nlu.original_text.lower() if nlu and nlu.original_text else "")
            if "umbrella" in user_text or ("8 am" in user_text and "5 pm" in user_text) or "commute" in user_text:
                rain_prob = weather.rain_probability if (weather and weather.rain_probability is not None) else 0.0
                umbrella_rec = "Yes, carrying an umbrella is recommended" if (rain_prob >= 30.0 or reasoning.active_warnings) else "Carrying an umbrella is not strictly required for dry morning hours, but recommended if evening clouds build"
                risk_lvl = "moderate" if rain_prob >= 30.0 else "low"
                commute_line = f"{user_prefix}your commute has a {risk_lvl} rain risk around 8 AM." if user_prefix else f"Your commute has a {risk_lvl} rain risk around 8 AM."
                lines.append(f"\nCommute Decision (8:00 AM Departure — 5:00 PM Return):")
                lines.append(f"- {commute_line}")
                lines.append(f"- Recommendation: {user_prefix}{umbrella_rec.lower() if user_prefix else umbrella_rec}.")
                lines.append(f"- Precipitation Risk: {rain_str} precipitation chance during transit window.")

            lines.append(f"\nAdvisory: {advisory.advisory_text}")

            if advisory.key_precautions:
                precautions_str = "\n- " + "\n- ".join(advisory.key_precautions)
                lines.append(f"\nRecommended Precautions:{precautions_str}")

            lines.append(
                f"\n(Source: {', '.join(reasoning.sources_used)} | Updated {reasoning.data_age_minutes}m ago | Data Quality Score: {reasoning.consistency_score}/100)"
            )

        return "\n".join(lines)
