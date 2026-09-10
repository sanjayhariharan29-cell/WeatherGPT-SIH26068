"""Conversation Memory Manager for WeatherGPT.

Provides thread-safe in-memory session cache with TTL expiration,
bounded turn history windows, and context update/reset lifecycle methods.
"""

import threading
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any

from backend.config.logging import logger
from ai.memory.models import ConversationContext, ConversationTurn


class ConversationMemoryManager:
    """Manages short-term conversational context across multi-turn interactions."""

    def __init__(self, ttl_seconds: int = 1800, max_turns: int = 10):
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        self._contexts: Dict[str, ConversationContext] = {}
        self._lock = threading.RLock()

    def get_context(self, conversation_id: str) -> ConversationContext:
        """Retrieves active conversation context, or creates a new one if missing or expired."""
        with self._lock:
            now = datetime.now(timezone.utc)
            if conversation_id in self._contexts:
                ctx = self._contexts[conversation_id]
                if ctx.is_expired(now):
                    logger.info("Conversation context %s expired (TTL=%ds). Resetting.", conversation_id, self.ttl_seconds)
                    del self._contexts[conversation_id]
                else:
                    return ctx

            # Create fresh context
            new_ctx = ConversationContext(
                conversation_id=conversation_id,
                ttl_seconds=self.ttl_seconds,
                created_at=now,
                updated_at=now
            )
            self._contexts[conversation_id] = new_ctx
            return new_ctx

    def update_context(
        self,
        conversation_id: str,
        user_turn: Optional[ConversationTurn] = None,
        assistant_turn: Optional[ConversationTurn] = None,
        location: Optional[str] = None,
        date_context: Optional[str] = None,
        time_context: Optional[str] = None,
        persona: Optional[str] = None,
        language: Optional[str] = None,
        active_topic: Optional[str] = None,
        last_intent: Optional[str] = None,
        entities: Optional[Dict[str, Any]] = None,
        departure_time: Optional[str] = None,
        return_time: Optional[str] = None
    ) -> ConversationContext:
        """Updates conversational state and appends turns within bounded window."""
        with self._lock:
            now = datetime.now(timezone.utc)
            ctx = self.get_context(conversation_id)
            ctx.updated_at = now

            if location:
                ctx.location = location
                # Track recent locations (bounded to last 5) for ambiguity checks
                if not ctx.recent_locations or ctx.recent_locations[-1] != location:
                    ctx.recent_locations.append(location)
                    if len(ctx.recent_locations) > 5:
                        ctx.recent_locations = ctx.recent_locations[-5:]

            if date_context:
                ctx.date_context = date_context
            if time_context:
                ctx.time_context = time_context
            if departure_time:
                ctx.departure_time = departure_time
            if return_time:
                ctx.return_time = return_time
            if persona:
                ctx.persona = persona
            if language:
                ctx.language = language
            if active_topic:
                ctx.active_topic = active_topic
            if last_intent:
                ctx.last_intent = last_intent
            if entities:
                ctx.recent_entities.update(entities)

            # Append turns and enforce maximum window bounds
            if user_turn:
                ctx.turns.append(user_turn)
            if assistant_turn:
                ctx.turns.append(assistant_turn)

            if len(ctx.turns) > self.max_turns:
                ctx.turns = ctx.turns[-self.max_turns:]

            self._contexts[conversation_id] = ctx
            return ctx

    def reset_context(self, conversation_id: str) -> None:
        """Explicitly resets and clears context for a conversation."""
        with self._lock:
            if conversation_id in self._contexts:
                logger.info("Explicitly resetting conversation context for %s", conversation_id)
                del self._contexts[conversation_id]

    def cleanup_expired(self) -> int:
        """Purges all expired conversation sessions from memory."""
        with self._lock:
            now = datetime.now(timezone.utc)
            expired_keys = [
                cid for cid, ctx in self._contexts.items()
                if ctx.is_expired(now)
            ]
            for cid in expired_keys:
                del self._contexts[cid]
            return len(expired_keys)

    def count_active(self) -> int:
        """Returns total active unexpired sessions."""
        with self._lock:
            now = datetime.now(timezone.utc)
            return sum(1 for ctx in self._contexts.values() if not ctx.is_expired(now))


# Singleton default memory manager
memory_manager = ConversationMemoryManager()
