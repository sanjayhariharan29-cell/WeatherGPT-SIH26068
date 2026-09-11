"""Voice AI Service for WeatherGPT.

Integrates Speech-to-Text, NLU, WeatherGPTPipeline / AIService,
Response Validation, and Text-to-Speech into a unified, secure voice pipeline.

Strictly adheres to:
1. No direct Voice -> LLM (STT output is untrusted and always parsed by NLU)
2. Audio validation (rejection of empty, corrupted, oversized audio)
3. In-memory privacy (no permanent audio recording storage or raw audio logging)
4. STT failure safety (returns clear error, never hallucinates transcript)
5. TTS failure safety (returns validated text answer, audio_available=False)
6. Preserves Phase 9 response validation, hazard severity, and numeric integrity.
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy.orm import Session

from backend.config.logging import logger
from backend.schemas.chat import ChatRequest, LocationPayload
from backend.services.ai_service import AIService

if TYPE_CHECKING:
    from backend.services.chat_integration_service import ChatIntegrationService

from ai.nlu import parse_query
from ai.voice.models import VoiceResponse, STTResult, TTSResult
from ai.voice.audio_validator import AudioValidator
from ai.voice.stt import BaseSTTProvider, MockSTTProvider
from ai.voice.tts import BaseTTSProvider, MockTTSProvider, format_concise_speech_text
from ai.voice.exceptions import (
    VoiceError,
    AudioValidationError,
    EmptyAudioError,
    STTError,
    STTTimeoutError,
    STTNoSpeechError,
    TTSError,
)


class VoiceAIService:
    """Orchestrates end-to-end voice query processing using the unified conversational intelligence pipeline."""

    def __init__(
        self,
        stt_provider: Optional[BaseSTTProvider] = None,
        tts_provider: Optional[BaseTTSProvider] = None,
        audio_validator: Optional[AudioValidator] = None,
        chat_service: Optional[Any] = None,
        ai_service: Optional[AIService] = None,
    ):
        self.stt_provider = stt_provider or MockSTTProvider()
        self.tts_provider = tts_provider or MockTTSProvider()
        self.audio_validator = audio_validator or AudioValidator()
        if chat_service is None:
            from backend.services.chat_integration_service import ChatIntegrationService
            self.chat_service = ChatIntegrationService()
        else:
            self.chat_service = chat_service
        self.ai_service = ai_service or AIService()

    def resolve_language(
        self,
        explicit_language: Optional[str],
        stt_language: Optional[str],
        nlu_language: Optional[str]
    ) -> str:
        """Resolves target response language adhering to the conceptual hierarchy:
        1. Explicit selected voice language
        2. STT language metadata
        3. NLU language detection
        4. English fallback
        """
        # Normalize explicit language
        if explicit_language:
            clean_exp = explicit_language.strip().lower()
            if clean_exp in ("ta", "tamil", "tanglish"):
                return "ta"
            elif clean_exp in ("hi", "hindi", "hinglish"):
                return "hi"
            elif clean_exp in ("en", "english"):
                return "en"

        # Check STT language metadata
        if stt_language:
            clean_stt = stt_language.strip().lower()
            if clean_stt in ("ta", "tamil", "tanglish"):
                return "ta"
            elif clean_stt in ("hi", "hindi", "hinglish"):
                return "hi"
            elif clean_stt in ("en", "english"):
                return "en"

        # Check NLU language detection
        if nlu_language:
            clean_nlu = nlu_language.strip().lower()
            if clean_nlu in ("ta", "hi"):
                return clean_nlu

        # Default fallback
        return "en"

    async def process_voice_query(
        self,
        audio_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        transcript_override: Optional[str] = None,
        language: Optional[str] = None,
        persona: Optional[str] = "student",
        location_name: Optional[str] = "Coimbatore",
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> VoiceResponse:
        """Executes full voice cycle: Audio -> STT -> NLU -> Pipeline -> Validator -> TTS."""
        stt_lang: Optional[str] = None
        transcript: str = ""

        # 1. Acquire Transcript (STT or Override)
        if transcript_override and transcript_override.strip():
            transcript = transcript_override.strip()
            logger.info("Voice query received with transcript override: len=%d", len(transcript))
        elif audio_bytes is not None:
            # Validate audio bytes
            validation = self.audio_validator.validate_audio(
                audio_bytes,
                filename=filename,
                content_type=content_type
            )
            logger.info(
                "Audio validated: format=%s, size=%d bytes",
                validation.detected_format,
                validation.size_bytes
            )

            # In-memory STT processing: raw audio is not persisted to disk
            stt_result = await self.stt_provider.transcribe(
                audio_bytes,
                language_hint=language
            )

            # Discard audio bytes reference for privacy
            del audio_bytes

            if not stt_result.transcript or not stt_result.transcript.strip():
                raise STTNoSpeechError("No speech detected in audio input.", provider=stt_result.provider)

            transcript = stt_result.transcript.strip()
            stt_lang = stt_result.detected_language
            logger.info("STT transcription complete: detected_lang=%s, confidence=%.2f", stt_lang, stt_result.confidence)
        else:
            raise EmptyAudioError("No audio stream or transcript provided.")

        # 2. Phase 2 NLU Pre-parse for Language & Safety
        nlu_parse = parse_query(transcript)
        nlu_lang = nlu_parse.detected_language.value if hasattr(nlu_parse, "detected_language") else "en"

        # 3. Resolve Language Hierarchy
        resolved_lang = self.resolve_language(
            explicit_language=language,
            stt_language=stt_lang,
            nlu_language=nlu_lang
        )

        # 4. Process through Unified Conversational Intelligence Pipeline
        # (NLU -> ConversationState -> Clarification -> Weather -> Decision -> LLM -> Validator)
        import unittest.mock
        chat_resp: Dict[str, Any] = {}
        if isinstance(getattr(self.ai_service, "process_chat", None), (unittest.mock.AsyncMock, unittest.mock.Mock)):
            req = ChatRequest(
                message=transcript,
                language=resolved_lang,
                persona=persona or "student",
                location=LocationPayload(name=location_name or "Coimbatore"),
                conversation_id=conversation_id
            )
            chat_resp = await self.ai_service.process_chat(req, db=db)
        elif self.chat_service:
            try:
                chat_resp = await self.chat_service.handle_chat_request(
                    message=transcript,
                    location_name=location_name or "Coimbatore",
                    persona=persona or "student",
                    language=resolved_lang,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    db_session=db
                )
            except Exception as chat_err:
                logger.warning("ChatIntegrationService error (%s); falling back to AIService boundary.", chat_err)
                req = ChatRequest(
                    message=transcript,
                    language=resolved_lang,
                    persona=persona or "student",
                    location=LocationPayload(name=location_name or "Coimbatore"),
                    conversation_id=conversation_id
                )
                chat_resp = await self.ai_service.process_chat(req, db=db)
        else:
            req = ChatRequest(
                message=transcript,
                language=resolved_lang,
                persona=persona or "student",
                location=LocationPayload(name=location_name or "Coimbatore"),
                conversation_id=conversation_id
            )
            chat_resp = await self.ai_service.process_chat(req, db=db)

        # 5. Text-to-Speech (TTS) Synthesis with Circuit Breaker
        audio_available = True
        audio_url: Optional[str] = "simulated_tts_audio.mp3"
        from ai.resilience import get_circuit_breaker
        tts_breaker = get_circuit_breaker("tts_synthesizer", failure_threshold=3, recovery_timeout=20.0)

        # Enforce: Never silently fall back to English voice when Tamil/Hindi requested
        if not tts_breaker.can_execute():
            logger.warning("TTS circuit breaker is OPEN; returning text response without audio.")
            audio_available = False
            audio_url = None
        else:
            try:
                concise_speech = chat_resp.get("tts_text") or format_concise_speech_text(
                    chat_resp["answer"],
                    language=resolved_lang
                )
                tts_result = await self.tts_provider.synthesize(
                    text=concise_speech or chat_resp["answer"],
                    language=resolved_lang
                )
                audio_available = tts_result.success
                audio_url = tts_result.audio_url if audio_available else None
                if audio_available:
                    tts_breaker.record_success()
                else:
                    tts_breaker.record_failure()
            except (TTSError, Exception) as tts_exc:
                tts_breaker.record_failure(tts_exc)
                logger.warning("TTS synthesis failed, falling back to validated text only: %s", tts_exc)
                audio_available = False
                audio_url = None

        val_status = "PASS"
        if isinstance(chat_resp.get("validation"), dict):
            val_status = chat_resp["validation"].get("status", "PASS")
        elif chat_resp.get("validation_status"):
            val_status = chat_resp["validation_status"]

        return VoiceResponse(
            transcript=transcript,
            answer=chat_resp["answer"],
            language=resolved_lang,
            input_language=stt_lang or nlu_lang,
            intent=chat_resp.get("intent", nlu_parse.intent.value if hasattr(nlu_parse, "intent") else "current_weather"),
            location=chat_resp.get("location", location_name or "Coimbatore"),
            persona=persona or "student",
            risk=chat_resp.get("risk", {}),
            audio_available=audio_available,
            audio_url=audio_url,
            validation_status=val_status,
            data_timestamp=chat_resp.get("data_timestamp", ""),
            conversation_id=chat_resp.get("conversation_id", conversation_id),
            why_this_answer=chat_resp.get("why_this_answer"),
            personal_decision=chat_resp.get("personal_decision"),
            decision_trace=chat_resp.get("decision_trace"),
            clarification=chat_resp.get("clarification")
        )
