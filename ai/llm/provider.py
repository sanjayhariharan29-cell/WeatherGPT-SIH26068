"""LLM Provider Abstraction Layer for WeatherGPT.

Enables clean decoupling between generation logic and underlying model providers
(e.g. Google Gemini, Groq, local mock, or fallback routing) per docs/09_AI_Design.md:621.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional, List
from ai.config import LLMConfig
from backend.config.logging import logger


class BaseLLMProvider(ABC):
    """Abstract interface for LLM text generation."""
    name: str = "base"

    def is_available(self) -> bool:
        """Indicates whether this provider has valid credentials and is ready."""
        return True

    @abstractmethod
    def generate_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Generates text from system instruction and user prompt."""
        pass


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini model provider using google-generativeai."""
    name: str = "gemini"

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.config = config or LLMConfig()
        self._model = None
        self.api_key = api_key or self.config.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model or self.config.model_name or "gemini-1.5-flash"

        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config={
                        "temperature": self.config.temperature,
                        "max_output_tokens": self.config.max_output_tokens,
                    }
                )
            except Exception as e:
                logger.debug("Failed initializing Gemini generative model: %s", type(e).__name__)
                self._model = None

    def __repr__(self) -> str:
        masked_key = "***REDACTED***" if self.api_key else "None"
        return f"GeminiLLMProvider(model='{self.model_name}', api_key='{masked_key}')"

    def is_available(self) -> bool:
        return self._model is not None

    def generate_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self._model:
            return None

        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self._model.generate_content(full_prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning("Gemini generation failed: %s", type(e).__name__)
            return None
        return None


class GroqLLMProvider(BaseLLMProvider):
    """Groq LPU model provider with resilient SDK and HTTPX support."""
    name: str = "groq"

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.config = config or LLMConfig()
        self.api_key = (
            api_key
            or getattr(self.config, "groq_api_key", None)
            or os.getenv("GROQ_API_KEY")
        )
        self.model_name = (
            model
            or getattr(self.config, "groq_model", None)
            or os.getenv("WEATHERGPT_GROQ_MODEL", "llama-3.3-70b-versatile")
        )

    def __repr__(self) -> str:
        masked_key = "***REDACTED***" if self.api_key else "None"
        return f"GroqLLMProvider(model='{self.model_name}', api_key='{masked_key}')"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.is_available():
            return None

        # 1. Try official groq SDK if installed
        try:
            import groq
            client = groq.Groq(api_key=self.api_key, timeout=self.config.timeout_seconds)
            completion = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_output_tokens,
            )
            if completion and completion.choices and completion.choices[0].message.content:
                return completion.choices[0].message.content.strip()
        except ImportError:
            pass
        except Exception as e:
            logger.warning("Groq SDK generation error (%s). Attempting HTTP fallback.", type(e).__name__)

        # 2. Resilient HTTPX OpenAI-compatible fallback
        try:
            import httpx
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_output_tokens
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0] and "content" in choices[0]["message"]:
                        return choices[0]["message"]["content"].strip()
                else:
                    logger.warning("Groq API returned HTTP %d", resp.status_code)
        except Exception as e:
            logger.warning("Groq HTTP generation failed: %s", type(e).__name__)

        return None


_UNSET = object()


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider for automated testing, offline demos, and failure simulation."""
    name: str = "mock"

    def __init__(
        self,
        canned_response: Any = _UNSET,
        should_fail: bool = False,
        simulate_timeout: bool = False,
        failure_exception: Optional[Exception] = None,
    ):
        self.canned_response = canned_response
        self.should_fail = should_fail
        self.simulate_timeout = simulate_timeout
        self.failure_exception = failure_exception

    def generate_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if self.simulate_timeout:
            raise TimeoutError("LLM provider timed out during text generation")
        if self.should_fail:
            if self.failure_exception:
                raise self.failure_exception
            return None
        if self.canned_response is None:
            return None
        if self.canned_response is not _UNSET:
            return self.canned_response

        # Deterministic grounded mock text generation for testing / offline
        import re
        sys_low = system_prompt.lower()
        usr_low = user_prompt.lower()

        is_ta = (
            "target output language (ta)" in sys_low
            or "target_language=ta" in sys_low
            or "output_language: ta" in usr_low
            or "detected language: ta" in usr_low
            or bool(re.search(r"[\u0B80-\u0BFF]", user_prompt))
        )
        is_hi = (
            "target output language (hi)" in sys_low
            or "target_language=hi" in sys_low
            or "output_language: hi" in usr_low
            or "detected language: hi" in usr_low
            or bool(re.search(r"[\u0900-\u097F]", user_prompt))
        )

        loc_match = re.search(r"Target Location:\s*([^\n\r]+)", user_prompt)
        loc = loc_match.group(1).strip() if loc_match else "Coimbatore"

        temp_match = re.search(r"Current Temperature:\s*([0-9.]+)", user_prompt)
        temp_val = f"{float(temp_match.group(1)):.1f}" if temp_match else "31.5"
        temp_int = f"{round(float(temp_val))}" if temp_match else "32"

        rain_match = re.search(r"Precipitation Probability:\s*([0-9.]+)", user_prompt) or re.search(r"Rain Prob(?:ability)?:\s*([0-9.]+)", user_prompt)
        rain_val = f"{round(float(rain_match.group(1)))}" if rain_match else "80"

        cond_match = re.search(r"Sky Condition:\s*([^\n\r]+)", user_prompt)
        cond = cond_match.group(1).strip() if cond_match else "Heavy Rain"

        src_match = re.search(r"Data Source:\s*([^\n\r]+)", user_prompt) or re.search(r"Source:\s*([^\n\r]+)", user_prompt)
        src = src_match.group(1).strip() if src_match else "IMD"

        score_match = re.search(r"Forecast Consistency Score:\s*([0-9]+)", user_prompt) or re.search(r"Consistency Score:\s*([0-9]+)", user_prompt)
        score = score_match.group(1).strip() if score_match else "85"

        adv_match = re.search(r"Advisory Guidance:\s*([^\n\r]+)", user_prompt) or re.search(r"Headline:\s*([^\n\r]+)", user_prompt)
        adv_text = adv_match.group(1).strip() if adv_match else "Moderate rain expected. Commute with care."

        has_warning = "[OFFICIAL WARNINGS]" in user_prompt and "Official Warnings: NONE_ACTIVE" not in user_prompt
        if has_warning:
            warn_match = re.search(r"⚠️ \[URGENT OFFICIAL ALERT\] ([^|(]+)", user_prompt)
            warn_title = warn_match.group(1).strip() if warn_match else "Cyclone Warning"
            if is_ta:
                return (
                    f"⚠️ [அதிகாரப்பூர்வ IMD எச்சரிக்கை: {warn_title}] {loc} பகுதியில் தீவிர வானிலை எச்சரிக்கை செயலில் உள்ளது.\n"
                    f"ஆலோசனை: {adv_text}\n"
                    f"(மூலம்: {src} | முன்னறிவிப்பு நிலைத்தன்மை: {score}/100)"
                )
            elif is_hi:
                return (
                    f"⚠️ [आधिकारिक IMD चेतावनी: {warn_title}] {loc} में गंभीर मौसम चेतावनी सक्रिय है।\n"
                    f"सलाह: {adv_text}\n"
                    f"(स्रोत: {src} | पूर्वानुमान संगति स्कोर: {score}/100)"
                )
            else:
                return (
                    f"[OFFICIAL IMD WARNING] CRITICAL ALERT: {warn_title}\n"
                    f"Affected Area: {loc}\n"
                    f"Critical Safety Instruction: Stay indoors and avoid travel.\n"
                    f"Explanation: Official alert in effect.\n"
                    f"Advisory: {adv_text}\n"
                    f"(Source: {src} | Forecast Consistency Score: {score}/100)"
                )

        user_prefix = ""
        name_match = re.search(r"User Profile:\s*Name=([A-Za-z0-9_ -]+?)(?:,|$|\.|\n)", user_prompt)
        if name_match:
            fname = name_match.group(1).strip().split()[0]
            if fname:
                user_prefix = f"{fname}, "

        direct_action_match = re.search(r"Direct Action Directive:\s*([^\n\r]+)", user_prompt)
        direct_action = direct_action_match.group(1).strip() if direct_action_match else ""

        if direct_action:
            if "unavailable" in direct_action.lower() or "not recommended" in direct_action.lower() or "தவிர்க்கவும்" in direct_action:
                return f"{user_prefix}{direct_action}"
            if is_ta:
                return (
                    f"{user_prefix}{direct_action}\n"
                    f"{loc}ல் தற்போதைய வெப்பநிலை {temp_val}°C ({temp_int}°C) மற்றும் மழை வாய்ப்பு {rain_val}% ஆகும்.\n"
                    f"ஆலோசனை: {adv_text}\n"
                    f"(மூலம்: {src} | தர நம்பகத்தன்மை: முன்னறிவிப்பு நிலைத்தன்மை: {score}/100)"
                )
            elif is_hi:
                return (
                    f"{user_prefix}{direct_action}\n"
                    f"{loc} में वर्तमान तापमान {temp_val}°C ({temp_int}°C) और बारिश की संभावना {rain_val}% है।\n"
                    f"सलाह: {adv_text}\n"
                    f"(स्रोत: {src} | डेटा गुणवत्ता स्कोर: पूर्वानुमान संगति स्कोर: {score}/100)"
                )
            return f"{user_prefix}{direct_action}"

        if "Historical Archive Status: UNAVAILABLE" in user_prompt:
            return f"{user_prefix}Historical weather records for {loc} are currently unavailable in official archives. SkyZen does not fabricate historical statistics."

        hist_scope = re.search(r"Dataset Scope: Historical meteorological observations for ([^ ]+) from ([0-9-]+) to ([0-9-]+)", user_prompt)
        if hist_scope:
            h_loc = hist_scope.group(1)
            h_start = hist_scope.group(2)
            h_end = hist_scope.group(3)
            h_rain_match = re.search(r"Historical Average Annual Rainfall:\s*([0-9.]+)", user_prompt)
            h_rain = h_rain_match.group(1) if h_rain_match else "1340.5"
            return (
                f"{user_prefix}Historically in {h_loc} ({h_start} to {h_end}), recorded total rainfall was {h_rain} mm "
                f"compared to a typical normal baseline of 1200.0 mm. Current conditions should be evaluated using live forecasts."
            )

        uq_match = re.search(r"(?:Original|User)\s+(?:Query|Request):\s*([^\n\r]+)", user_prompt, re.IGNORECASE)
        uq_text = uq_match.group(1).strip().lower() if uq_match else user_prompt.lower()

        cs_match = re.search(r"Consistency Summary:\s*([^\n\r]+)", user_prompt)
        is_low_conf = "data confidence indicator: low" in user_prompt.lower() or "source agreement: low" in user_prompt.lower()
        if cs_match and (is_low_conf or any(w in uq_text for w in ["disagree", "consistency", "conflict", "sources agree", "difference"])):
            cs_text = cs_match.group(1).strip()
            if is_ta:
                return (
                    f"{user_prefix}{cs_text}\n"
                    f"{loc}ல் தற்போதைய வெப்பநிலை {temp_val}°C ({temp_int}°C) மற்றும் மழை வாய்ப்பு {rain_val}% ஆகும்.\n"
                    f"ஆலோசனை: {adv_text}\n"
                    f"(மூலம்: {src} | தர நம்பகத்தன்மை: முன்னறிவிப்பு நிலைத்தன்மை: {score}/100)"
                )
            elif is_hi:
                return (
                    f"{user_prefix}{cs_text}\n"
                    f"{loc} में वर्तमान तापमान {temp_val}°C ({temp_int}°C) और बारिश की संभावना {rain_val}% है।\n"
                    f"सलाह: {adv_text}\n"
                    f"(स्रोत: {src} | डेटा गुणवत्ता स्कोर: पूर्वानुमान संगति स्कोर: {score}/100)"
                )
            else:
                return (
                    f"{user_prefix}{cs_text}\n"
                    f"In {loc}, current temperature is {temp_val}°C with a {rain_val}% chance of precipitation. Available sources disagree on forecast conditions.\n"
                    f"Advisory: {adv_text}\n"
                    f"(Source: {src} | Data Quality Score: Forecast Consistency Score: {score}/100)"
                )

        if "Current Weather Observation: UNAVAILABLE" in user_prompt or "status: UNAVAILABLE" in user_prompt.lower():
            if is_ta:
                return f"{user_prefix}{loc} பகுதிக்கான தற்போதைய வானிலை தரவு கிடைக்கவில்லை (unavailable). தயவுசெய்து அதிகாரப்பூர்வ முன்னறிவிப்பை பார்க்கவும்."
            elif is_hi:
                return f"{user_prefix}{loc} के लिए वर्तमान मौसम डेटा उपलब्ध नहीं है (unavailable)। कृपया आधिकारिक पूर्वानुमान देखें।"
            else:
                return f"{user_prefix}Current weather observation is unavailable for {loc}. Please check official local forecasts."

        if is_ta:
            return (
                f"{user_prefix}{loc}ல் தற்போதைய வெப்பநிலை {temp_val}°C ({temp_int}°C) மற்றும் மழை வாய்ப்பு {rain_val}% ஆகும் (வானிலை: {cond}).\n"
                f"ஆலோசனை: {adv_text}\n"
                f"(மூலம்: {src} | தர நம்பகத்தன்மை: முன்னறிவிப்பு நிலைத்தன்மை: {score}/100)"
            )
        elif is_hi:
            return (
                f"{user_prefix}{loc} में वर्तमान तापमान {temp_val}°C ({temp_int}°C) है और बारिश की संभावना {rain_val}% है (मौसम: {cond})।\n"
                f"सलाह: {adv_text}\n"
                f"(स्रोत: {src} | डेटा गुणवत्ता स्कोर: पूर्वानुमान संगति स्कोर: {score}/100)"
            )
        else:
            return (
                f"{user_prefix}In {loc}, current temperature is {temp_val}°C ({temp_int}°C) with a {rain_val}% chance of precipitation ({cond}).\n"
                f"Advisory: {adv_text}\n"
                f"(Source: {src} | Data Quality Score: Forecast Consistency Score: {score}/100)"
            )


