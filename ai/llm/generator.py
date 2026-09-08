"""LLM Generation Engine for WeatherGPT.

Uses provider abstraction (Gemini / Mock) with the Grounded Context Builder,
fast-path Grounding Safety Guard, and resilient deterministic template fallback.
"""

from typing import List, Optional
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

    def generate_response(
        self,
        nlu: NLUResult,
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory,
        forecast: Optional[List[ForecastItem]] = None,
        safety_guidance: Optional[List[str]] = None
    ) -> GroundedResponse:
        """Generates a verified, grounded natural language answer conforming to GroundedResponse contract."""
        context = build_grounded_context(
            nlu=nlu,
            weather=weather,
            reasoning=reasoning,
            advisory=advisory,
            forecast=forecast,
            safety_guidance=safety_guidance
        )

        system_prompt = SYSTEM_INSTRUCTION.format(
            target_language=nlu.detected_language.value,
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
        fallback_answer = self._generate_fallback(nlu, weather, reasoning, advisory, context)
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
        safety_guidance: Optional[List[str]] = None
    ) -> str:
        """String generation interface preserving complete backward compatibility."""
        return self.generate_response(
            nlu=nlu,
            weather=weather,
            reasoning=reasoning,
            advisory=advisory,
            forecast=forecast,
            safety_guidance=safety_guidance
        ).answer

    def _generate_fallback(
        self,
        nlu: NLUResult,
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory,
        context: Optional[GroundedContext] = None
    ) -> str:
        """Deterministic, grounded template generator for offline/resilience/guard failure use."""
        is_tamil = nlu.detected_language in (LanguageEnum.TA, LanguageEnum.TANGLISH)
        loc = reasoning.location

        temp_str = f"{weather.temperature:.0f}°C" if (weather and weather.temperature is not None) else "கிடைக்கவில்லை" if is_tamil else "unavailable"
        rain_str = f"{weather.rain_probability:.0f}%" if (weather and weather.rain_probability is not None) else "கிடைக்கவில்லை" if is_tamil else "unavailable"
        cond_str = weather.weather_condition if (weather and weather.weather_condition) else "தெரியவில்லை" if is_tamil else "unavailable"

        lines: List[str] = []

        if is_tamil:
            if reasoning.active_warnings:
                alert = reasoning.active_warnings[0]
                lines.append(f"⚠️ [அதிகாரப்பூர்வ IMD எச்சரிக்கை] {alert.title}: {alert.description}")

            lines.append(
                f"{loc}-ல் தற்போதைய வெப்பநிலை {temp_str}, மழை வாய்ப்பு {rain_str}, வானிலை: {cond_str}."
            )
            lines.append(f"\nஆலோசனை: {advisory.advisory_text}")

            if advisory.key_precautions:
                precautions_str = "\n- " + "\n- ".join(advisory.key_precautions)
                lines.append(f"\nமுக்கிய பாதுகாப்பு வழிகாட்டுதல்கள்:{precautions_str}")

            lines.append(
                f"\n(தகவல் மூலம்: {', '.join(reasoning.sources_used)} | புதுப்பிக்கப்பட்டது {reasoning.data_age_minutes} நிமிடங்களுக்கு முன் | தர நம்பகத்தன்மை: {reasoning.consistency_score}/100)"
            )
        else:
            if reasoning.active_warnings:
                alert = reasoning.active_warnings[0]
                lines.append(f"⚠️ [OFFICIAL IMD WARNING] {alert.title}: {alert.description}")

            if weather and weather.temperature is not None and weather.rain_probability is not None:
                lines.append(
                    f"In {loc}, current temperature is {temp_str} with a {rain_str} chance of precipitation ({cond_str})."
                )
            else:
                lines.append(
                    f"In {loc}, current observation data is partially unavailable (Temperature: {temp_str}, Precipitation probability: {rain_str})."
                )

            lines.append(f"\nAdvisory: {advisory.advisory_text}")

            if advisory.key_precautions:
                precautions_str = "\n- " + "\n- ".join(advisory.key_precautions)
                lines.append(f"\nRecommended Precautions:{precautions_str}")

            lines.append(
                f"\n(Source: {', '.join(reasoning.sources_used)} | Updated {reasoning.data_age_minutes}m ago | Data Quality Score: {reasoning.consistency_score}/100)"
            )

        return "\n".join(lines)
