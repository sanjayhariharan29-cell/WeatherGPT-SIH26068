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


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider for automated testing, offline demos, and failure simulation."""
    name: str = "mock"

    def __init__(
        self,
        canned_response: Optional[str] = None,
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
        return self.canned_response


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
        self.fallback_provider = fallback_provider or MockLLMProvider()
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