class RoutingLLMProvider(BaseLLMProvider):
    """Orchestrates multi-provider routing with automatic failover.

    Tries configured primary provider first; on failure, rate limit, or timeout,
    transparently falls over to secondary provider.
    If all external LLM providers fail, delegates to the configured fallback provider.
    """
    name: str = "routing"

    def __init__(
        self,
        providers: List[BaseLLMProvider],
        fallback_provider: Optional[BaseLLMProvider] = None
    ):
        self.providers = [p for p in providers if p]
        self.fallback_provider = fallback_provider
        self.last_provider_used: Optional[str] = None

    def is_available(self) -> bool:
        return any(p.is_available() for p in self.providers) or (
            self.fallback_provider is not None and self.fallback_provider.is_available()
        )

    def generate_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        # Sequentially attempt generation across active providers
        for p in self.providers:
            if not p.is_available():
                continue
            try:
                result = p.generate_text(system_prompt, user_prompt)
                if result and result.strip():
                    self.last_provider_used = p.name
                    return result.strip()
            except Exception as e:
                logger.warning("Provider %s failed (%s). Failing over to next provider.", p.name, type(e).__name__)
                continue

        # All primary/secondary providers failed: delegate to fallback provider
        if self.fallback_provider:
            try:
                fb_result = self.fallback_provider.generate_text(system_prompt, user_prompt)
                if fb_result and fb_result.strip():
                    self.last_provider_used = getattr(self.fallback_provider, "name", "fallback")
                    return fb_result.strip()
            except Exception as e:
                logger.warning("Fallback provider failed: %s", type(e).__name__)

        self.last_provider_used = "deterministic_fallback"
        return None


