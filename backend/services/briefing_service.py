"""Skizen Personalized Weather SMS Briefing Service.

Phase 1 Scope:
Deterministic, role-aware, multilingual meteorological SMS message generator (<320 chars)
with Skizen-derived risk assessment, dynamic reasoning bullets ("Why did I get this?"),
and non-directive official advisory cross-references.

Reuses:
- User & UserPreference models (user ID, registered mobile, persona, preferred language, last known location)
- WeatherManager (OpenWeather primary, Open-Meteo secondary, IMD alerts)
- WeatherReasoner (safety, data completeness, hazard detection, source agreement)
- DecisionEngine (calibrated thresholds, persona advisories)
- Multilingual mappings (EN, TA, HI)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session

from backend.db.models import User, UserPreference
from backend.services.weather_manager import WeatherManager
from ai.models import (
    PersonaEnum,
    RiskLevelEnum,
    FreshnessStatusEnum,
    LanguageEnum,
    WeatherReasoningResult,
    DecisionAdvisory,
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
)
from ai.reasoner.reasoner import WeatherReasoner
from ai.decision.decision_engine import DecisionEngine
from ai.llm.multilingual import translate_condition
from backend.schemas.briefing import PersonalizedBriefingResponse

logger = logging.getLogger("weathergpt.services.briefing")

# IST Timezone (UTC + 05:30)
IST = timezone(timedelta(hours=5, minutes=30))


class PersonalizedBriefingService:
    """Service to orchestrate personalized, role-aware weather briefings."""

    def __init__(self, weather_manager: Optional[WeatherManager] = None):
        self.weather_manager = weather_manager or WeatherManager()

    @staticmethod
    def _normalize_role(role_str: Optional[str]) -> str:
        """Normalizes role strings into supported canonical keys."""
        if not role_str:
            return "student"
        r = role_str.strip().lower()
        if r in ("fisherman", "marine", "fisher"):
            return "fisherman"
        if r in ("farmer", "agriculture", "farming"):
            return "farmer"
        if r in ("commuter", "traveler", "traveller", "transit"):
            return "commuter"
        if r in ("outdoor_worker", "worker", "construction", "delivery", "outdoor"):
            return "outdoor_worker"
        if r in ("student", "college", "school"):
            return "student"
        return "student"

    @staticmethod
    def _normalize_language(lang_str: Optional[str]) -> LanguageEnum:
        """Resolves target language to EN, TA, or HI."""
        if not lang_str:
            return LanguageEnum.EN
        l = lang_str.strip().lower()
        if l in ("ta", "tamil", "tanglish"):
            return LanguageEnum.TA
        if l in ("hi", "hindi", "hinglish"):
            return LanguageEnum.HI
        if l in ("mr", "marathi"):
            return LanguageEnum.MR
        if l in ("te", "telugu"):
            return LanguageEnum.TE
        return LanguageEnum.EN

    @staticmethod
    def _derive_skizen_risk_status(
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory,
        lang: LanguageEnum
    ) -> Tuple[str, str]:
        """Derives the Skizen-specific risk status and localized display label.
        
        Status: LOW, MODERATE, HIGH.
        Always clearly labeled as '(Skizen-derived assessment)' — never as an official government rating.
        """
        raw_risk = reasoning.overall_risk
        active_warnings = reasoning.active_warnings or []
        has_warnings = len(active_warnings) > 0

        # Deterministic risk derivation
        if raw_risk in (RiskLevelEnum.EXTREME, RiskLevelEnum.HIGH) or (has_warnings and any(w.severity == RiskLevelEnum.HIGH for w in active_warnings)):
            level = "HIGH"
            if lang == LanguageEnum.TA:
                label = "🔴 அதிக ஆபத்து (Skizen மதிப்பீடு)"
            elif lang == LanguageEnum.HI:
                label = "🔴 उच्च जोखिम (Skizen मूल्यांकन)"
            else:
                label = "🔴 HIGH RISK (Skizen-derived assessment)"
        elif raw_risk == RiskLevelEnum.MEDIUM or has_warnings or (reasoning.detected_hazards and len(reasoning.detected_hazards) > 0):
            level = "MODERATE"
            if lang == LanguageEnum.TA:
                label = "🟡 மிதமானது / எச்சரிக்கை (Skizen மதிப்பீடு)"
            elif lang == LanguageEnum.HI:
                label = "🟡 MODERATE/CAUTION (Skizen-derived assessment)"
            else:
                label = "🟡 MODERATE/CAUTION (Skizen-derived assessment)"
        else:
            level = "LOW"
            if lang == LanguageEnum.TA:
                label = "🟢 சாதகமானது / குறைந்த ஆபத்து (Skizen மதிப்பீடு)"
            elif lang == LanguageEnum.HI:
                label = "🟢 अनुकूल / कम जोखिम (Skizen मूल्यांकन)"
            else:
                label = "🟢 LOW/FAVORABLE (Skizen-derived assessment)"

        return level, label

    @staticmethod
    def _generate_why_bullets(
        role: str,
        location_name: str,
        is_last_known: bool,
        reasoning: WeatherReasoningResult,
        weather: Optional[AIWeatherRecord],
        forecast: Optional[List[AIForecastItem]],
        risk_level: str,
        lang: LanguageEnum
    ) -> List[str]:
        """Generates dynamic 'Why did I get this?' bullet points derived from actual reasoning inputs."""
        bullets: List[str] = []
        is_ta = (lang == LanguageEnum.TA)
        is_hi = (lang == LanguageEnum.HI)

        # 1. Profile identification
        role_titles = {
            "fisherman": ("Fisherman", "மீனவர்", "मछुआरा"),
            "farmer": ("Farmer", "விவசாயி", "किसान"),
            "commuter": ("Commuter", "பயணி", "यात्री"),
            "student": ("Student", "மாணவர்", "छात्र"),
            "outdoor_worker": ("Outdoor Worker", "வெளிப்புற பணியாளர்", "आउटडोर कार्यकर्ता")
        }
        role_label = role_titles.get(role, ("User", "பயனர்", "उपयोगकर्ता"))
        role_name = role_label[1] if is_ta else (role_label[2] if is_hi else role_label[0])

        if is_ta:
            bullets.append(f"உங்கள் சுயவிவரம் {role_name} வகையைச் சார்ந்தது.")
        elif is_hi:
            bullets.append(f"आपकी प्रोफ़ाइल {role_name} के रूप में पंजीकृत है।")
        else:
            bullets.append(f"Your registered profile is {role_name}.")

        # 2. Location context
        loc_suffix = " (Last known location)" if is_last_known else ""
        if is_ta:
            loc_s = " (கடைசி அறியப்பட்ட இடம்)" if is_last_known else ""
            bullets.append(f"உங்கள் இருப்பிடம் {location_name}{loc_s} எல்லைக்குள் உள்ளது.")
        elif is_hi:
            loc_s = " (अंतिम ज्ञात स्थान)" if is_last_known else ""
            bullets.append(f"आपका स्थान {location_name}{loc_s} प्रभावित क्षेत्र में है।")
        else:
            bullets.append(f"Your location is {location_name}{loc_suffix}.")

        # 3. Active Official Warnings
        if reasoning.active_warnings:
            for w in reasoning.active_warnings[:2]:
                title = w.title or w.hazard_type or "Weather Warning"
                if is_ta:
                    bullets.append(f"அதிகாரப்பூர்வ எச்சரிக்கை பதிவாகியுள்ளது: {title}")
                elif is_hi:
                    bullets.append(f"आधिकारिक चेतावनी सक्रिय है: {title}")
                else:
                    bullets.append(f"Official meteorological alert active: {title}")

        # 4. Detected Hazards & Meteorological threshold excesses
        if reasoning.detected_hazards:
            for h in reasoning.detected_hazards[:2]:
                if is_ta:
                    bullets.append(f"வானிலை காரணி: {h.details}")
                elif is_hi:
                    bullets.append(f"मौसम कारक: {h.details}")
                else:
                    bullets.append(f"Hazard detected: {h.details}")

        # 5. Role-specific metric triggers
        if weather:
            # Fisherman wind trigger
            if role == "fisherman" and weather.wind_speed >= 25:
                if is_ta:
                    bullets.append(f"கடலோர காற்றின் வேகம் ({weather.wind_speed} km/h) எச்சரிக்கை எல்லையைத் தாண்டியுள்ளது.")
                elif is_hi:
                    bullets.append(f"हवा की गति ({weather.wind_speed} km/h) तटीय चेतावनी सीमा से अधिक है।")
                else:
                    bullets.append(f"Wind speed ({weather.wind_speed} km/h) exceeds coastal caution threshold (25 km/h).")

            # Commuter/Student rain trigger
            if role in ("commuter", "student") and weather.rain_probability >= 40:
                if is_ta:
                    bullets.append(f"மழை பெய்யும் வாய்ப்பு {int(weather.rain_probability)}% ஆக உள்ளது.")
                elif is_hi:
                    bullets.append(f"बारिश की संभावना {int(weather.rain_probability)}% है, जिससे आवागमन प्रभावित हो सकता है।")
                else:
                    bullets.append(f"Precipitation probability is {int(weather.rain_probability)}%, impacting transit.")

            # Farmer rain/humidity trigger
            if role == "farmer":
                if weather.rain_probability >= 50:
                    if is_ta:
                        bullets.append(f"மழை வாய்ப்பு ({int(weather.rain_probability)}%) வயல்வெளி வேலைகளை பாதிக்கலாம்.")
                    elif is_hi:
                        bullets.append(f"बारिश की संभावना ({int(weather.rain_probability)}%) कृषि कार्यों को प्रभावित कर सकती है।")
                    else:
                        bullets.append(f"High rain probability ({int(weather.rain_probability)}%) may affect field spraying or harvesting.")

            # Outdoor worker heat trigger
            if role == "outdoor_worker" and weather.temperature >= 35:
                if is_ta:
                    bullets.append(f"வெப்பநிலை {weather.temperature}°C ஆக இருப்பதால் வெப்ப அழுத்தம் ஏற்படலாம்.")
                elif is_hi:
                    bullets.append(f"तापमान {weather.temperature}°C है, जिससे दोपहर में लू का खतरा है।")
                else:
                    bullets.append(f"High ambient temperature ({weather.temperature}°C) indicates thermal stress.")

        # 6. Fallback if LOW risk
        if risk_level == "LOW" and len(bullets) <= 2:
            if is_ta:
                bullets.append("அதிகாரப்பூர்வ எச்சரிக்கைகள் ஏதுமில்லை; அனைத்து காரணிகளும் சாதகமான வரம்பிற்குள் உள்ளன.")
            elif is_hi:
                bullets.append("कोई आधिकारिक चेतावनी नहीं है; सभी मौसम कारक सामान्य और सुरक्षित सीमा में हैं।")
            else:
                bullets.append("No official warnings active; all key meteorological indicators within favorable ranges.")

        return bullets

    @staticmethod
    def _find_heavy_rain_window(forecast: Optional[List[AIForecastItem]]) -> Optional[str]:
        """Finds any window of heavy rain or high precipitation from the forecast items."""
        if not forecast:
            return None
        high_rain_items = [
            f for f in forecast
            if (f.rain_probability and f.rain_probability >= 50) or (getattr(f, "rainfall_amount_mm", 0.0) and getattr(f, "rainfall_amount_mm", 0.0) >= 5)
        ]
        if not high_rain_items:
            return None
        first_time = high_rain_items[0].time
        last_time = high_rain_items[-1].time
        if first_time and last_time and first_time != last_time:
            return f"{first_time[:5]}-{last_time[:5]}"
        elif first_time:
            return f"{first_time[:5]}"
        return None

    def _compose_sms_message(
        self,
        role: str,
        location_name: str,
        is_last_known: bool,
        risk_level: str,
        risk_status_label: str,
        weather: Optional[AIWeatherRecord],
        forecast: Optional[List[AIForecastItem]],
        reasoning: WeatherReasoningResult,
        advisory: DecisionAdvisory,
        lang: LanguageEnum,
        freshness_label: str,
        updated_time_str: str
    ) -> str:
        """Composes a concise, role-aware, non-directive SMS message strictly under 320 chars."""
        is_ta = (lang == LanguageEnum.TA)
        is_hi = (lang == LanguageEnum.HI)

        # 1. Location Header with Last Known flag if applicable
        if is_last_known:
            if is_ta:
                loc_header = f"📍 {location_name} (கடைசி இடம்)"
            elif is_hi:
                loc_header = f"📍 {location_name} (अंतिम स्थान)"
            else:
                loc_header = f"📍 {location_name} (Last known)"
        else:
            loc_header = f"📍 {location_name}"

        # 2. Risk Tag (Shortened for SMS)
        if risk_level == "HIGH":
            risk_badge = "🔴 HIGH (Skizen)" if not (is_ta or is_hi) else ("🔴 அதிக ஆபத்து (Skizen)" if is_ta else "🔴 उच्च जोखिम (Skizen)")
        elif risk_level == "MODERATE":
            risk_badge = "🟡 CAUTION (Skizen)" if not (is_ta or is_hi) else ("🟡 எச்சரிக்கை (Skizen)" if is_ta else "🟡 सावधानी (Skizen)")
        else:
            risk_badge = "🟢 LOW (Skizen)" if not (is_ta or is_hi) else ("🟢 சாதகமானது (Skizen)" if is_ta else "🟢 अनुकूल (Skizen)")

        # Extract verified meteorological metrics
        temp_val = f"{int(round(weather.temperature))}°C" if weather and weather.temperature is not None else None
        rain_prob = f"{int(weather.rain_probability)}%" if weather and weather.rain_probability is not None else None
        raw_precip = getattr(weather, "rainfall_amount_mm", 0.0) if weather else 0.0
        precip_mm = f"{round(raw_precip, 1)}mm" if raw_precip and raw_precip > 0 else None
        wind_speed = f"{int(weather.wind_speed)} km/h" if weather and weather.wind_speed is not None else None
        humidity = f"{int(weather.humidity)}%" if weather and weather.humidity is not None else None
        rain_window = self._find_heavy_rain_window(forecast)

        # Build role-specific body
        if role == "fisherman":
            if is_ta:
                # Tamil Fisherman
                wind_part = f"காற்று: {wind_speed}" if wind_speed else "வானிலை தகவல் பெறப்பட்டது"
                cond_part = f", {translate_condition(weather.weather_condition, lang)}" if weather and weather.weather_condition else ""
                alert_text = " IMD கடல் எச்சரிக்கை உள்ளது." if reasoning.active_warnings else ""
                advice = "ஆழ்கடல் செல்வதற்கு முன் அதிகாரப்பூர்வ IMD/INCOIS வழிகாட்டலைச் சரிபார்க்கவும்."
                msg = f"{loc_header} | {risk_badge}\n{wind_part}{cond_part}.{alert_text}\nபார்வை: {advice}\nபுதுப்பிக்கப்பட்டது: {updated_time_str}"
            elif is_hi:
                # Hindi Fisherman
                wind_part = f"हवा: {wind_speed}" if wind_speed else "मौसम विवरण"
                cond_part = f", {translate_condition(weather.weather_condition, lang)}" if weather and weather.weather_condition else ""
                alert_text = " IMD तटीय चेतावनी सक्रिय।" if reasoning.active_warnings else ""
                advice = "समुद्र में जाने से पूर्व आधिकारिक IMD/INCOIS बुलेटिन अवश्य देखें।"
                msg = f"{loc_header} | {risk_badge}\n{wind_part}{cond_part}.{alert_text}\nसलाह: {advice}\nअपडेट: {updated_time_str}"
            else:
                # English Fisherman
                wind_part = f"Wind: {wind_speed}" if wind_speed else "Observation verified"
                cond_part = f", {weather.weather_condition}" if weather and weather.weather_condition else ""
                alert_text = " IMD marine warning active." if reasoning.active_warnings else ""
                advice = "Refer to official IMD/INCOIS marine advisory before sailing."
                msg = f"{loc_header} | {risk_badge}\n{wind_part}{cond_part}.{alert_text}\nOutlook: {advice}\nUpdated: {updated_time_str}"

        elif role == "farmer":
            if is_ta:
                # Tamil Farmer
                rain_str = f"மழை: {rain_prob}" if rain_prob else ""
                rain_full = f"{rain_str} ({precip_mm})" if rain_str and precip_mm else rain_str
                temp_str = f"வெப்பம்: {temp_val}" if temp_val else ""
                figures = ", ".join(filter(None, [temp_str, rain_full, f"காற்று: {wind_speed}" if wind_speed else ""]))
                advice = "பயிர் பாதுகாப்பு மற்றும் தெளிப்பிற்கு மாவட்ட அக்ரோமெட் ஆலோசனையைப் பின்பற்றவும்."
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nபார்வை: {advice}\nபுதுப்பிக்கப்பட்டது: {updated_time_str}"
            elif is_hi:
                # Hindi Farmer
                rain_str = f"बारिश: {rain_prob}" if rain_prob else ""
                rain_full = f"{rain_str} ({precip_mm})" if rain_str and precip_mm else rain_str
                temp_str = f"तापमान: {temp_val}" if temp_val else ""
                figures = ", ".join(filter(None, [temp_str, rain_full, f"हवा: {wind_speed}" if wind_speed else ""]))
                advice = "फसल सुरक्षा हेतु जिला कृषि मौसम बुलेटिन देखें।"
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nसलाह: {advice}\nअपडेट: {updated_time_str}"
            else:
                # English Farmer
                rain_str = f"Rain: {rain_prob}" if rain_prob else ""
                rain_full = f"{rain_str} ({precip_mm})" if rain_str and precip_mm else rain_str
                temp_str = f"Temp: {temp_val}" if temp_val else ""
                figures = ", ".join(filter(None, [temp_str, rain_full, f"Wind: {wind_speed}" if wind_speed else ""]))
                advice = "Consult district Agromet advisory for crop spraying & harvesting."
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nOutlook: {advice}\nUpdated: {updated_time_str}"

        elif role == "commuter":
            if is_ta:
                # Tamil Commuter
                rain_str = f"மழை: {rain_prob}" if rain_prob else "வானிலை சீரானது"
                win_str = f" ({rain_window} நேரம்)" if rain_window else ""
                wind_part = f", காற்று: {wind_speed}" if wind_speed else ""
                advice = "பயண தாமதங்களை தவிர்க்க போக்குவரத்து காவல்துறை & IMD அறிவிப்புகளை கவனிக்கவும்."
                msg = f"{loc_header} | {risk_badge}\n{rain_str}{win_str}{wind_part}.\nபார்வை: {advice}\nபுதுப்பிக்கப்பட்டது: {updated_time_str}"
            elif is_hi:
                # Hindi Commuter
                rain_str = f"बारिश: {rain_prob}" if rain_prob else "मौसम सामान्य"
                win_str = f" ({rain_window} बजे)" if rain_window else ""
                wind_part = f", हवा: {wind_speed}" if wind_speed else ""
                advice = "यात्रा से पूर्व यातायात और IMD मौसम बुलेटिन देखें।"
                msg = f"{loc_header} | {risk_badge}\n{rain_str}{win_str}{wind_part}.\nसलाह: {advice}\nअपडेट: {updated_time_str}"
            else:
                # English Commuter
                rain_str = f"Rain: {rain_prob}" if rain_prob else "Normal conditions"
                win_str = f" (window: {rain_window})" if rain_window else ""
                wind_part = f", Wind: {wind_speed}" if wind_speed else ""
                advice = "Monitor traffic police updates & IMD nowcasts for transit delays."
                msg = f"{loc_header} | {risk_badge}\n{rain_str}{win_str}{wind_part}.\nOutlook: {advice}\nUpdated: {updated_time_str}"

        elif role == "student":
            if is_ta:
                # Tamil Student
                figures = ", ".join(filter(None, [f"வெப்பம்: {temp_val}" if temp_val else "", f"மழை: {rain_prob}" if rain_prob else ""]))
                advice = "பள்ளி/கல்லூரி பயணத்தின் போது வானிலை மாற்றங்களை கவனிக்கவும்."
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nபார்வை: {advice}\nபுதுப்பிக்கப்பட்டது: {updated_time_str}"
            elif is_hi:
                # Hindi Student
                figures = ", ".join(filter(None, [f"तापमान: {temp_val}" if temp_val else "", f"बारिश: {rain_prob}" if rain_prob else ""]))
                advice = "कॉलेज/स्कूल यात्रा के दौरान मौसम अपडेट का ध्यान रखें।"
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nसलाह: {advice}\nअपडेट: {updated_time_str}"
            else:
                # English Student
                figures = ", ".join(filter(None, [f"Temp: {temp_val}" if temp_val else "", f"Rain: {rain_prob}" if rain_prob else ""]))
                advice = "Check daily travel forecast and keep umbrella/water as appropriate."
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nOutlook: {advice}\nUpdated: {updated_time_str}"

        else:
            # Outdoor Worker / General
            if is_ta:
                figures = ", ".join(filter(None, [f"வெப்பம்: {temp_val}" if temp_val else "", f"மழை: {rain_prob}" if rain_prob else "", f"காற்று: {wind_speed}" if wind_speed else ""]))
                advice = "வெளிப்புற பணிகளின் போது நீரேற்றத்துடன் இருக்கவும் மற்றும் அதிகாரப்பூர்வ அறிவுறுத்தல்களைப் பின்பற்றவும்."
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nபார்வை: {advice}\nபுதுப்பிக்கப்பட்டது: {updated_time_str}"
            elif is_hi:
                figures = ", ".join(filter(None, [f"तापमान: {temp_val}" if temp_val else "", f"बारिश: {rain_prob}" if rain_prob else "", f"हवा: {wind_speed}" if wind_speed else ""]))
                advice = "खुले में कार्य करते समय पर्याप्त जल पिएं और स्थानीय सुरक्षा सलाह का पालन करें।"
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nसलाह: {advice}\nअपडेट: {updated_time_str}"
            else:
                figures = ", ".join(filter(None, [f"Temp: {temp_val}" if temp_val else "", f"Rain: {rain_prob}" if rain_prob else "", f"Wind: {wind_speed}" if wind_speed else ""]))
                advice = "Stay hydrated during outdoor shifts and heed local disaster management advisories."
                msg = f"{loc_header} | {risk_badge}\n{figures}.\nOutlook: {advice}\nUpdated: {updated_time_str}"

        # If data is stale, append a freshness warning
        if freshness_label == "stale":
            stale_warning = "\n(⚠️ Data aged >3h)" if not is_ta else "\n(⚠️ பழைய தரவு)"
            if len(msg) + len(stale_warning) <= 320:
                msg += stale_warning

        return msg.strip()

    @staticmethod
    def _format_valid_window(alert_obj_or_dict: Any, now_ist: datetime) -> str:
        """Extracts or formats a human-readable validity window string (e.g. 14:00-20:00 IST)."""
        start_str = None
        end_str = None

        if isinstance(alert_obj_or_dict, dict):
            if "valid_window" in alert_obj_or_dict:
                return str(alert_obj_or_dict["valid_window"])
            start_raw = alert_obj_or_dict.get("effective") or alert_obj_or_dict.get("valid_from") or alert_obj_or_dict.get("issued_at")
            end_raw = alert_obj_or_dict.get("expires") or alert_obj_or_dict.get("expires_at")

            if isinstance(start_raw, str):
                try:
                    if "T" in start_raw:
                        dt = datetime.fromisoformat(start_raw)
                        start_str = dt.strftime("%H:%M")
                    elif ":" in start_raw:
                        start_str = start_raw[:5]
                except Exception:
                    start_str = None
            elif isinstance(start_raw, datetime):
                start_str = start_raw.strftime("%H:%M")

            if isinstance(end_raw, str):
                try:
                    if "T" in end_raw:
                        dt = datetime.fromisoformat(end_raw)
                        end_str = dt.strftime("%H:%M")
                    elif ":" in end_raw:
                        end_str = end_raw[:5]
                except Exception:
                    end_str = None
            elif isinstance(end_raw, datetime):
                end_str = end_raw.strftime("%H:%M")

        elif alert_obj_or_dict is not None:
            issued = getattr(alert_obj_or_dict, "valid_from", None) or getattr(alert_obj_or_dict, "issued_at", None)
            expires = getattr(alert_obj_or_dict, "expires_at", None)
            if issued and isinstance(issued, datetime):
                start_str = issued.strftime("%H:%M")
            if expires and isinstance(expires, datetime):
                end_str = expires.strftime("%H:%M")

        if start_str and end_str:
            return f"{start_str}-{end_str} IST"
        elif end_str:
            return f"until {end_str} IST"
        else:
            return f"{now_ist.strftime('%H:%M')}-{(now_ist + timedelta(hours=6)).strftime('%H:%M')} IST"

    def _compose_proactive_sms_message(
        self,
        role: str,
        location_name: str,
        is_last_known: bool,
        risk_level: str,
        trigger_title: str,
        valid_window_str: str,
        lang: LanguageEnum,
        escalated: bool = False
    ) -> str:
        """Composes an urgent proactive severe weather alert strictly under 320 chars."""
        is_ta = (lang == LanguageEnum.TA)
        is_hi = (lang == LanguageEnum.HI)

        # 1. Header
        if is_ta:
            header = "🚨 SKIZEN வானிலை எச்சரிக்கை" + (" [தீவிரமடைந்தது]" if escalated else "")
            loc_label = f"📍 {location_name}" + (" (கடைசி இடம்)" if is_last_known else "")
            window_line = f"{loc_label} | காலஅளவு: {valid_window_str}"
            reason_line = f"காரணம்: {trigger_title}"
        elif is_hi:
            header = "🚨 SKIZEN मौसम चेतावनी" + (" [तीव्रता बढ़ी]" if escalated else "")
            loc_label = f"📍 {location_name}" + (" (अंतिम स्थान)" if is_last_known else "")
            window_line = f"{loc_label} | वैधता: {valid_window_str}"
            reason_line = f"कारण: {trigger_title}"
        else:
            header = "🚨 SKIZEN WEATHER ALERT" + (" [ESCALATED]" if escalated else "")
            loc_label = f"📍 {location_name}" + (" (Last known)" if is_last_known else "")
            window_line = f"{loc_label} | Valid: {valid_window_str}"
            reason_line = f"Reason: {trigger_title}"

        # 2. Role-specific Outlook
        if role == "fisherman":
            if is_ta:
                outlook_line = "பார்வை: கடுமையான காற்று/அலைகள் எதிர்பார்க்கப்படுகிறது. கடலுக்கு செல்வதை தவிர்க்கவும்; IMD அறிக்கையை கவனிக்கவும்."
            elif is_hi:
                outlook_line = "सलाह: तेज हवाएं और ऊंची लहरें संभावित। समुद्र में जाने से बचें; IMD तटीय बुलेटिन देखें।"
            else:
                outlook_line = "Outlook: Heavy squall & rough seas expected. Avoid venturing into sea; heed IMD coastal bulletins."
        elif role == "farmer":
            if is_ta:
                outlook_line = "பார்வை: பலத்த காற்று & இடி மின்னல். அறுவடை செய்த பயிர்களை பாதுகாக்கவும்; தெளிப்பை நிறுத்தவும்."
            elif is_hi:
                outlook_line = "सलाह: तेज हवाएं व आंधी-तूफान की आशंका। कटी फसल सुरक्षित करें और कीटनाशक छिड़काव रोकें।"
            else:
                outlook_line = "Outlook: Thunderstorms & gusty winds. Secure harvested produce and pause open spraying."
        elif role == "commuter":
            if is_ta:
                outlook_line = "பார்வை: தீவிர மழை & நீர் தேக்கம் ஏற்படலாம். கூடுதல் பயண நேரத்தை ஒதுக்கவும்; போக்குவரத்து அறிவிப்புகளை கவனிக்கவும்."
            elif is_hi:
                outlook_line = "सलाह: तेज बारिश व जलभराव की संभावना। यात्रा में अतिरिक्त समय रखें; ट्रैफिक पुलिस अपडेट देखें।"
            else:
                outlook_line = "Outlook: Intense rain & waterlogging likely. Allow extra travel buffer; monitor traffic nowcasts."
        elif role == "student":
            if is_ta:
                outlook_line = "பார்வை: தீவிர வானிலை சூழல். உச்ச நேரத்தில் பயணத்தை தவிர்க்கவும்; பள்ளி/கல்லூரி அறிவிப்புகளை பின்பற்றவும்."
            elif is_hi:
                outlook_line = "सलाह: प्रतिकूल गंभीर मौसम। चरम समय पर बाहर न निकलें; स्कूल/कॉलेज दिशानिर्देश देखें।"
            else:
                outlook_line = "Outlook: Severe storm conditions. Avoid transit during peak intensity; follow local school advisories."
        else:
            # Outdoor worker / General
            if is_ta:
                outlook_line = "பார்வை: அபாயகரமான வானிலை. பாதுகாப்பான தங்குமிடம் தேடவும்; வெளிப்புற பணிகளை ஒத்திவைக்கவும்."
            elif is_hi:
                outlook_line = "सलाह: खतरनाक मौसम स्थिति। सुरक्षित स्थान पर रहें और उच्च जोखिम वाले बाहरी काम टालें।"
            else:
                outlook_line = "Outlook: Hazardous severe weather. Seek safe shelter and suspend high-exposure outdoor tasks."

        message = f"{header}\n{window_line}\n{reason_line}\n{outlook_line}"

        if len(message) > 320:
            logger.warning("Proactive alert exceeded 320 chars (%d), truncating safely", len(message))
            message = message[:317] + "..."

        return message.strip()

    async def generate_personalized_briefing(
        self,
        user_id: Optional[str] = None,
        db_session: Optional[Session] = None,
        override_role: Optional[str] = None,
        override_location: Optional[str] = None,
        override_latitude: Optional[float] = None,
        override_longitude: Optional[float] = None,
        override_language: Optional[str] = None,
        override_phone: Optional[str] = None,
        is_last_known_override: Optional[bool] = None
    ) -> PersonalizedBriefingResponse:
        """Main Phase 1 backend function to generate a personalized weather briefing.
        
        Fetches user profile, resolves latest permitted location, fetches verified live weather,
        runs WeatherReasoner and DecisionEngine, derives Skizen risk, dynamic why-bullets,
        and constructs the SMS text (<320 chars).
        """
        now_ist = datetime.now(IST)
        updated_time_str = now_ist.strftime("%H:%M IST")

        # 1. Profile Resolution
        user: Optional[User] = None
        user_pref: Optional[UserPreference] = None
        if user_id and db_session:
            user = db_session.query(User).filter(User.id == user_id).first()
            if user:
                user_pref = user.preferences

        # Extract user profile attributes or apply overrides/defaults
        resolved_phone = override_phone or (user.phone_number if user else "") or (user.mobile_number if user else "")
        resolved_role_raw = override_role or (user_pref.persona if user_pref and user_pref.persona else (user.persona if user else "student"))
        resolved_role = self._normalize_role(resolved_role_raw)
        
        resolved_lang_raw = override_language or (user.language if user else (user_pref.preferred_units if user_pref else "en"))
        resolved_lang = self._normalize_language(resolved_lang_raw)

        notification_enabled = user_pref.notification_enabled if user_pref else True

        # Resolve location
        is_last_known = False
        target_location_name = "Chennai"
        target_lat: Optional[float] = override_latitude
        target_lon: Optional[float] = override_longitude

        if override_location:
            target_location_name = override_location
            if is_last_known_override is not None:
                is_last_known = is_last_known_override
        elif override_latitude is not None and override_longitude is not None:
            target_location_name = override_location or f"Coords({target_lat:.2f},{target_lon:.2f})"
            if is_last_known_override is not None:
                is_last_known = is_last_known_override
        elif user_pref and user_pref.last_known_location:
            target_location_name = user_pref.last_known_location
            target_lat = user_pref.last_latitude
            target_lon = user_pref.last_longitude
            is_last_known = True
        elif user_pref and user_pref.last_latitude is not None and user_pref.last_longitude is not None:
            target_lat = user_pref.last_latitude
            target_lon = user_pref.last_longitude
            target_location_name = user_pref.last_known_location or "Registered Location"
            is_last_known = True
        else:
            target_location_name = "Chennai"
            is_last_known = False

        if is_last_known_override is not None:
            is_last_known = is_last_known_override

        # 2. Meteorological Data Acquisition via WeatherManager
        ai_obs, ai_forecasts, ai_alerts = await self.weather_manager.get_ai_weather_input(
            lat=target_lat,
            lon=target_lon,
            location_name=target_location_name
        )

        # 3. Weather Reasoning Engine
        reasoning_result = WeatherReasoner.evaluate(
            primary_weather=ai_obs,
            forecast=ai_forecasts,
            active_alerts=ai_alerts
        )

        # 4. Decision Advisory Engine
        persona_enum_map = {
            "fisherman": PersonaEnum.FISHERMAN,
            "farmer": PersonaEnum.FARMER,
            "commuter": PersonaEnum.COMMUTER,
            "student": PersonaEnum.STUDENT,
            "outdoor_worker": PersonaEnum.GENERAL
        }
        target_persona_enum = persona_enum_map.get(resolved_role, PersonaEnum.STUDENT)

        decision_advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning_result,
            persona=target_persona_enum,
            target_language=resolved_lang,
            weather=ai_obs,
            forecast=ai_forecasts
        )

        # 5. Skizen-Specific Risk Assessment Derivation
        risk_level, risk_status_label = self._derive_skizen_risk_status(
            reasoning=reasoning_result,
            advisory=decision_advisory,
            lang=resolved_lang
        )

        # 6. Freshness Status
        freshness_label = reasoning_result.freshness.value if reasoning_result.freshness else "fresh"

        # 7. Dynamic "Why Did I Get This?" Bullets
        why_bullets = self._generate_why_bullets(
            role=resolved_role,
            location_name=target_location_name,
            is_last_known=is_last_known,
            reasoning=reasoning_result,
            weather=ai_obs,
            forecast=ai_forecasts,
            risk_level=risk_level,
            lang=resolved_lang
        )

        # 8. Role-Aware SMS Message Composition (< 320 chars)
        composed_message = self._compose_sms_message(
            role=resolved_role,
            location_name=target_location_name,
            is_last_known=is_last_known,
            risk_level=risk_level,
            risk_status_label=risk_status_label,
            weather=ai_obs,
            forecast=ai_forecasts,
            reasoning=reasoning_result,
            advisory=decision_advisory,
            lang=resolved_lang,
            freshness_label=freshness_label,
            updated_time_str=updated_time_str
        )

        # Safety length guard: Ensure strict adherence to <= 320 characters
        if len(composed_message) > 320:
            logger.warning("Composed SMS message exceeded 320 chars (%d), truncating safely", len(composed_message))
            composed_message = composed_message[:317] + "..."

        raw_weather_summary = {
            "temperature": ai_obs.temperature if ai_obs else None,
            "rain_probability": ai_obs.rain_probability if ai_obs else None,
            "wind_speed": ai_obs.wind_speed if ai_obs else None,
            "humidity": ai_obs.humidity if ai_obs else None,
            "condition": ai_obs.weather_condition if ai_obs else None,
            "warnings_count": len(reasoning_result.active_warnings),
            "hazards_count": len(reasoning_result.detected_hazards)
        }

        return PersonalizedBriefingResponse(
            user_id=user.id if user else user_id,
            mobile_number=resolved_phone,
            role=resolved_role,
            location_name=target_location_name,
            is_last_known_location=is_last_known,
            language=resolved_lang.value,
            notification_enabled=notification_enabled,
            risk_level=risk_level,
            risk_status_label=risk_status_label,
            message_text=composed_message,
            character_count=len(composed_message),
            reasoning_bullets=why_bullets,
            data_freshness=freshness_label,
            timestamp=updated_time_str,
            raw_weather=raw_weather_summary
        )

    async def generate_proactive_alert(
        self,
        user_id: Optional[str] = None,
        db_session: Optional[Session] = None,
        override_role: Optional[str] = None,
        override_location: Optional[str] = None,
        override_latitude: Optional[float] = None,
        override_longitude: Optional[float] = None,
        override_language: Optional[str] = None,
        override_phone: Optional[str] = None,
        is_last_known_override: Optional[bool] = None,
        active_alert_override: Optional[Union[Dict[str, Any], AIOfficialAlert]] = None,
        simulated_weather_override: Optional[AIWeatherRecord] = None,
        simulated_forecast_override: Optional[List[AIForecastItem]] = None,
        escalated: bool = False
    ) -> PersonalizedBriefingResponse:
        """Generates an urgent proactive severe weather alert (<320 chars) for unexpected/developing events.

        Triggered between scheduled daily briefings when an official warning becomes active or hazards exceed thresholds.
        """
        now_utc = datetime.now(timezone.utc)
        now_ist = datetime.now(IST)
        updated_time_str = now_ist.strftime("%H:%M IST")

        # 1. Profile Resolution
        user: Optional[User] = None
        user_pref: Optional[UserPreference] = None
        if user_id and db_session:
            user = db_session.query(User).filter(User.id == user_id).first()
            if user:
                user_pref = user.preferences

        resolved_phone = override_phone or (user.phone_number if user else "") or (user.mobile_number if user else "")
        resolved_role_raw = override_role or (user_pref.persona if user_pref and user_pref.persona else (user.persona if user else "student"))
        resolved_role = self._normalize_role(resolved_role_raw)

        resolved_lang_raw = override_language or (user.language if user else (user_pref.preferred_units if user_pref else "en"))
        resolved_lang = self._normalize_language(resolved_lang_raw)

        notification_enabled = user_pref.notification_enabled if user_pref else True

        # Resolve location
        is_last_known = False
        target_location_name = "Chennai"
        target_lat: Optional[float] = override_latitude
        target_lon: Optional[float] = override_longitude

        if override_location:
            target_location_name = override_location
            if is_last_known_override is not None:
                is_last_known = is_last_known_override
        elif override_latitude is not None and override_longitude is not None:
            target_location_name = override_location or f"Coords({target_lat:.2f},{target_lon:.2f})"
            if is_last_known_override is not None:
                is_last_known = is_last_known_override
        elif user_pref and user_pref.last_known_location:
            target_location_name = user_pref.last_known_location
            target_lat = user_pref.last_latitude
            target_lon = user_pref.last_longitude
            is_last_known = True
        elif user_pref and user_pref.last_latitude is not None and user_pref.last_longitude is not None:
            target_lat = user_pref.last_latitude
            target_lon = user_pref.last_longitude
            target_location_name = user_pref.last_known_location or "Registered Location"
            is_last_known = True
        else:
            target_location_name = "Chennai"
            is_last_known = False

        if is_last_known_override is not None:
            is_last_known = is_last_known_override

        # 2. Meteorological Data Acquisition
        if simulated_weather_override is not None:
            ai_obs = simulated_weather_override
            ai_forecasts = simulated_forecast_override or []
            ai_alerts: List[AIOfficialAlert] = []
        else:
            ai_obs, ai_forecasts, ai_alerts = await self.weather_manager.get_ai_weather_input(
                lat=target_lat,
                lon=target_lon,
                location_name=target_location_name
            )

        # Merge active alert override if provided
        target_alert_obj: Optional[AIOfficialAlert] = None
        if active_alert_override:
            if isinstance(active_alert_override, dict):
                sev_str = str(active_alert_override.get("severity", "high")).lower()
                sev_enum = RiskLevelEnum.HIGH
                if sev_str in ("medium", "moderate", "yellow"):
                    sev_enum = RiskLevelEnum.MEDIUM
                elif sev_str in ("extreme", "red"):
                    sev_enum = RiskLevelEnum.EXTREME
                elif sev_str in ("low", "green"):
                    sev_enum = RiskLevelEnum.LOW

                target_alert_obj = AIOfficialAlert(
                    id=active_alert_override.get("id") or "IMD-WARN-ACTIVE",
                    type=active_alert_override.get("hazard_type") or active_alert_override.get("type", "severe_weather"),
                    severity=sev_enum,
                    title=active_alert_override.get("title", "Severe Weather Warning"),
                    description=active_alert_override.get("description", "Severe weather conditions developing."),
                    instructions=active_alert_override.get("instructions"),
                    source=active_alert_override.get("source", "IMD"),
                    issued_at=now_utc,
                    expires_at=now_utc + timedelta(hours=6),
                    status="ACTIVE",
                    affected_locations=[target_location_name]
                )
            else:
                target_alert_obj = active_alert_override

            ai_alerts = [target_alert_obj] + [a for a in ai_alerts if getattr(a, "id", None) != getattr(target_alert_obj, "id", None)]

        # 3. Weather Reasoning Engine
        reasoning_result = WeatherReasoner.evaluate(
            primary_weather=ai_obs,
            forecast=ai_forecasts,
            active_alerts=ai_alerts
        )

        # 4. Trigger & Validity Window Extraction
        valid_window_str = self._format_valid_window(active_alert_override or (ai_alerts[0] if ai_alerts else None), now_ist)

        trigger_title = "Severe Meteorological Hazard"
        if ai_alerts:
            first_alert = ai_alerts[0]
            alert_sev = first_alert.severity.value.upper() if hasattr(first_alert.severity, "value") else str(first_alert.severity).upper()
            trigger_title = f"{first_alert.title} ({alert_sev})"
        elif reasoning_result.detected_hazards:
            first_h = reasoning_result.detected_hazards[0]
            trigger_title = first_h.details

        # 5. Skizen Risk Level Derivation
        risk_level = "HIGH"
        if reasoning_result.overall_risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or (ai_alerts and any(a.severity in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) for a in ai_alerts)):
            risk_level = "HIGH"
        elif reasoning_result.overall_risk == RiskLevelEnum.MEDIUM or ai_alerts:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        if resolved_lang == LanguageEnum.TA:
            risk_status_label = "🔴 அதிக ஆபத்து (Skizen மதிப்பீடு)" if risk_level == "HIGH" else "🟡 எச்சரிக்கை (Skizen மதிப்பீடு)"
        elif resolved_lang == LanguageEnum.HI:
            risk_status_label = "🔴 उच्च जोखिम (Skizen मूल्यांकन)" if risk_level == "HIGH" else "🟡 सावधानी (Skizen मूल्यांकन)"
        else:
            risk_status_label = "🔴 HIGH RISK (Skizen-derived assessment)" if risk_level == "HIGH" else "🟡 MODERATE/CAUTION (Skizen-derived assessment)"

        # 6. Compose Proactive SMS Message (<320 chars)
        composed_message = self._compose_proactive_sms_message(
            role=resolved_role,
            location_name=target_location_name,
            is_last_known=is_last_known,
            risk_level=risk_level,
            trigger_title=trigger_title,
            valid_window_str=valid_window_str,
            lang=resolved_lang,
            escalated=escalated
        )

        # 7. Dynamic "Why Did I Get This?" Bullets
        why_bullets: List[str] = []
        is_ta = (resolved_lang == LanguageEnum.TA)
        is_hi = (resolved_lang == LanguageEnum.HI)

        # Profile context
        role_en = resolved_role.capitalize()
        if is_ta:
            why_bullets.append(f"உங்கள் சுயவிவரம் {role_en} வகையாக பதிவு செய்யப்பட்டுள்ளது.")
            why_bullets.append(f"இருப்பிடம்: {target_location_name}{' (கடைசி இடம்)' if is_last_known else ''}.")
            why_bullets.append(f"அவசர தூண்டுதல்: {trigger_title} கண்டறியப்பட்டுள்ளது.")
            if escalated:
                why_bullets.append("முந்தைய எச்சரிக்கையுடன் ஒப்பிடும்போது தீவிரம் அதிகரித்துள்ளது.")
        elif is_hi:
            why_bullets.append(f"आपकी प्रोफ़ाइल {role_en} के रूप में पंजीकृत है।")
            why_bullets.append(f"स्थान: {target_location_name}{' (अंतिम स्थान)' if is_last_known else ''}।")
            why_bullets.append(f"आपातकालीन अलर्ट: {trigger_title} सक्रिय हुआ है।")
            if escalated:
                why_bullets.append("पिछली चेतावनी की तुलना में मौसम की गंभीरता बढ़ गई है।")
        else:
            why_bullets.append(f"Your registered profile is {role_en}.")
            why_bullets.append(f"Your location is {target_location_name}{' (Last known location)' if is_last_known else ''}.")
            why_bullets.append(f"Proactive trigger: {trigger_title} detected.")
            if escalated:
                why_bullets.append("Alert severity escalated from previous notification level.")

        raw_weather_summary = {
            "temperature": ai_obs.temperature if ai_obs else None,
            "rain_probability": ai_obs.rain_probability if ai_obs else None,
            "wind_speed": ai_obs.wind_speed if ai_obs else None,
            "condition": ai_obs.weather_condition if ai_obs else None,
            "warnings_count": len(reasoning_result.active_warnings),
            "hazards_count": len(reasoning_result.detected_hazards),
            "is_proactive": True,
            "escalated": escalated
        }

        return PersonalizedBriefingResponse(
            user_id=user.id if user else user_id,
            mobile_number=resolved_phone,
            role=resolved_role,
            location_name=target_location_name,
            is_last_known_location=is_last_known,
            language=resolved_lang.value,
            notification_enabled=notification_enabled,
            risk_level=risk_level,
            risk_status_label=risk_status_label,
            message_text=composed_message,
            character_count=len(composed_message),
            reasoning_bullets=why_bullets,
            data_freshness="fresh",
            timestamp=updated_time_str,
            raw_weather=raw_weather_summary
        )
