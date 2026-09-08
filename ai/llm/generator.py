"""LLM Generation Engine for WeatherGPT.

Uses provider abstraction (Gemini / Mock) with a resilient,
deterministic template fallback for offline/test environments.
"""

from typing import Optional
from ai.config import AIConfig, get_ai_config
from ai.llm.prompts import SYSTEM_INSTRUCTION, build_grounded_prompt
from ai.llm.provider import BaseLLMProvider, GeminiLLMProvider, get_llm_provider
from ai.models import (
    DecisionAdvisory,
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

    def generate(
        self,
        nlu: NLUResult,
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory
    ) -> str:
        """Generates a verified, grounded natural language answer."""
        prompt = build_grounded_prompt(
            nlu=nlu,
            weather=weather,
            reasoning=reasoning,
            advisory=advisory
        )

        system_prompt = SYSTEM_INSTRUCTION.format(
            target_language=nlu.detected_language.value,
            persona=advisory.persona.value,
            source=", ".join(reasoning.sources_used)
        )

        # Attempt generation via configured provider
        if self.provider:
            response_text = self.provider.generate_text(
                system_prompt=system_prompt,
                user_prompt=prompt
            )
            if response_text and response_text.strip():
                return response_text.strip()

        # Deterministic Grounded Generation Fallback
        return self._generate_fallback(nlu, weather, reasoning, advisory)

    def _generate_fallback(
        self,
        nlu: NLUResult,
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory
    ) -> str:
        """Deterministic, grounded template generator for offline/resilience use."""
        is_tamil = nlu.detected_language in (LanguageEnum.TA, LanguageEnum.TANGLISH)
        loc = reasoning.location

        temp_str = f"{weather.temperature:.0f}°C" if weather else "N/A"
        rain_str = f"{weather.rain_probability:.0f}%" if weather else "N/A"
        cond_str = weather.weather_condition if weather else "Clear"

        if is_tamil:
            lines = []
            if reasoning.active_warnings:
                alert = reasoning.active_warnings[0]
                lines.append(f"⚠️ [அதிகாரப்பூர்வ எச்சரிக்கை] {alert.title}: {alert.description}")

            lines.append(
                f"{loc}-ல் தற்போதைய வெப்பநிலை {temp_str}, மழை வாய்ப்பு {rain_str}, வானிலை: {cond_str}."
            )
            lines.append(f"\nஆலோசனை: {advisory.advisory_text}")

            if advisory.key_precautions:
                precautions_str = "\n- " + "\n- ".join(advisory.key_precautions)
                lines.append(f"\nமுக்கிய பாதுகாப்பு வழிகாட்டுதல்கள்:{precautions_str}")

            lines.append(
                f"\n(தகவல் மூலம்: {', '.join(reasoning.sources_used)} | புதுப்பிக்கப்பட்டது {reasoning.data_age_minutes} நிமிடங்களுக்கு முன் | நிலைப்புத்தன்மை: {reasoning.consistency_score}/100)"
            )
            return "\n".join(lines)
        else:
            lines = []
            if reasoning.active_warnings:
                alert = reasoning.active_warnings[0]
                lines.append(f"⚠️ [OFFICIAL WARNING] {alert.title}: {alert.description}")

            lines.append(
                f"In {loc}, current temperature is {temp_str} with a {rain_str} chance of rain ({cond_str})."
            )
            lines.append(f"\nAdvisory: {advisory.advisory_text}")

            if advisory.key_precautions:
                precautions_str = "\n- " + "\n- ".join(advisory.key_precautions)
                lines.append(f"\nRecommended Precautions:{precautions_str}")

            lines.append(
                f"\n(Source: {', '.join(reasoning.sources_used)} | Updated {reasoning.data_age_minutes}m ago | Consistency: {reasoning.consistency_score}/100)"
            )
            return "\n".join(lines)
