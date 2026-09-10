"""Test Suite for SkyZen Phase 10: Voice Experience & Conversational AI Polish.

Tests:
1. Voice input (English, Tamil, Hindi)
2. Tanglish and Hinglish voice/text handling
3. Voice output (concise speech formatting, unit expansions)
4. Safety response order (Warning status -> Affected area -> Critical safety instruction -> Explanation)
5. Conversational filler prohibition ahead of active warnings (Rule 1f)
6. Voice error handling, audio validation, and STT/TTS resilience
7. Context reset & conversation history clearing
8. Anti-hallucination safeguards (weather values, phantom alerts, fabricated history)
9. Accessibility, screen-reader labels, and Material Symbols (no emoji UI)
10. Mobile Android integration and permissions
"""

import os
import re
import pytest
from datetime import datetime, timezone

from ai.models import (
    AdvisoryPriorityEnum,
    AdvisoryTypeEnum,
    ConfidenceLevelEnum,
    DecisionAdvisory,
    ForecastItem,
    FreshnessStatusEnum,
    HistoricalWeatherDataset,
    LanguageEnum,
    LocationInfo,
    NLUResult,
    OfficialAlert,
    RiskLevelEnum,
    SourceAgreementEnum,
    TimeContextEnum,
    ValidationCategoryEnum,
    ValidationStatusEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.nlu import parse_query
from ai.voice import (
    VoiceAIService,
    MockSTTProvider,
    MockTTSProvider,
    format_speech_friendly_text,
    format_concise_speech_text,
    EmptyAudioError,
    STTNoSpeechError,
    STTTimeoutError
)
from ai.voice.audio_validator import AudioValidator
from ai.llm.context_builder import build_grounded_context
from ai.llm.generator import GroundedLLMGenerator
from ai.validator.response_validator import ResponseValidator


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
ANDROID_DIR = os.path.join(REPO_ROOT, "android")


@pytest.mark.asyncio
async def test_01_voice_input_english_tamil_hindi():
    """1. Voice Input: verifies voice query processing across English, Tamil, and Hindi."""
    voice_service = VoiceAIService(
        stt_provider=MockSTTProvider(),
        tts_provider=MockTTSProvider(),
    )

    # English query
    resp_en = await voice_service.process_voice_query(
        transcript_override="What is the current weather in Coimbatore?",
        language="en",
        location_name="Coimbatore"
    )
    assert resp_en.transcript == "What is the current weather in Coimbatore?"
    assert resp_en.language == "en"
    assert resp_en.audio_available is True
    assert resp_en.audio_url is not None

    # Tamil query
    resp_ta = await voice_service.process_voice_query(
        transcript_override="கோயம்புத்தூரில் இன்று மழை வருமா?",
        language="ta",
        location_name="Coimbatore"
    )
    assert "மழை" in resp_ta.transcript
    assert resp_ta.language == "ta"
    assert resp_ta.audio_available is True

    # Hindi query
    resp_hi = await voice_service.process_voice_query(
        transcript_override="क्या आज कोयंबटूर में बारिश होगी?",
        language="hi",
        location_name="Coimbatore"
    )
    assert "बारिश" in resp_hi.transcript
    assert resp_hi.language == "hi"
    assert resp_hi.audio_available is True


@pytest.mark.asyncio
async def test_02_voice_input_tanglish_and_hinglish():
    """2. Tanglish & Hinglish: verifies natural conversational transliterated inputs."""
    voice_service = VoiceAIService(
        stt_provider=MockSTTProvider(),
        tts_provider=MockTTSProvider(),
    )

    # Tanglish input
    resp_tanglish = await voice_service.process_voice_query(
        transcript_override="Naalaiku morning college pogalama?",
        language="tanglish",
        location_name="Coimbatore"
    )
    assert resp_tanglish.transcript == "Naalaiku morning college pogalama?"
    # Tanglish maps into resolved target language (ta)
    assert resp_tanglish.language in ("ta", "tanglish")
    assert resp_tanglish.audio_available is True

    # Hinglish input
    resp_hinglish = await voice_service.process_voice_query(
        transcript_override="Aaj Coimbatore mein baarish hogi kya?",
        language="hinglish",
        location_name="Coimbatore"
    )
    assert resp_hinglish.transcript == "Aaj Coimbatore mein baarish hogi kya?"
    assert resp_hinglish.language in ("hi", "hinglish")
    assert resp_hinglish.audio_available is True


def test_03_voice_output_concise_speech_formatting():
    """3. Voice Output: verifies concise speech text, unit expansions, and telemetry stripping."""
    # Test text containing technical telemetry and markdown symbols
    raw_answer = (
        "### Weather Advisory for Coimbatore\n\n"
        "In Coimbatore, current temperature is 32.5°C with a 75% chance of precipitation (Rainy).\n"
        "- High wind gusts of 45 km/h recorded with 35 mm of rainfall.\n"
        "(Source: IMD, Open-Meteo | Updated 12m ago | Forecast Consistency Score: 85/100 [Data Confidence Indicator: HIGH])\n\n"
        "Please carry an umbrella and drive carefully on wet roads."
    )

    # English concise speech formatting
    concise_en = format_concise_speech_text(raw_answer, language="en")
    assert "###" not in concise_en
    assert "Forecast Consistency Score" not in concise_en
    assert "(Source:" not in concise_en
    assert "32.5 degrees Celsius" in concise_en
    assert "75 percent" in concise_en
    assert "35 millimeters" in concise_en
    assert "45 kilometers per hour" in concise_en

    # Tamil concise speech formatting
    raw_ta = (
        "கோயம்புத்தூரில் தற்போதைய வெப்பநிலை 31°C மற்றும் மழை வாய்ப்பு 80%.\n"
        "மழை அளவு 25 mm.\n"
        "(தகவல் மூலம்: IMD | புதுப்பிக்கப்பட்டது 15 நிமிடங்களுக்கு முன்)"
    )
    concise_ta = format_concise_speech_text(raw_ta, language="ta")
    assert "டிகிரி செல்சியஸ்" in concise_ta
    assert "சதவீதம்" in concise_ta
    assert "மில்லிமீட்டர்" in concise_ta
    assert "(தகவல் மூலம்" not in concise_ta

    # Hindi concise speech formatting
    raw_hi = (
        "कोयंबटूर में तापमान 30°C है और बारिश की संभावना 70% है।\n"
        "(स्रोत: IMD | 10 मिनट पहले)"
    )
    concise_hi = format_concise_speech_text(raw_hi, language="hi")
    assert "डिग्री सेल्सियस" in concise_hi
    assert "प्रतिशत" in concise_hi
    assert "(स्रोत:" not in concise_hi


def test_04_safety_response_order_warning_priority():
    """4. Safety Response Order: verifies official warning follows 1. Status -> 2. Area -> 3. Action -> 4. Explanation."""
    generator = GroundedLLMGenerator()
    nlu = parse_query("What is the weather today?")
    loc = LocationInfo(name="Chennai", latitude=13.08, longitude=80.27)

    alert = OfficialAlert(
        id="WARN-001",
        title="Cyclone Fengal Approaching",
        severity=RiskLevelEnum.CRITICAL,
        type="cyclone",
        description="Severe cyclonic storm making landfall near coast with torrential rains and gale winds.",
        source="IMD",
        issued_at=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
        affected_locations=["Chennai", "Kanchipuram"]
    )

    reasoning = WeatherReasoningResult(
        location="Chennai",
        overall_risk=RiskLevelEnum.CRITICAL,
        freshness=FreshnessStatusEnum.FRESH,
        source_agreement=SourceAgreementEnum.HIGH,
        evaluated_at=datetime.now(timezone.utc),
        active_warnings=[alert],
        sources_used=["IMD"],
        data_age_minutes=5,
        consistency_score=85,
        confidence_level=ConfidenceLevelEnum.HIGH,
        confidence_indicator="High"
    )

    advisory = DecisionAdvisory(
        persona="student",
        headline="Cyclone Alert Active",
        advisory_text="Severe cyclone approaching coast.",
        key_precautions=["Remain indoors", "Avoid coastal roads", "Do not travel"],
        risk_level=RiskLevelEnum.CRITICAL,
        priority=AdvisoryPriorityEnum.CRITICAL,
        official_warning_present=True,
        source_attribution="IMD",
        timestamp_info="Updated 5m ago"
    )

    resp = generator.generate(
        nlu=nlu,
        weather=None,
        reasoning=reasoning,
        advisory=advisory,
        target_language=LanguageEnum.EN
    )

    # Verify 4-step sequence in opening lines
    lines = [l.strip() for l in resp.split("\n") if l.strip()]
    assert "OFFICIAL IMD" in lines[0] and ("CRITICAL" in lines[0] or "EXTREME" in lines[0])
    assert "Affected Area:" in lines[1]
    assert "Critical Safety Instruction:" in lines[2]
    assert "Explanation:" in lines[3]


def test_05_safety_response_order_filler_rejection():
    """5. Filler Rejection: Rule 1f catches pleasantries/filler preceding active warnings."""
    loc = LocationInfo(name="Chennai", latitude=13.08, longitude=80.27)
    alert = OfficialAlert(
        id="WARN-002",
        title="Heavy Rain Warning",
        severity=RiskLevelEnum.HIGH,
        type="rain",
        description="Heavy downpours expected across the district.",
        source="IMD",
        issued_at=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
        affected_locations=["Chennai"]
    )

    reasoning = WeatherReasoningResult(
        location="Chennai",
        overall_risk=RiskLevelEnum.HIGH,
        freshness=FreshnessStatusEnum.FRESH,
        source_agreement=SourceAgreementEnum.HIGH,
        evaluated_at=datetime.now(timezone.utc),
        active_warnings=[alert],
        sources_used=["IMD"],
        data_age_minutes=10,
        consistency_score=80
    )

    advisory = DecisionAdvisory(
        persona="student",
        headline="Heavy Rain Warning",
        advisory_text="Heavy rain expected.",
        key_precautions=["Stay indoors"],
        risk_level=RiskLevelEnum.HIGH,
        priority=AdvisoryPriorityEnum.HIGH,
        official_warning_present=True,
        source_attribution="IMD",
        timestamp_info="Updated 10m ago"
    )

    # Bad response: Pleasantries bury the critical warning
    bad_filler_response = (
        "Hello! Hope you are having a wonderful and pleasant day! "
        "I would be glad to help you with your weather plans. "
        "By the way, there is an official warning for heavy rain in Chennai."
    )

    val_res = ResponseValidator.validate_response(
        response_text=bad_filler_response,
        reasoning=reasoning,
        advisory=advisory
    )

    assert val_res.is_valid is False
    assert val_res.status == ValidationStatusEnum.REJECT
    assert any("buried beneath conversational filler" in issue for issue in val_res.issues)


@pytest.mark.asyncio
async def test_06_voice_error_handling_and_permissions():
    """6. Voice Error Handling: verifies rejection of empty audio, timeouts, and graceful fallback."""
    voice_service = VoiceAIService(
        stt_provider=MockSTTProvider(simulate_timeout=True),
        tts_provider=MockTTSProvider(simulate_error=True)
    )

    # Rejection of empty input
    with pytest.raises(EmptyAudioError):
        await voice_service.process_voice_query()

    # STT timeout handled
    with pytest.raises(STTTimeoutError):
        await voice_service.process_voice_query(audio_bytes=b"MOCK_AUDIO_PAYLOAD")

    # TTS circuit-breaking fallback: returns text even when TTS provider fails
    working_stt = MockSTTProvider(forced_transcript="What is the weather today in Coimbatore?")
    broken_tts = MockTTSProvider(simulate_error=True)
    resilient_voice_service = VoiceAIService(stt_provider=working_stt, tts_provider=broken_tts)

    resp = await resilient_voice_service.process_voice_query(audio_bytes=b"MOCK_AUDIO_PAYLOAD")
    assert resp.transcript == "What is the weather today in Coimbatore?"
    assert resp.answer is not None
    assert len(resp.answer) > 10
    assert resp.audio_available is False
    assert resp.audio_url is None


def test_07_context_reset_action():
    """7. Context Reset: verifies reset button and handler exist in index.html and app.js."""
    index_html_path = os.path.join(FRONTEND_DIR, "index.html")
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")

    with open(index_html_path, "r", encoding="utf-8") as f:
        html = f.read()
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Reset button in HTML
    assert 'id="chatResetBtn"' in html
    assert 'onclick="resetConversationContext()"' in html
    assert 'aria-label="Reset Conversation Context"' in html
    assert 'restart_alt' in html

    # Reset handler in JS
    assert 'resetConversationContext' in js
    assert 'Conversation context reset' in js


def test_08_hallucination_safeguards():
    """8. Hallucination Safeguards: verifies rejection of invented weather numbers, phantom alerts, and fake history."""
    reasoning = WeatherReasoningResult(
        location="Coimbatore",
        overall_risk=RiskLevelEnum.LOW,
        sources_used=["IMD"],
        data_age_minutes=5,
        consistency_score=90,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        freshness="fresh",
        source_agreement="high"
    )

    weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.01, longitude=76.95),
        observed_at=datetime.now(timezone.utc),
        retrieved_at=datetime.now(timezone.utc),
        temperature=30.0,
        humidity=65.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Clear",
        source="IMD"
    )

    # 1. Unphysical temperature hallucination (68°C)
    val_unphysical = ResponseValidator.validate_response(
        response_text="The temperature in Coimbatore is currently 68°C with pleasant skies.",
        reasoning=reasoning,
        weather=weather
    )
    assert val_unphysical.is_valid is False
    assert any(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value in c for c in val_unphysical.violation_categories)

    # 2. Phantom official alert when none exists in ground truth
    val_phantom = ResponseValidator.validate_response(
        response_text="An official cyclone warning active evacuation order has been issued for Coimbatore.",
        reasoning=reasoning,
        weather=weather
    )
    assert val_phantom.is_valid is False
    assert any(ValidationCategoryEnum.FABRICATED_DATA.value in c for c in val_phantom.violation_categories)

    # 3. Fabricated historical weather figures when archive is unavailable
    hist_unavailable = HistoricalWeatherDataset(
        location=LocationInfo(name="Coimbatore", latitude=11.01, longitude=76.95),
        start_date="2023-01-01",
        end_date="2023-12-31",
        is_available=False,
        unavailability_reason="No records found"
    )
    val_fake_history = ResponseValidator.validate_response(
        response_text="In Coimbatore during 2023, it rained 1250 mm with an average temperature was 28°C.",
        reasoning=reasoning,
        weather=weather,
        historical_weather=hist_unavailable
    )
    assert val_fake_history.is_valid is False
    assert any(ValidationCategoryEnum.FABRICATED_DATA.value in c for c in val_fake_history.violation_categories)