def get_llm_provider(config: Optional[LLMConfig] = None) -> BaseLLMProvider:
    """Factory returning the appropriate configured LLM provider or multi-provider router."""
    from ai.config import get_ai_config
    cfg = config or get_ai_config().llm

    primary = (cfg.provider or "gemini").lower().strip()
    gemini_key = cfg.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    groq_key = getattr(cfg, "groq_api_key", None) or os.getenv("GROQ_API_KEY")

    gemini_prov = GeminiLLMProvider(cfg) if gemini_key else None
    groq_prov = GroqLLMProvider(cfg) if groq_key else None

    # Construct priority list based on configured primary provider
    candidate_providers: List[BaseLLMProvider] = []
    if primary == "groq":
        if groq_prov and groq_prov.is_available():
            candidate_providers.append(groq_prov)
        if gemini_prov and gemini_prov.is_available():
            candidate_providers.append(gemini_prov)
    else:  # default "gemini"
        if gemini_prov and gemini_prov.is_available():
            candidate_providers.append(gemini_prov)
        if groq_prov and groq_prov.is_available():
            candidate_providers.append(groq_prov)

    if candidate_providers:
        return RoutingLLMProvider(
            providers=candidate_providers,
            fallback_provider=MockLLMProvider()
        )

    # Default to mock/fallback provider when no external keys available
    return MockLLMProvider()
