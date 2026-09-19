"""
Unit & Integration Tests: Native Capacitor Text-to-Speech (@capacitor-community/text-to-speech)
Verifies native Android plugin registration, manifest queries, DEX bytecode inclusion,
and multilingual speech routing (en-IN, ta-IN, hi-IN) with graceful fallback.
"""

import os
import json
import zipfile
import subprocess
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
ANDROID_DIR = os.path.join(REPO_ROOT, "android")
APK_PATH = os.path.join(REPO_ROOT, "SkyZen-release.apk")
APP_JS_PATH = os.path.join(FRONTEND_DIR, "app.js")
ANDROID_APP_JS_PATH = os.path.join(ANDROID_DIR, "app", "src", "main", "assets", "public", "app.js")
PACKAGE_JSON_PATH = os.path.join(REPO_ROOT, "package.json")
CAP_SETTINGS_GRADLE = os.path.join(ANDROID_DIR, "capacitor.settings.gradle")
MANIFEST_XML_PATH = os.path.join(ANDROID_DIR, "app", "src", "main", "AndroidManifest.xml")


def test_01_package_json_and_capacitor_gradle_registration():
    """1. Test plugin is listed in package.json and capacitor.settings.gradle."""
    assert os.path.exists(PACKAGE_JSON_PATH)
    with open(PACKAGE_JSON_PATH, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    assert "@capacitor-community/text-to-speech" in pkg.get("dependencies", {}), "Missing TTS dependency in package.json"

    assert os.path.exists(CAP_SETTINGS_GRADLE)
    with open(CAP_SETTINGS_GRADLE, "r", encoding="utf-8") as f:
        gradle_content = f.read()
    assert ":capacitor-community-text-to-speech" in gradle_content, "Missing TTS plugin in capacitor.settings.gradle"


def test_02_android_manifest_tts_service_queries():
    """2. Test AndroidManifest declares TTS_SERVICE query for Android 11+ package visibility."""
    assert os.path.exists(MANIFEST_XML_PATH)
    with open(MANIFEST_XML_PATH, "r", encoding="utf-8") as f:
        manifest_content = f.read()
    assert "android.intent.action.TTS_SERVICE" in manifest_content, "Must declare TTS_SERVICE query in AndroidManifest"


def test_03_release_apk_contains_native_tts_bytecode():
    """3. Test built release APK bundles native TextToSpeech classes in DEX bytecode."""
    assert os.path.exists(APK_PATH), f"Release APK missing at {APK_PATH}"
    with zipfile.ZipFile(APK_PATH, "r") as z:
        dex_files = [n for n in z.namelist() if n.endswith(".dex")]
        assert len(dex_files) > 0, "No DEX files in release APK"
        
        found_tts = False
        for dex in dex_files:
            data = z.read(dex)
            if b"com/getcapacitor/community/tts/TextToSpeech" in data or b"TextToSpeechPlugin" in data:
                found_tts = True
                break
        assert found_tts, "TextToSpeech plugin bytecode not found in release APK DEX files"


def test_04_synchronized_frontend_assets():
    """4. Test frontend/app.js is synchronized with android/app/src/main/assets/public/app.js."""
    assert os.path.exists(APP_JS_PATH)
    assert os.path.exists(ANDROID_APP_JS_PATH)
    assert os.path.getsize(APP_JS_PATH) == os.path.getsize(ANDROID_APP_JS_PATH), "app.js file sizes must match"


def test_05_javascript_native_tts_multilingual_execution():
    """5. Test multilingual speech synthesis in English, Tamil, and Hindi with graceful fallback via Node.js."""
    node_test_script = """
    const fs = require('fs');
    const path = require('path');

    // Minimal browser environment simulation
    global.localStorage = { getItem: () => null, setItem: () => null, removeItem: () => null };
    global.navigator = { userAgent: "Mozilla/5.0 (Linux; Android 14)" };
    global.window = {
      location: { protocol: 'https:', hostname: 'localhost', port: '' },
      localStorage: global.localStorage,
      navigator: global.navigator,
      I18N: { currentLanguage: 'en' },
      addEventListener: () => {}
    };
    let capturedNotice = null;
    const noticeEl = {
      classList: { remove: () => {}, add: () => {} },
      style: {},
      set innerHTML(val) { capturedNotice = val; },
      get innerHTML() { return capturedNotice; },
      set textContent(val) { capturedNotice = val; },
      get textContent() { return capturedNotice; }
    };

    global.document = {
      getElementById: (id) => {
        if (id === 'mobileNotice' || id === 'noticeText') {
          return noticeEl;
        }
        return {
          value: 'general',
          classList: { add: () => {}, remove: () => {} },
          setAttribute: () => {},
          innerHTML: ''
        };
      },
      querySelectorAll: () => [],
      addEventListener: () => {}
    };

    // Load app.js code
    const appJsContent = fs.readFileSync(path.resolve(__dirname, 'frontend/app.js'), 'utf8');
    
    // Evaluate app.js within this scope
    eval(appJsContent);

    async function runSuite() {
      const results = {};

      // 1. Configure Mock Native Capacitor Environment
      let speakCalls = [];
      let isSupportedMap = {
        'en-IN': true,
        'ta-IN': false, // Tamil not installed on test phone
        'hi-IN': true   // Hindi installed on test phone
      };

      window.Capacitor = {
        isNativePlatform: () => true,
        isPluginAvailable: (name) => name === 'TextToSpeech',
        Plugins: {
          TextToSpeech: {
            isLanguageSupported: async ({ lang }) => ({ supported: Boolean(isSupportedMap[lang]) }),
            speak: async (opts) => {
              speakCalls.push(opts);
              if (!isSupportedMap[opts.lang]) {
                throw new Error("This language is not supported.");
              }
            },
            stop: async () => {}
          }
        }
      };

      // TEST A: English on native Android
      const btnEn = { classList: { add: () => {}, remove: () => {} }, innerHTML: '' };
      capturedNotice = null;
      await window.toggleSpeakMessage(btnEn, "Sunny and warm today with 31°C.", "en");
      results.english = {
        spoke: speakCalls.some(c => c.lang === 'en-IN' && c.text.includes('Sunny')),
        calledLang: speakCalls.find(c => c.text.includes('Sunny'))?.lang
      };

      // TEST B: Tamil on native Android (language pack not installed)
      const btnTa = { classList: { add: () => {}, remove: () => {} }, innerHTML: '' };
      capturedNotice = null;
      await window.toggleSpeakMessage(btnTa, "இன்று மிதமான மழை பெய்யக்கூடும்.", "ta");
      results.tamil_missing_pack = {
        noticeShown: capturedNotice,
        expectedGraceful: Boolean(capturedNotice && capturedNotice.includes("Tamil voice not available on this device"))
      };

      // TEST C: Tamil installed on native Android
      isSupportedMap['ta-IN'] = true;
      capturedNotice = null;
      speakCalls = [];
      await window.toggleSpeakMessage(btnTa, "இன்று மிதமான மழை பெய்யக்கூடும்.", "ta");
      results.tamil_installed = {
        spoke: speakCalls.some(c => c.lang === 'ta-IN'),
        calledLang: speakCalls.find(c => c.lang === 'ta-IN')?.lang
      };

      // TEST D: Hindi on native Android
      const btnHi = { classList: { add: () => {}, remove: () => {} }, innerHTML: '' };
      capturedNotice = null;
      speakCalls = [];
      await window.toggleSpeakMessage(btnHi, "आज तापमान 31 डिग्री सेल्सियस रहेगा।", "hi");
      results.hindi = {
        spoke: speakCalls.some(c => c.lang === 'hi-IN'),
        calledLang: speakCalls.find(c => c.lang === 'hi-IN')?.lang
      };

      // TEST E: Web/Desktop Fallback (non-native platform)
      window.Capacitor.isNativePlatform = () => false;
      let webSpeechCalled = false;
      window.speechSynthesis = {
        speaking: false,
        cancel: () => {},
        getVoices: () => [{ name: 'Google English', lang: 'en-IN', default: true }],
        speak: () => { webSpeechCalled = true; }
      };
      global.SpeechSynthesisUtterance = function(t) { this.text = t; };

      const btnWeb = { classList: { add: () => {}, remove: () => {} }, innerHTML: '' };
      await window.toggleSpeakMessage(btnWeb, "Desktop browser test message.", "en");
      results.web_fallback = { webSpeechCalled };

      console.log(JSON.stringify(results));
    }

    runSuite().catch(e => {
      console.error(e);
      process.exit(1);
    });
    """

    res = subprocess.run(
        ["node", "-e", node_test_script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    assert res.returncode == 0, f"Node test execution failed:\n{res.stderr}\n{res.stdout}"
    
    data = json.loads(res.stdout.strip().split("\n")[-1])
    assert data["english"]["spoke"], "Native TTS English speech failed"
    assert data["english"]["calledLang"] == "en-IN", "English must pass en-IN"
    assert data["tamil_missing_pack"]["expectedGraceful"], "Missing Tamil pack must notify: 'Tamil voice not available on this device'"
    assert data["tamil_installed"]["spoke"], "Native TTS Tamil speech failed when installed"
    assert data["tamil_installed"]["calledLang"] == "ta-IN", "Tamil must pass ta-IN"
    assert data["hindi"]["spoke"], "Native TTS Hindi speech failed"
    assert data["hindi"]["calledLang"] == "hi-IN", "Hindi must pass hi-IN"
    assert data["web_fallback"]["webSpeechCalled"], "Web Speech API fallback must work on non-native browsers"