def test_09_accessibility_and_material_symbols():
    """9. Accessibility & Material Symbols: verifies screen-reader labels, touch targets, and absence of raw emoji UI."""
    index_html_path = os.path.join(FRONTEND_DIR, "index.html")
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    styles_css_path = os.path.join(FRONTEND_DIR, "styles.css")

    with open(index_html_path, "r", encoding="utf-8") as f:
        html = f.read()
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()
    with open(styles_css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Material Symbols usage
    assert 'class="material-symbols-rounded' in html
    assert 'class="material-symbols-rounded' in js

    # No raw emoji UI characters inside HTML button/tag labels
    raw_emoji_pattern = re.compile(r'[\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\u2600-\u26FF\u2700-\u27BF\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF]')
    # Check button tags specifically in index.html
    button_matches = re.findall(r'<button[^>]*>(.*?)</button>', html, re.DOTALL)
    for btn in button_matches:
        assert not raw_emoji_pattern.search(btn), f"Found raw emoji in UI button: {btn}"

    # Screen-reader aria labels
    assert 'aria-label="Voice input"' in html
    assert 'aria-label="Send message"' in html
    assert 'aria-label="Reset Conversation Context"' in html

    # Accessible speech button and listening animations in CSS
    assert '.speech-btn' in css
    assert '#voiceBtn.listening' in css
    assert 'min-height: 44px;' in css


def test_10_mobile_and_android_integration():
    """10. Mobile Android Integration: verifies permissions in AndroidManifest and asset synchronization."""
    manifest_path = os.path.join(ANDROID_DIR, "app", "src", "main", "AndroidManifest.xml")
    assert os.path.exists(manifest_path)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = f.read()

    # Permissions
    assert 'android.permission.RECORD_AUDIO' in manifest
    assert 'android.permission.MODIFY_AUDIO_SETTINGS' in manifest
    assert 'android.permission.POST_NOTIFICATIONS' in manifest
    assert 'android.permission.INTERNET' in manifest

    # Assets synced in public directory
    public_assets_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "assets", "public")
    assert os.path.exists(os.path.join(public_assets_dir, "index.html"))
    assert os.path.exists(os.path.join(public_assets_dir, "app.js"))
    assert os.path.exists(os.path.join(public_assets_dir, "styles.css"))
