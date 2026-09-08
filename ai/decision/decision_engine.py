"""Persona-Aware Decision & Advisory Engine for WeatherGPT.

Converts meteorological findings into actionable, conservative,
persona-tailored recommendations per docs/09_AI_Design.md and docs/10_Demo_Scenarious.md.
"""

from typing import List
from ai.models import (
    DecisionAdvisory,
    LanguageEnum,
    PersonaEnum,
    RiskLevelEnum,
    WeatherReasoningResult,
)


class DecisionEngine:
    """Generates grounded, persona-tailored advisories from weather reasoning."""

    @staticmethod
    def generate_advisory(
        reasoning: WeatherReasoningResult,
        persona: PersonaEnum = PersonaEnum.GENERAL,
        target_language: LanguageEnum = LanguageEnum.EN
    ) -> DecisionAdvisory:
        """Generates structured advice tailored to user persona and risk."""
        risk = reasoning.overall_risk
        active_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_present = active_warning is not None

        precautions: List[str] = []
        headline = ""
        advisory_text = ""

        # Language selection: English vs Tamil/Tanglish
        is_tamil = target_language in (LanguageEnum.TA, LanguageEnum.TANGLISH)

        # ---------------- STUDENT PERSONA ----------------
        if persona == PersonaEnum.STUDENT:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
                if is_tamil:
                    headline = "கனமழை எச்சரிக்கை — பள்ளி/கல்லூரி பயணத்தில் அதிக கவனம் தேவை"
                    advisory_text = (
                        "கனமழை அல்லது தீவிர வானிலை எச்சரிக்கை நிலவுகிறது. "
                        "தேவையற்ற வெளிப்பயணங்களைத் தவிர்க்கவும். "
                        "கல்லூரி/பள்ளி விடுமுறை மற்றும் வகுப்புகள் குறித்த அதிகாரப்பூர்வ நிர்வாக அறிவிப்புகளைச் சரிபார்க்கவும்."
                    )
                    precautions = [
                        "மழைக்கோட்டு அல்லது குடை எடுத்துச் செல்லவும்",
                        "நீர் தேங்கிய சாலைகள் மற்றும் தாழ்வான பகுதிகளைத் தவிர்க்கவும்",
                        "அதிகாரப்பூர்வ கல்வி நிறுவன அறிவிப்புகளைத் தொடர்ந்து கண்காணிக்கவும்"
                    ]
                else:
                    headline = "High Weather Risk — Commute Precaution Advised"
                    advisory_text = (
                        "Significant precipitation or hazardous conditions detected during your travel window. "
                        "Prioritize personal safety and verify institutional notices regarding class schedules."
                    )
                    precautions = [
                        "Carry rain protection (waterproof bag, umbrella, raincoat)",
                        "Avoid waterlogged commuter corridors and open storm drains",
                        "Check official institutional notifications (WeatherGPT does not declare holidays)"
                    ]
            elif risk == RiskLevelEnum.MEDIUM:
                if is_tamil:
                    headline = "மிதமான மழை வாய்ப்பு — பயணத்திற்கு தயாராக இருங்கள்"
                    advisory_text = "மழை பெய்ய வாய்ப்புள்ளது. பொதுப்போக்குவரத்து காலதாமதத்திற்கு திட்டமிடுங்கள்."
                    precautions = ["குடை எடுத்துச் செல்லவும்", "பயணத்தை முன்கூட்டியே தொடங்கவும்"]
                else:
                    headline = "Moderate Rain Expected — Prepare for Commute"
                    advisory_text = "Precipitation is likely. Anticipate minor transit delays during morning/evening commute."
                    precautions = ["Keep an umbrella handy", "Allow extra commute time"]
            else:
                if is_tamil:
                    headline = "சாதகமான வானிலை"
                    advisory_text = "வானிலை பொதுவாக சாதகமாக உள்ளது. இயல்பான பயணத்தை மேற்கொள்ளலாம்."
                    precautions = ["வழக்கமான பயண ஏற்பாடுகள் போதுமானது"]
                else:
                    headline = "Normal Weather Conditions"
                    advisory_text = "Weather conditions are stable for travel and outdoor campus activities."
                    precautions = ["Standard commuter routine applies"]

        # ---------------- FISHERMAN PERSONA ----------------
        elif persona == PersonaEnum.FISHERMAN:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or warning_present:
                if is_tamil:
                    headline = "கடல் எச்சரிக்கை — கடலுக்கு செல்ல வேண்டாம்"
                    advisory_text = (
                        "பலத்த காற்று / புயல் சின்னம் காரணமாக கடல் கொந்தளிப்பாக இருக்கும். "
                        "மீனவர்கள் கடலுக்குள் செல்ல வேண்டாம் என அறிவுறுத்தப்படுகிறார்கள்."
                    )
                    precautions = [
                        "ஆழ்கடல் மீன்பிடிப்பைத் தவிர்க்கவும்",
                        "படகு மற்றும் வலைகளைப் பாதுகாப்பான மேடான இடங்களில் கட்டவும்",
                        "மீன்வளத்துறை மற்றும் IMD வானிலை எச்சரிக்கைகளைக் கேட்கவும்"
                    ]
                else:
                    headline = "Marine Weather Alert — Avoid Venturing into Sea"
                    advisory_text = (
                        "Squally weather with hazardous wind gusts and rough seas expected. "
                        "Fishermen are strictly advised not to venture into deep sea or coastal waters."
                    )
                    precautions = [
                        "Do not venture into open sea",
                        "Secure all small craft and fishing equipment at designated safe moorings",
                        "Monitor coastal radio broadcasts for IMD marine bulletins"
                    ]
            else:
                if is_tamil:
                    headline = "சாதகமான கடல் நிலை"
                    advisory_text = "தற்போது கடல் கொந்தளிப்புக்கான எச்சரிக்கைகள் இல்லை. எச்சரிக்கையுடன் தொழிலை மேற்கொள்ளவும்."
                    precautions = ["வானொலி தொடர்பு சாதனங்களை தயாராக வைத்திருக்கவும்"]
                else:
                    headline = "Favorable Marine Conditions"
                    advisory_text = "Wind speed and sea state are currently within normal operational limits."
                    precautions = ["Maintain standard onboard communication and life jacket safety"]

        # ---------------- FARMER PERSONA ----------------
        elif persona == PersonaEnum.FARMER:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
                if is_tamil:
                    headline = "கனமழை எச்சரிக்கை — பயிர் பாதுகாப்பு ஆலோசனை"
                    advisory_text = "கனமழை எதிர்பார்க்கப்படுவதால் நீர் தேங்குவதைத் தடுக்க வடிகால் வசதிகளைச் சரிசெய்யவும்."
                    precautions = [
                        "வயல்களில் பாசனம் செய்வதைத் தவிர்க்கவும்",
                        "உரங்கள் அல்லது பூச்சிக்கொல்லி தெளிப்பதை ஒத்திவைக்கவும்",
                        "அறுவடை செய்த பயிர்களைப் பாதுகாப்பான இடங்களில் சேமிக்கவும்"
                    ]
                else:
                    headline = "Agricultural Advisory — Heavy Precipitation Ahead"
                    advisory_text = "Heavy rainfall can lead to field inundation and nutrient runoff."
                    precautions = [
                        "Suspend irrigation immediately",
                        "Postpone fertilizer and pesticide applications to prevent runoff",
                        "Clear field drainage channels and secure harvested produce under cover"
                    ]
            else:
                if is_tamil:
                    headline = "இயல்பான விவசாய வானிலை"
                    advisory_text = "விவசாய பணிகளுக்கு வானிலை ஏற்றதாக உள்ளது."
                    precautions = ["வழக்கமான பாசன அட்டவணையைப் பின்பற்றவும்"]
                else:
                    headline = "Standard Agricultural Conditions"
                    advisory_text = "Favorable conditions for routine cultivation and field management."
                    precautions = ["Proceed with standard irrigation schedule"]

        # ---------------- GENERAL / TRAVELLER / DISASTER ----------------
        else:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
                headline = "Severe Weather Alert Active" if not is_tamil else "தீவிர வானிலை எச்சரிக்கை"
                advisory_text = (
                    "Adverse weather conditions detected. Avoid non-essential travel and follow local authority advisories."
                    if not is_tamil else
                    "மோசமான வானிலை நிலவுகிறது. அவசியமற்ற பயணங்களைத் தவிர்த்து பாதுகாப்புடன் இருக்கவும்."
                )
                precautions = [
                    "Stay indoors during peak storm activity",
                    "Keep emergency lights and phones charged",
                    "Follow official government guidelines"
                ]
            else:
                headline = "Pleasant / Moderate Weather" if not is_tamil else "மிதமான வானிலை"
                advisory_text = "No severe weather hazards detected for your area." if not is_tamil else "தீவிர வானிலை ஆபத்துகள் ஏதுமில்லை."
                precautions = ["Standard outdoor precautions"]

        timestamp_str = f"Data updated {reasoning.data_age_minutes}m ago ({reasoning.freshness.value})"
        source_str = f"Source: {', '.join(reasoning.sources_used)}"

        return DecisionAdvisory(
            persona=persona,
            risk_level=risk,
            headline=headline,
            advisory_text=advisory_text,
            key_precautions=precautions,
            official_warning_present=warning_present,
            official_warning_title=active_warning.title if active_warning else None,
            source_attribution=source_str,
            timestamp_info=timestamp_str
        )
