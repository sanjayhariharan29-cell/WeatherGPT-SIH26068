# Phase 12 — Voice AI Integration

**Role:** Person 1 (AI & Weather Intelligence Stack)  
**Status:** COMPLETE  
**Repository Branch:** `main`  
**Dependencies:** Phase 0–11 completed (NLU, Reasoner, Hazards, Advisory, LLM, Multilingual, Response Validation, Evaluation, Backend AI Integration)

---

## 1. Executive Summary

Phase 12 integrates seamless voice interaction into the WeatherGPT AI architecture without creating a secondary or parallel reasoning pipeline. All voice inputs pass through Speech-to-Text (STT), enter the existing Natural Language Understanding (NLU) pipeline, flow through meteorological reasoning, hazard detection, advisory generation, and LLM grounded response synthesis, undergo strict Phase 9 Response Validation, and finally undergo speech-friendly Text-to-Speech (TTS) synthesis.

```
VOICE INPUT (Audio Upload / Base64 / Stream)
   │
   ▼
[AudioValidator] (Sanitization, Container Magic Bytes, 10MB limit)
   │
   ▼
[SpeechToTextProvider] (MockSTT / Bhashini / Whisper)
   │
   ▼
Untrusted Text Transcript
   │
   ▼
[Phase 2 NLU: parse_query()] (Intent, Entities, Language Identification)
   │
   ▼
[Weather Intelligence Pipeline] (Live Observations, Consensus, IMD Alerts)
   │
   ▼
[Phase 3 & 4 Weather Reasoner & Hazard Engine]
   │
   ▼
[Phase 7 Advisory Engine & Persona Resolution]
   │
   ▼
[Phase 5 Grounded Context & LLM Response Layer]
   │
   ▼
[Phase 9 ResponseValidator & Anti-Hallucination Guard] (MANDATORY GATE)
   │
   ▼
Validated Natural Language Response
   │
   ▼
[format_speech_friendly_text()] (Authority & Numeric Preservation)
   │
   ▼
[TextToSpeechProvider] (MockTTS / Bhashini / Browser Audio Stream)
   │
   ▼
Voice Response (Spoken Audio + Accessible URL + Structured Metadata)
```

---

## 2. Voice Architecture & Provider Abstraction

### 2.1 Single Intelligence Pipeline Guarantee
Voice is an input/output modal adapter. It does **not** make weather reasoning decisions or communicate directly with the LLM. 
- Raw audio is converted to untrusted text.
- That untrusted text is processed by existing NLU and validated by existing guardrails.
- Spoken audio is generated strictly from the validated response.

### 2.2 Speech-to-Text (STT) Abstraction
Defined in [`ai/voice/stt.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/ai/voice/stt.py):
- `BaseSTTProvider(ABC)` with asynchronous `transcribe(audio_bytes: bytes, language_hint: Optional[str] = None) -> STTResult`.
- `MockSTTProvider`: Provides deterministic offline testing for English, Tamil, Hindi, Tanglish, and Hinglish, plus fault injection capabilities (`simulate_timeout`, `simulate_error`, `simulate_no_speech`).
- Readily extensible for Bhashini, OpenAI Whisper, or browser-native Web Speech API.

### 2.3 Text-to-Speech (TTS) Abstraction
Defined in [`ai/voice/tts.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/ai/voice/tts.py):
- `BaseTTSProvider(ABC)` with asynchronous `synthesize(text: str, language: str = "en") -> TTSResult`.
- `MockTTSProvider`: Synthesizes deterministic audio streams and provides mock MP3 URLs (`/static/audio/{lang}_simulated_tts_audio.mp3`) without calling external billable APIs.
- Integrates `format_speech_friendly_text()` to guarantee phonetic safety while keeping numbers and warnings unaltered.

---

## 3. Supported Languages & Conceptual Resolution Hierarchy

