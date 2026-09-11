"""WeatherGPT Conversational Memory & Context Package.

Provides short-term conversational context tracking, entity inheritance,
reference and pronoun resolution, multi-location ambiguity detection,
and bounded TTL-based session memory.
"""

from ai.memory.models import (
    ConversationTurn,
    ConversationContext,
    ResolvedQueryContext,
    ConversationState,
    TurnTypeEnum,
    ClarificationState
)
from ai.memory.resolver import ContextResolver
from ai.memory.manager import ConversationMemoryManager, memory_manager
from ai.memory.state_service import ConversationStateService, state_service

__all__ = [
    "ConversationTurn",
    "ConversationContext",
    "ResolvedQueryContext",
    "ConversationState",
    "TurnTypeEnum",
    "ClarificationState",
    "ContextResolver",
    "ConversationMemoryManager",
    "memory_manager",
    "ConversationStateService",
    "state_service",
]
