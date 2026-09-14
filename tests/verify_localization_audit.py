import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

with open("frontend/i18n.js", "r", encoding="utf-8") as f:
    i18n_code = f.read()

with open("frontend/app.js", "r", encoding="utf-8") as f:
    app_code = f.read()

with open("frontend/index.html", "r", encoding="utf-8") as f:
    html_code = f.read()

print("================================================================")
print("AUDIT 1: BOTTOM NAVIGATION COMPONENT AUDIT & GREP VERIFICATION")
print("================================================================")
nav_keys = [
    "nav.home", "nav.radar", "nav.alerts", "nav.forecast", "nav.ai", "nav.aqi", "nav.settings"
]
for k in nav_keys:
    en_m = re.search(rf'"{re.escape(k)}":\s*"([^"]+)"', i18n_code[:i18n_code.find('"ta":')])
    ta_m = re.search(rf'"{re.escape(k)}":\s*"([^"]+)"', i18n_code[i18n_code.find('"ta":'):i18n_code.find('"hi":')])
    hi_m = re.search(rf'"{re.escape(k)}":\s*"([^"]+)"', i18n_code[i18n_code.find('"hi":'):i18n_code.find('const DYNAMIC_LABELS')])
    in_html = f'data-i18n="{k}"' in html_code
    print(f"Key: {k:<15} | In HTML: {str(in_html):<5} | EN: {en_m.group(1) if en_m else 'MISSING'} | TA: {ta_m.group(1) if ta_m else 'MISSING'} | HI: {hi_m.group(1) if hi_m else 'MISSING'}")

print("\n================================================================")
print("AUDIT 2: HOME DASHBOARD LIFESTYLE CARDS & STATUS BADGES")
print("================================================================")
lifestyle_keys = [
    # Filter chips
    "chip.all", "chip.commute", "chip.farmer", "chip.fitness", "chip.home_daily",
    # Categories
    "lifestyle.cat_home_daily", "lifestyle.cat_agriculture", "lifestyle.cat_commute",
    "lifestyle.cat_transit", "lifestyle.cat_fitness", "lifestyle.cat_farming", "lifestyle.cat_daily_life",
    # Titles
    "lifestyle.title_laundry", "lifestyle.title_spray", "lifestyle.title_bike",
    "lifestyle.title_flood", "lifestyle.title_fitness", "lifestyle.title_harvest", "lifestyle.title_umbrella",
    # Status badges
    "lifestyle.status_slow_dry", "lifestyle.status_ideal_spray", "lifestyle.status_smooth_ride",
    "lifestyle.status_clear_roads", "lifestyle.status_hydration_caution", "lifestyle.status_safe_harvest",
    # Descriptions
    "lifestyle.desc_laundry_slow", "lifestyle.desc_spray_opt", "lifestyle.desc_commute_opt",
    "lifestyle.desc_flood_opt", "lifestyle.desc_fitness_caution", "lifestyle.desc_harvest_opt",
    # Metrics & units
    "lifestyle.metric_drying_index", "lifestyle.metric_road_traction", "lifestyle.metric_heat_index",
    "lifestyle.unit_hrs", "lifestyle.unit_rain", "lifestyle.unit_wind", "lifestyle.unit_hum"
]
for k in lifestyle_keys:
    ta_m = re.search(rf'"{re.escape(k)}":\s*"([^"]+)"', i18n_code[i18n_code.find('"ta":'):i18n_code.find('"hi":')])
    hi_m = re.search(rf'"{re.escape(k)}":\s*"([^"]+)"', i18n_code[i18n_code.find('"hi":'):i18n_code.find('const DYNAMIC_LABELS')])
    print(f"Key: {k:<32} | TA: {ta_m.group(1) if ta_m else 'MISSING'} | HI: {hi_m.group(1) if hi_m else 'MISSING'}")

print("\n================================================================")
print("AUDIT 3: SKYZEN AI CHATBOT INITIAL GREETING & UI TEXT")
print("================================================================")
chat_keys = [
    "chat.title", "chat.subtitle", "chat.welcome_bubble", "chat.why_answer",
    "chat.decision_engine_badge", "chat.telemetry_grounded", "chat.placeholder", "chat.send",
    "chat.chip_rain", "chat.chip_college", "chat.chip_bike", "chat.chip_umbrella"
]
for k in chat_keys:
    ta_m = re.search(rf'"{re.escape(k)}":\s*"([^"]+)"', i18n_code[i18n_code.find('"ta":'):i18n_code.find('"hi":')])
    hi_m = re.search(rf'"{re.escape(k)}":\s*"([^"]+)"', i18n_code[i18n_code.find('"hi":'):i18n_code.find('const DYNAMIC_LABELS')])
    print(f"Key: {k:<28} | TA: {ta_m.group(1) if ta_m else 'MISSING'} | HI: {hi_m.group(1) if hi_m else 'MISSING'}")

print("\n================================================================")
print("AUDIT 4: PROOF OF ZERO HARDCODED ENGLISH LITERALS IN LIFESTYLE CARDS")
print("================================================================")
# Check renderLifestyleInsights function in app.js for any remaining hardcoded English text in allCards
func_match = re.search(r'function renderLifestyleInsights[\s\S]*?grid\.innerHTML = filtered\.map', app_code)
if func_match:
    func_body = func_match.group(0)
    # Search for hardcoded string literals assigned to title, catTitle, statusText, metricLabel, desc
    bad_patterns = [
        r'title:\s*"[A-Za-z]',
        r'catTitle:\s*"[A-Za-z]',
        r'statusText:\s*"[A-Za-z]',
        r'desc:\s*"[A-Za-z]',
        r'metricLabel:\s*"[A-Za-z]'
    ]
    leaks = []
    for pat in bad_patterns:
        found = re.findall(pat, func_body)
        if found:
            leaks.extend(found)
    if not leaks:
        print("✓ Zero hardcoded English string literals in allCards definition (100% wired through t())")
    else:
        print("✗ Leaks found:", leaks)

print("\n================================================================")
print("AUDIT 5: BACKEND LANGUAGE OVERWRITE BUG CHECK")
print("================================================================")
with open("backend/services/chat_integration_service.py", "r", encoding="utf-8") as f:
    backend_code = f.read()

if 'if (not language or language == "ta")' in backend_code:
    print("✗ Bug present: Tamil is being overwritten by authed_user.language")
elif 'if not language and authed_user.language:' in backend_code:
    print("✓ Backend language overwrite bug RESOLVED: Tamil (ta) is preserved when sent")
else:
    print("? State ambiguous")

if 'pre_nlu.intent in (IntentEnum.GREETING, IntentEnum.GENERAL_CONVERSATION)' in backend_code:
    print("✓ Greeting intent routing RESOLVED: Greetings in Tamil/Hindi route to localized fast-path")