### 3.1 Supported Languages
- **English (`en`)**: Native queries (e.g., "Will it rain tomorrow in Coimbatore?").
- **Tamil (`ta`)**: Native Tamil script queries (e.g., "நாளைக்கு கோயம்புத்தூரில் மழை வருமா?").
- **Hindi (`hi`)**: Native Devanagari script queries (e.g., "कल कोयंबटूर में बारिश होगी क्या?").
- **Tanglish (`tanglish`)**: Latin-script transliterated Tamil (e.g., "Naalaiku Coimbatore la mazhai varuma?"). Transcribed to text, parsed by Phase 2 NLU, and mapped to Tamil (`ta`) for spoken response synthesis.
- **Hinglish (`hinglish`)**: Latin-script transliterated Hindi (e.g., "Aaj Coimbatore mein baarish hogi kya?"). Parsed by Phase 2 NLU and mapped to Hindi (`hi`) for spoken response synthesis.

### 3.2 Conceptual Resolution Hierarchy (Step 7)
Target spoken language is deterministically resolved using the following order of precedence:
1. **Explicit Selected Voice Language:** Parameter passed by client/UI.
2. **STT Language Metadata:** Language reported by the speech recognition model.
3. **NLU Language Detection:** Language identified by Phase 2 script/lexicon analysis.
4. **English Fallback:** Safe default if language cannot be determined.

```python
def resolve_language(explicit_language, stt_language, nlu_language) -> str:
    # 1. Explicit selection
    if explicit_language in ("ta", "hi", "en", ...): return normalized
    # 2. STT metadata
    if stt_language in ("ta", "tanglish", "hi", "hinglish", ...): return mapped
    # 3. NLU detection
    if nlu_language in ("ta", "hi"): return nlu_language
    # 4. Fallback
    return "en"
```

---

## 4. Audio Validation & Security Controls

Defined in [`ai/voice/audio_validator.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/ai/voice/audio_validator.py):
1. **Empty Audio Rejection:** Payloads of 0 bytes raise `EmptyAudioError`.
2. **Size Bounding:** Payloads exceeding 10 MB default raise `OversizedAudioError` (preventing denial-of-service memory exhaustion).
3. **Container Format Validation:** Inspects magic headers (`WAV/RIFF`, `MP3/ID3`, `OggS`, `WebM`, `FLAC`, `M4A`). Corrupted headers raise `CorruptedAudioError` or `UnsupportedAudioFormatError`.
4. **Filename Sanitization:** Blocks path traversal (`..`, `/`, `\`) and null-byte injection (`\x00`).

---

## 5. Privacy & Ephemeral In-Memory Processing

WeatherGPT adheres to strict privacy-by-design principles:
- **No Permanent Disk Storage:** Audio payloads are processed in-memory.
- **Immediate Disposal:** The raw byte array is explicitly dereferenced (`del audio_bytes`) immediately after STT transcription.
- **No Biometric Logging:** Raw microphone audio data is never logged to application loggers or stored in database tables.

---

## 6. Failure Modes & Fault Tolerance

### 6.1 STT Failure (Step 14)
If speech recognition encounters a timeout, service crash, or silence:
- An explicit domain error (`STTTimeoutError`, `STTNoSpeechError`, `STTError`) is raised.
- Returns HTTP 400 Bad Request with a clear message: `"Sorry, I couldn't understand the voice input."`
- **Zero Hallucination:** The system will **never** invent or hallucinate a transcript when STT fails.

### 6.2 TTS Failure (Step 15)
If speech synthesis fails or is temporarily unavailable:
- The error is captured and logged.
- The interaction **does not fail**.
- The validated natural language answer is returned with `audio_available: false` and `audio_url: null`.

---

## 7. Meteorological Safety & Numeric Preservation

### 7.1 Warning Preservation (Step 16 & 19)
- If an official IMD alert exists (e.g., Red or Orange warning for cyclone or torrential rain), the response generated by the pipeline is strictly verified by Phase 9 `ResponseValidator`.
- The voice output is prohibited from stating "everything is safe" or softening an official warning into a "possible warning".

### 7.2 Numeric Preservation (Step 18)
Meteorological quantities must not have their semantic meaning altered by speech formatting:
- `31.5°C` -> `31.5 degrees Celsius` (EN) / `31.5 டிகிரி செல்சியஸ்` (TA) / `31.5 डिग्री सेल्सियस` (HI)
- `80%` -> `80 percent` (EN) / `80 சதவீதம்` (TA) / `80 प्रतिशत` (HI)
- `64.5 mm` -> `64.5 millimeters` (EN) / `64.5 மில்லிமீட்டர்` (TA) / `64.5 मिलीमीटर` (HI)
- `25 km/h` -> `25 kilometers per hour` (EN) / `25 கிலோமீட்டர்/மணி` (TA) / `25 किलोमीटर प्रति घंटा` (HI)

All digits and decimal precisions remain 100% faithful to live verified data.

---

## 8. Backend Contract & Person 2 Boundary

The FastAPI endpoint `POST /api/v1/voice/query` in [`backend/api/voice.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/api/voice.py) coordinates through the clean service interface:
```python
voice_result = await _voice_service.process_voice_query(
    audio_bytes=audio_bytes,
    filename=filename,
    content_type=content_type,
    transcript_override=transcript,
    language=language,
    persona=persona,
    location_name=location_name,
    db=db
)
```

