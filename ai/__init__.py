"""WeatherGPT AI & Intelligence Layer.

Owned by Person 1. Implements NLU, Weather Reasoning, Decision Engine,
RAG Safety Knowledge, Grounded LLM Generation, and Response Validation
for MoES / IMD — SIH26068.
"""

from ai.config import (
    AIConfig,
    LLMConfig,
    MeteorologicalThresholds,
    default_config,
    get_ai_config,
)
from ai.models import (
    DecisionAdvisory,
    ExtractedEntities,
    ForecastItem,
    HazardDetection,
    IntentEnum,
    LanguageEnum,
    LocationInfo,
    NLUResult,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    ValidationResult,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.nlu import (
    classify_intent,
    detect_language,
    extract_entities,
    parse_query,
)
from ai.reasoner import (
    WeatherReasoner,
    calculate_consistency_score,
    check_data_freshness,
    detect_hazards,
    evaluate_source_agreement,
)
from ai.decision import DecisionEngine
from ai.validator import ResponseValidator
from ai.rag import SAFETY_KNOWLEDGE_CORPUS, retrieve_safety_guidance
from ai.llm import (
    BaseLLMProvider,
    GeminiLLMProvider,
    GroundedLLMGenerator,
    MockLLMProvider,
    build_grounded_prompt,
    get_llm_provider,
)
from ai.pipeline import WeatherGPTPipeline

__all__ = [
    # Configuration
    "AIConfig",
    "LLMConfig",
    "MeteorologicalThresholds",
    "default_config",
    "get_ai_config",
    # Models
    "PersonaEnum",
    "LanguageEnum",
    "IntentEnum",
    "RiskLevelEnum",
    "LocationInfo",
    "WeatherRecord",
    "ForecastItem",
    "OfficialAlert",
    "ExtractedEntities",
    "NLUResult",
    "HazardDetection",
    "WeatherReasoningResult",
    "DecisionAdvisory",
    "ValidationResult",
    # NLU
    "parse_query",
    "detect_language",
    "classify_intent",
    "extract_entities",
    # Reasoner
    "WeatherReasoner",
    "check_data_freshness",
    "detect_hazards",
    "evaluate_source_agreement",
    "calculate_consistency_score",
    # Decision
    "DecisionEngine",
    # Validator
    "ResponseValidator",
    # RAG
    "SAFETY_KNOWLEDGE_CORPUS",
    "retrieve_safety_guidance",
    # LLM & Pipeline
    "BaseLLMProvider",
    "GeminiLLMProvider",
    "MockLLMProvider",
    "get_llm_provider",
    "GroundedLLMGenerator",
    "build_grounded_prompt",
    "WeatherGPTPipeline"
]
