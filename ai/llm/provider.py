"""LLM Provider Abstraction Layer for WeatherGPT.

Enables clean decoupling between generation logic and underlying model providers
(e.g. Google Gemini, local mock, or fallback) per docs/09_AI_Design.md:621.
"""

from abc import ABC, abstractmethod
from typing import Optional
from ai.config import LLMConfig


class BaseLLMProvider(ABC):
    """Abstract interface for LLM text generation."""

    @abstractmethod
    def generate_text(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Generates text from system instruction and user prompt."""
        pass


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini model provider using google-generativeai."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._model = None

        if self.config.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.config.api_key)
                self._model = genai.GenerativeModel(
                    model_name=self.config.model_name,
                    generation_config={
                        "temperature": self.config.temperature,
                        "max_output_tokens": self.config.max_output_tokens,
                    }
                )
            except Exception:
                self._model = None

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
        except Exception:
            return None
        return None


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider for automated testing, offline demos, and failure simulation."""

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


def get_llm_provider(config: Optional[LLMConfig] = None) -> BaseLLMProvider:
    """Factory returning the appropriate configured LLM provider."""
    from ai.config import get_ai_config
    cfg = config or get_ai_config().llm

    if cfg.provider == "gemini" and cfg.api_key:
        provider = GeminiLLMProvider(cfg)
        if provider.is_available():
            return provider

    # Default to mock/fallback provider
    return MockLLMProvider()