The response conforms to Person 2's expected contract while including extended voice metadata:
```json
{
  "transcript": "Naalaiku morning college pogalama?",
  "answer": "...",
  "language": "ta",
  "input_language": "tanglish",
  "intent": "forecast",
  "location": "Coimbatore",
  "persona": "student",
  "risk": { "level": "low", "consistency": "single_source", "consistency_score": 0.0 },
  "audio_available": true,
  "audio_url": "/static/audio/ta_simulated_tts_audio.mp3",
  "validation_status": "PASS",
  "data_timestamp": "2026-09-09T00:00:00Z"
}
```

---

## 9. Test Suite Verification

The dedicated test suite [`tests/test_ai_voice_depth.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/tests/test_ai_voice_depth.py) implements 26 scenarios:
1. English STT transcription
2. Tamil STT transcription
3. Hindi STT transcription
4. Tanglish transcript processing
5. Hinglish transcript processing
6. Empty audio byte stream rejection
7. Corrupted header detection
8. Oversized upload rejection (>10MB)
9. STT timeout handling
10. STT service error handling
11. Untrusted transcript entering NLU (no direct Voice->LLM)
12. Multi-tier language propagation hierarchy
13. Tamil natural language response generation
14. Hindi natural language response generation
15. English natural language response generation
16. Official alert & authority preservation
17. Hazard & severity level preservation
18. Numeric precision preservation in speech
19. Phase 9 ResponseValidator enforcement
20. TTS speech synthesis success
21. TTS failure graceful degradation
22. Full Voice -> STT -> NLU -> Reasoner -> Hazard -> Advisory -> LLM -> Validator -> TTS flow
23. Ephemeral in-memory privacy verification
24. Offline deterministic mock provider execution
25. End-to-end deterministic scenario ("Naalaiku Coimbatore la mazhai varuma?")
26. FastAPI `/api/v1/voice/query` multipart audio upload & transcript integration

---

## 10. Limitations & Production Considerations

1. **Local Offline Testing:** Tests use `MockSTTProvider` and `MockTTSProvider` to ensure fast, deterministic CI/CD execution without billing or network dependency.
2. **Production Providers:** In live deployment, `BhashiniSTTProvider` / `WhisperSTTProvider` and `BhashiniTTSProvider` can be plugged in by inheriting `BaseSTTProvider` and `BaseTTSProvider`.
3. **Ambient Noise:** Real-world field usage under heavy rain or wind may require front-end noise cancellation before STT ingestion.

---

## 11. Next Phase

- **Phase 13:** AI Conversation Memory & Multi-turn Context.
