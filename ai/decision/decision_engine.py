"""Persona-Aware Decision & Advisory Engine for WeatherGPT.

Converts verified meteorological findings (telemetry, reasoner consistency,
calibrated hazards, and official IMD warnings) into deterministic, actionable,
persona-specific recommendations in English, Tamil, and Hindi per docs/09_AI_Design.md
and docs/10_Demo_Scenarious.md.

Strict Division of Responsibility:
- The Advisory Engine decides WHAT KIND OF ADVICE IS APPROPRIATE (priority, timing,
  risk summary, action items, evidence).
- The LLM decides HOW TO EXPRESS THAT ADVICE in conversational prose.
"""

from typing import Any, Dict, List, Optional
from ai.models import (
    AdvisoryPriorityEnum,
    AdvisoryTypeEnum,
    DecisionAdvisory,
    ForecastItem,
    HazardDetection,
    LanguageEnum,
    NLUResult,
    PersonaEnum,
    RiskLevelEnum,
    TimeContextEnum,
    WeatherReasoningResult,
    WeatherRecord,
)


class DecisionEngine:
    """Generates grounded, persona-tailored advisories from weather reasoning."""

    @staticmethod
    def _normalize_persona(persona: Any) -> PersonaEnum:
        """Normalizes persona input safely to supported PersonaEnum members."""
        if isinstance(persona, str):
            p_str = persona.lower().strip()
            if p_str in ("commuter",):
                return PersonaEnum.COMMUTER
            if p_str in ("farmer", "agriculture"):
                return PersonaEnum.FARMER
            if p_str in ("fisherman", "fisher", "marine"):
                return PersonaEnum.FISHERMAN
            if p_str in ("student",):
                return PersonaEnum.STUDENT
            if p_str in ("traveller", "traveler", "tourist"):
                return PersonaEnum.TRAVELLER
            if p_str in ("disaster_response", "disaster", "emergency"):
                return PersonaEnum.DISASTER_RESPONSE
            return PersonaEnum.GENERAL
        elif isinstance(persona, PersonaEnum):
            if persona in (PersonaEnum.TRAVELER, PersonaEnum.TRAVELLER):
                return PersonaEnum.TRAVELLER
            if persona in (PersonaEnum.GENERAL_USER, PersonaEnum.GENERAL):
                return PersonaEnum.GENERAL
            return persona
        return PersonaEnum.GENERAL

    @staticmethod
    def _get_hazard_temporal_scope(h: Any) -> str:
        """Extracts temporal scope safely from HazardDetection objects."""
        if hasattr(h, "current_or_forecast") and h.current_or_forecast:
            return h.current_or_forecast
        if hasattr(h, "temporal_scope") and getattr(h, "temporal_scope"):
            return getattr(h, "temporal_scope")
        return "current"

    @classmethod
    def _determine_time_context(
        cls,
        nlu: Optional[NLUResult],
        hazards: List[HazardDetection]
    ) -> TimeContextEnum:
        """Determines the temporal scope of the advisory (NOW, NEXT_FEW_HOURS, TODAY, TOMORROW, LATER)."""
        if nlu and nlu.entities:
            d = (nlu.entities.date or "").lower()
            t = (nlu.entities.time or "").lower()
            if any(term in d for term in ("tomorrow", "naalai", "kal", "day after")):
                return TimeContextEnum.TOMORROW
            if any(term in t for term in ("tonight", "evening", "afternoon", "in 2 hours", "next few hours")):
                return TimeContextEnum.NEXT_FEW_HOURS
            if any(term in t for term in ("now", "currently", "ippo", "present", "ab")):
                return TimeContextEnum.NOW
            if any(term in d for term in ("next week", "later")):
                return TimeContextEnum.LATER

        # Fallback to hazard temporal scopes
        has_current = any(cls._get_hazard_temporal_scope(h) in ("current", "both") for h in hazards)
        has_forecast = any(cls._get_hazard_temporal_scope(h) == "forecast" for h in hazards)

        if has_current:
            return TimeContextEnum.NOW
        if has_forecast:
            return TimeContextEnum.NEXT_FEW_HOURS

        return TimeContextEnum.TODAY

    @staticmethod
    def _map_advisory_type(
        hazards: List[HazardDetection],
        persona: PersonaEnum,
        has_warning: bool
    ) -> AdvisoryTypeEnum:
        """Maps detected hazards and persona to an AdvisoryTypeEnum."""
        if has_warning:
            return AdvisoryTypeEnum.OFFICIAL_WARNING

        if not hazards:
            return AdvisoryTypeEnum.WEATHER_SUMMARY

        all_types = [h.hazard_type.lower() for h in hazards]

        if persona == PersonaEnum.FISHERMAN and any(any(k in t for k in ("wind", "cyclone", "gale", "thunderstorm", "marine", "rain")) for t in all_types):
            return AdvisoryTypeEnum.FISHING_CAUTION
        if persona == PersonaEnum.FARMER and any(any(k in t for k in ("rain", "heat", "cold", "wind")) for t in all_types):
            return AdvisoryTypeEnum.FARM_ACTIVITY_CAUTION
        if persona in (PersonaEnum.COMMUTER, PersonaEnum.TRAVELLER, PersonaEnum.STUDENT) and any(any(k in t for k in ("rain", "fog", "visibility", "thunderstorm")) for t in all_types):
            return AdvisoryTypeEnum.TRAVEL_CAUTION

        primary_ht = hazards[0].hazard_type.lower()
        if "cyclone" in primary_ht or "extreme_rain" in primary_ht:
            return AdvisoryTypeEnum.EXTREME_RAIN_ALERT
        if "rain" in primary_ht:
            return AdvisoryTypeEnum.RAIN_CAUTION
        if "wind" in primary_ht:
            return AdvisoryTypeEnum.WIND_CAUTION
        if "heat" in primary_ht:
            return AdvisoryTypeEnum.HEAT_CAUTION
        if "cold" in primary_ht:
            return AdvisoryTypeEnum.COLD_CAUTION
        if "thunderstorm" in primary_ht or "lightning" in primary_ht:
            return AdvisoryTypeEnum.THUNDERSTORM_CAUTION
        if "visibility" in primary_ht or "fog" in primary_ht:
            return AdvisoryTypeEnum.VISIBILITY_CAUTION

        return AdvisoryTypeEnum.OUTDOOR_ACTIVITY_CAUTION

    @classmethod
    def generate_advisory(
        cls,
        reasoning: WeatherReasoningResult,
        persona: PersonaEnum = PersonaEnum.GENERAL,
        target_language: LanguageEnum = LanguageEnum.EN,
        nlu: Optional[NLUResult] = None,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
    ) -> DecisionAdvisory:
        """Generates structured advice tailored to user persona, risk, and official warnings."""
        resolved_persona = cls._normalize_persona(persona)
        risk = reasoning.overall_risk
        active_warning = reasoning.active_warnings[0] if reasoning.active_warnings else None
        warning_present = active_warning is not None

        is_tamil = target_language in (LanguageEnum.TA, LanguageEnum.TANGLISH)
        is_hindi = target_language in (LanguageEnum.HI, LanguageEnum.HINGLISH)

        all_hazards = reasoning.detected_hazards or reasoning.ai_detected_hazards or []
        primary_hazard = all_hazards[0] if all_hazards else None

        # Determine time context
        time_context = cls._determine_time_context(nlu, all_hazards)

        # Initialize structured fields
        reason_codes: List[str] = []
        source_basis: List[str] = []
        evidence: List[str] = []
        precautions: List[str] = []
        headline = ""
        advisory_text = ""
        risk_summary = ""

        # Check for Missing Data / Empty Weather
        temp = getattr(weather, "temperature", None) if weather else None
        cond = getattr(weather, "weather_condition", None) if weather else None
        if not reasoning.data_complete or (weather is not None and temp is None and (cond is None or cond == "Unknown")):
            advisory_type = AdvisoryTypeEnum.DATA_UNAVAILABLE
            priority = AdvisoryPriorityEnum.LOW
            time_context = TimeContextEnum.NOW
            reason_codes.append("DATA_INCOMPLETE_OR_UNAVAILABLE")
            source_basis.append("reasoner_validation")
            evidence.append("Critical weather telemetry is missing or incomplete; conservative guidance applied.")

            if is_tamil:
                headline = "வானிலை தரவு கிடைக்கவில்லை"
                advisory_text = "தற்போதைய வானிலை தகவல் முழுமையாக கிடைக்கவில்லை. அதிகாரப்பூர்வ IMD தளங்களைச் சரிபார்க்கவும்."
                risk_summary = "முழுமையான வானிலை அளவீடுகள் இல்லை."
                precautions = ["பாதுகாப்பான பயணத்திற்கு அதிகாரப்பூர்வ IMD அறிவிப்புகளைச் சரிபார்க்கவும்"]
            elif is_hindi:
                headline = "मौसम डेटा अनुपलब्ध या अधूरा"
                advisory_text = "वर्तमान मौसम की सटीक जानकारी उपलब्ध नहीं है। आधिकारिक IMD पोर्टल देखें।"
                risk_summary = "मौसम संबंधी संपूर्ण आंकड़े उपलब्ध नहीं हैं।"
                precautions = ["सटीक जानकारी के लिए आधिकारिक IMD बुलेटिन देखें", "अनुपलब्ध मौसम को सुरक्षित न समझें"]
            else:
                headline = "Weather Data Incomplete or Unavailable"
                advisory_text = "Reliable meteorological observations are currently unavailable for this location."
                risk_summary = "Critical observation telemetry missing; safety cannot be independently verified."
                precautions = [
                    "Verify local conditions through official IMD portals",
                    "Do not assume unobserved conditions are clear or safe"
                ]

            timestamp_str = f"Data updated {reasoning.data_age_minutes}m ago ({reasoning.freshness.value})"
            source_str = f"Source: {', '.join(reasoning.sources_used) if reasoning.sources_used else 'Unknown'}"

            return DecisionAdvisory(
                persona=resolved_persona,
                risk_level=risk,
                headline=headline,
                advisory_text=advisory_text,
                key_precautions=precautions,
                official_warning_present=warning_present,
                official_warning_title=active_warning.title if active_warning else None,
                source_attribution=source_str,
                timestamp_info=timestamp_str,
                advisory_type=advisory_type,
                priority=priority,
                time_context=time_context,
                reason_codes=reason_codes,
                risk_summary=risk_summary,
                action_guidance=precautions,
                source_basis=source_basis,
                evidence=evidence,
            )

        # 1. OFFICIAL WARNING OVERRIDE (HIGHEST PRIORITY)
        if warning_present:
            advisory_type = AdvisoryTypeEnum.OFFICIAL_WARNING
            source_basis.append("official_alert")
            reason_codes.append(f"OFFICIAL_{active_warning.type.upper()}_ALERT")
            evidence.append(f"Authoritative official alert issued by {active_warning.source}: {active_warning.title} ({active_warning.severity.value})")

            if active_warning.severity in (RiskLevelEnum.EXTREME, RiskLevelEnum.HIGH):
                priority = AdvisoryPriorityEnum.CRITICAL
            else:
                priority = AdvisoryPriorityEnum.HIGH

            risk = active_warning.severity
        else:
            # Map deterministic priority from verified risk
            advisory_type = cls._map_advisory_type(all_hazards, resolved_persona, warning_present)
            if risk == RiskLevelEnum.EXTREME:
                priority = AdvisoryPriorityEnum.CRITICAL
            elif risk == RiskLevelEnum.HIGH:
                priority = AdvisoryPriorityEnum.HIGH
            elif risk == RiskLevelEnum.MEDIUM:
                priority = AdvisoryPriorityEnum.MEDIUM
            else:
                priority = AdvisoryPriorityEnum.LOW if risk == RiskLevelEnum.LOW else AdvisoryPriorityEnum.INFO

        # Track source basis & reason codes
        if primary_hazard:
            source_basis.append("detected_hazard")
            reason_codes.append(f"HAZARD_{primary_hazard.hazard_type.upper()}")
            scope = cls._get_hazard_temporal_scope(primary_hazard)
            evidence.append(f"Detected hazard '{primary_hazard.hazard_type}' with severity '{primary_hazard.severity.value}' (temporal scope: {scope})")
        if forecast:
            source_basis.append("forecast")
        if weather:
            source_basis.append("live_observation")

        # Source consistency / contradiction check
        if reasoning.consistency_score < 70 or reasoning.contradictions:
            reason_codes.append("SOURCE_DISAGREEMENT")
            evidence.append(f"Data consistency score is {reasoning.consistency_score}/100 with {len(reasoning.contradictions)} detected contradictions; adopting conservative posture.")

        # Stale telemetry check
        if reasoning.data_age_minutes > 120 or reasoning.freshness.value == "stale":
            reason_codes.append("STALE_DATA_NOTICE")
            evidence.append(f"Telemetry is aged {reasoning.data_age_minutes}m ({reasoning.freshness.value}); real-time verification recommended.")

        # ---------------- PERSONA-SPECIFIC LOGIC ----------------

        # ---------------- STUDENT PERSONA ----------------
        if resolved_persona == PersonaEnum.STUDENT:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or warning_present:
                reason_codes.append("STUDENT_COMMUTE_SAFETY")
                risk_summary = "Significant precipitation or hazardous weather detected during commute window."
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
                elif is_hindi:
                    headline = "मौसम चेतावनी — स्कूल/कॉलेज यात्रा में सावधानी बरतें"
                    advisory_text = (
                        "भारी बारिश या गंभीर मौसम की संभावना है। "
                        "अनावश्यक बाहरी यात्रा से बचें और कक्षाओं व छुट्टी से संबंधित संस्थान की आधिकारिक घोषणाओं पर नजर रखें।"
                    )
                    precautions = [
                        "रेनकोट या छाता साथ रखें",
                        "जलभराव वाले रास्तों और खुले नालों से बचें",
                        "संस्थान की आधिकारिक सूचनाएं देखें (WeatherGPT छुट्टियां घोषित नहीं करता)"
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
                reason_codes.append("STUDENT_TRANSIT_DELAY")
                risk_summary = "Moderate rain likely, possible minor transit delays."
                if is_tamil:
                    headline = "மிதமான மழை வாய்ப்பு — பயணத்திற்கு தயாராக இருங்கள்"
                    advisory_text = "மழை பெய்ய வாய்ப்புள்ளது. பொதுப்போக்குவரத்து காலதாமதத்திற்கு திட்டமிடுங்கள்."
                    precautions = ["குடை எடுத்துச் செல்லவும்", "பயணத்தை முன்கூட்டியே தொடங்கவும்"]
                elif is_hindi:
                    headline = "मध्यम बारिश की संभावना — यात्रा के लिए तैयार रहें"
                    advisory_text = "हल्की से मध्यम बारिश की संभावना है। यात्रा में थोड़ी देरी हो सकती है।"
                    precautions = ["छाता साथ रखें", "समय से पहले निकलें"]
                else:
                    headline = "Moderate Rain Expected — Prepare for Commute"
                    advisory_text = "Precipitation is likely. Anticipate minor transit delays during morning/evening commute."
                    precautions = ["Keep an umbrella handy", "Allow extra commute time"]
            else:
                reason_codes.append("STUDENT_NORMAL_ROUTINE")
                risk_summary = "Weather conditions are stable and clear."
                if is_tamil:
                    headline = "சாதகமான வானிலை"
                    advisory_text = "வானிலை பொதுவாக சாதகமாக உள்ளது. இயல்பான பயணத்தை மேற்கொள்ளலாம்."
                    precautions = ["வழக்கமான பயண ஏற்பாடுகள் போதுமானது"]
                elif is_hindi:
                    headline = "अनुकूल मौसम"
                    advisory_text = "मौसम साफ और यात्रा व कैंपस गतिविधियों के लिए अनुकूल है।"
                    precautions = ["सामान्य दिनचर्या लागू होती है"]
                else:
                    headline = "Normal Weather Conditions"
                    advisory_text = "Weather conditions are stable for travel and outdoor campus activities."
                    precautions = ["Standard commuter routine applies"]

        # ---------------- COMMUTER PERSONA ----------------
        elif resolved_persona == PersonaEnum.COMMUTER:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or warning_present:
                reason_codes.append("COMMUTER_SEVERE_TRANSIT_DISRUPTION")
                risk_summary = "Severe weather conditions likely to cause significant traffic slowdowns and waterlogging."
                if is_tamil:
                    headline = "போக்குவரத்து எச்சரிக்கை — பயண தாமதம் மற்றும் நீர் தேங்குதல் வாய்ப்பு"
                    advisory_text = "கனமழை காரணமாக சாலைகளில் நீர் தேங்க வாய்ப்புள்ளது. அவசியமற்ற பயணங்களைத் தவிர்க்கவும்."
                    precautions = [
                        "பயணத்திற்கு 20-30 நிமிடங்கள் கூடுதல் நேரம் ஒதுக்கவும்",
                        "தாழ்வான பாலங்கள் மற்றும் நீர் தேங்கிய சுரங்கப்பாதைகளைத் தவிர்க்கவும்",
                        "மழைக்கால பாதுகாப்பு கியர் மற்றும் குடையை உடன் வைத்திருக்கவும்"
                    ]
                elif is_hindi:
                    headline = "यातायात चेतावनी — भारी बारिश और जलभराव का खतरा"
                    advisory_text = "गंभीर मौसम के कारण सड़क और रेल यातायात में देरी हो सकती है। सुरक्षित रहें।"
                    precautions = [
                        "यात्रा के लिए 20-30 मिनट अतिरिक्त समय लें",
                        "जलभराव वाले अंडरपास, सबवे और खुले नालों से बचें",
                        "मेट्रो व बस के ताजा अपडेट देखें",
                        "रेनकोट या छाता साथ रखें"
                    ]
                else:
                    headline = "Commute Alert — Travel Delays & Waterlogging Risk"
                    advisory_text = "Hazardous weather conditions detected. Significant road transit and rail delays expected."
                    precautions = [
                        "Allow 20-30 minutes extra travel time",
                        "Avoid waterlogged underpasses, subway corridors, and open drains",
                        "Check public transit and metro status updates before departure",
                        "Carry waterproof gear and umbrella"
                    ]
            elif risk == RiskLevelEnum.MEDIUM:
                reason_codes.append("COMMUTER_MODERATE_RAIN")
                risk_summary = "Moderate precipitation expected to cause minor commute bottlenecks."
                if is_tamil:
                    headline = "பயண ஆலோசனை — மிதமான மழை வாய்ப்பு"
                    advisory_text = "மழை காரணமாக போக்குவரத்து தாமதமாகலாம். முன்கூட்டியே புறப்படவும்."
                    precautions = ["குடை அல்லது மழைக்கோட்டு எடுத்துச் செல்லவும்", "கூடுதல் பயண நேரத்தை திட்டமிடவும்"]
                elif is_hindi:
                    headline = "यात्रा सलाह — मध्यम बारिश की संभावना"
                    advisory_text = "बारिश के कारण सड़कों पर फिसलन और यातायात धीमा हो सकता है।"
                    precautions = ["छाता या रेनकोट साथ रखें", "अतिरिक्त समय लेकर चलें"]
                else:
                    headline = "Commute Advisory — Moderate Rain Expected"
                    advisory_text = "Wet road surfaces and minor transit delays expected along commuter routes."
                    precautions = [
                        "Keep rain protection handy",
                        "Allow buffer time for morning/evening transit"
                    ]
            else:
                reason_codes.append("COMMUTER_NORMAL_TRAFFIC")
                risk_summary = "Clear weather with normal traffic flow expected."
                if is_tamil:
                    headline = "சாதகமான போக்குவரத்து வானிலை"
                    advisory_text = "பயணத்திற்கான வானிலை சாதகமாக உள்ளது. போக்குவரத்து வழக்கம் போல் இயங்கும்."
                    precautions = ["வழக்கமான பயண ஏற்பாடுகள் போதுமானது"]
                elif is_hindi:
                    headline = "सामान्य यातायात स्थिति"
                    advisory_text = "मौसम साफ है और आवागमन सामान्य रहने की उम्मीद है।"
                    precautions = ["सामान्य यात्रा दिनचर्या लागू होती है", "सड़क व यातायात स्थिति सामान्य"]
                else:
                    headline = "Normal Commute Conditions"
                    advisory_text = "Weather conditions are clear and conducive to normal transit and road travel."
                    precautions = ["Standard commute routine applies", "Road and transit conditions clear"]

        # ---------------- FISHERMAN PERSONA ----------------
        elif resolved_persona == PersonaEnum.FISHERMAN:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or warning_present:
                reason_codes.append("FISHERMAN_SEA_VENTURING_PROHIBITION")
                risk_summary = "Dangerous sea state with squally winds and high wave activity."
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
                elif is_hindi:
                    headline = "समुद्री मौसम चेतावनी — समुद्र में न जाएं"
                    advisory_text = (
                        "तेज हवाएं और समुद्र में ऊंची लहरें उठने की आशंका है। "
                        "मछुआरों को समुद्र में न जाने की सख्त सलाह दी जाती है।"
                    )
                    precautions = [
                        "गहरे समुद्र में मछली पकड़ने न जाएं",
                        "नावों और जालों को सुरक्षित ऊंचे स्थानों पर बांधें",
                        "तटीय रेडियो और IMD समुद्री बुलेटिन को सुनते रहें"
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
                reason_codes.append("FISHERMAN_FAVORABLE_MARINE")
                risk_summary = "Wind speed and wave heights within normal safe operating limits."
                if is_tamil:
                    headline = "சாதகமான கடல் நிலை"
                    advisory_text = "தற்போது கடல் கொந்தளிப்புக்கான எச்சரிக்கைகள் இல்லை. எச்சரிக்கையுடன் தொழிலை மேற்கொள்ளவும்."
                    precautions = ["வானொலி தொடர்பு சாதனங்களை தயாராக வைத்திருக்கவும்"]
                elif is_hindi:
                    headline = "अनुकूल समुद्री स्थिति"
                    advisory_text = "हवा की गति और समुद्र की स्थिति सामान्य परिचालन सीमा के भीतर है।"
                    precautions = ["मानक लाइफ जैकेट और संचार उपकरण तैयार रखें"]
                else:
                    headline = "Favorable Marine Conditions"
                    advisory_text = "Wind speed and sea state are currently within normal operational limits."
                    precautions = ["Maintain standard onboard communication and life jacket safety"]

        # ---------------- FARMER PERSONA ----------------
        elif resolved_persona == PersonaEnum.FARMER:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or warning_present:
                reason_codes.append("FARMER_CROP_AND_DRAINAGE_PROTECTION")
                risk_summary = "Heavy rainfall or extreme conditions threatening soil inundation and nutrient runoff."
                if is_tamil:
                    headline = "கனமழை எச்சரிக்கை — பயிர் பாதுகாப்பு ஆலோசனை"
                    advisory_text = "கனமழை எதிர்பார்க்கப்படுவதால் நீர் தேங்குவதைத் தடுக்க வடிகால் வசதிகளைச் சரிசெய்யவும்."
                    precautions = [
                        "வயல்களில் பாசனம் செய்வதைத் தவிர்க்கவும்",
                        "உரங்கள் அல்லது பூச்சிக்கொல்லி தெளிப்பதை ஒத்திவைக்கவும்",
                        "அறுவடை செய்த பயிர்களைப் பாதுகாப்பான இடங்களில் சேமிக்கவும்"
                    ]
                elif is_hindi:
                    headline = "कृषि सलाह — भारी बारिश की चेतावनी"
                    advisory_text = "भारी बारिश के कारण खेतों में जलभराव हो सकता है। उचित जल निकासी की व्यवस्था करें।"
                    precautions = [
                        "सिंचाई तुरंत रोक दें",
                        "उर्वरक और कीटनाशक छिड़काव स्थगित करें",
                        "कटी हुई फसलों को सुरक्षित ढके हुए स्थान पर रखें"
                    ]
                else:
                    headline = "Agricultural Advisory — Heavy Precipitation Ahead"
                    advisory_text = "Heavy rainfall can lead to field inundation and nutrient runoff."
                    precautions = [
                        "Suspend irrigation immediately",
                        "Postpone fertilizer and pesticide applications to prevent runoff",
                        "Clear field drainage channels and secure harvested produce under cover"
                    ]
            elif risk == RiskLevelEnum.MEDIUM:
                reason_codes.append("FARMER_MODERATE_WEATHER")
                risk_summary = "Moderate showers expected; adjust irrigation schedules accordingly."
                if is_tamil:
                    headline = "விவசாய ஆலோசனை — மிதமான மழை வாய்ப்பு"
                    advisory_text = "மிதமான மழை எதிர்பார்க்கப்படுகிறது. பாசன அளவைக் குறைக்கவும்."
                    precautions = ["பாசனத்தை தற்காலிகமாக குறைக்கவும்", "வடிகால் பாதைகளைச் சரிபார்க்கவும்"]
                elif is_hindi:
                    headline = "कृषि सलाह — मध्यम बारिश की संभावना"
                    advisory_text = "मध्यम बारिश की संभावना है। सिंचाई की आवश्यकता को तदनुसार समायोजित करें।"
                    precautions = ["नियमित सिंचाई स्थगित रखें", "खेतों के निकास मार्ग खुले रखें"]
                else:
                    headline = "Agricultural Advisory — Moderate Showers"
                    advisory_text = "Moderate showers expected. Regulate irrigation to avoid excessive soil moisture."
                    precautions = [
                        "Withhold scheduled irrigation until soil moisture stabilizes",
                        "Ensure field channels are clear"
                    ]
            else:
                reason_codes.append("FARMER_STANDARD_CULTIVATION")
                risk_summary = "Optimal temperature and moisture levels for standard farming operations."
                if is_tamil:
                    headline = "இயல்பான விவசாய வானிலை"
                    advisory_text = "விவசாய பணிகளுக்கு வானிலை ஏற்றதாக உள்ளது."
                    precautions = ["வழக்கமான பாசன அட்டவணையைப் பின்பற்றவும்"]
                elif is_hindi:
                    headline = "सामान्य कृषि मौसम"
                    advisory_text = "फसल प्रबंधन और खेती के सामान्य कार्यों के लिए मौसम अनुकूल है।"
                    precautions = ["सामान्य सिंचाई चक्र जारी रखें"]
                else:
                    headline = "Standard Agricultural Conditions"
                    advisory_text = "Favorable conditions for routine cultivation and field management."
                    precautions = ["Proceed with standard irrigation schedule"]

        # ---------------- TRAVELLER PERSONA ----------------
        elif resolved_persona == PersonaEnum.TRAVELLER:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or warning_present:
                reason_codes.append("TRAVELLER_SEVERE_WEATHER_ALERT")
                risk_summary = "Severe weather conditions posing risks to intercity transit, flight, and train schedules."
                if is_tamil:
                    headline = "பயண எச்சரிக்கை — தீவிர வானிலை நிலவுகிறது"
                    advisory_text = "மோசமான வானிலை காரணமாக நீண்ட தூர பயணங்களைத் தள்ளிப்போடவும்."
                    precautions = [
                        "விமானம் மற்றும் ரயில் அட்டவணை மாற்றங்களைச் சரிபார்க்கவும்",
                        "நெடுஞ்சாலை பயணங்களின் போது வேகத்தைக் குறைத்து ஓட்டவும்",
                        "அவசர மருத்துவ மற்றும் உணவுப் பொருட்களை எடுத்துச் செல்லவும்"
                    ]
                elif is_hindi:
                    headline = "यात्रा चेतावनी — खराब मौसम"
                    advisory_text = "मौसम खराब होने के कारण लंबी दूरी की यात्रा में रुकावट आ सकती है।"
                    precautions = [
                        "हाइवे और ट्रेन के ताजा शेड्यूल चेक करें",
                        "गाड़ी चलाते समय गति धीमी रखें",
                        "बाढ़ संभावित रास्तों से बचें"
                    ]
                else:
                    headline = "Travel Alert — Severe Weather Ahead"
                    advisory_text = "Severe weather conditions detected across travel corridors. Significant delays anticipated."
                    precautions = [
                        "Verify highway road status and train schedules before departure",
                        "Expect significant speed restrictions and transit delays",
                        "Avoid non-essential transit across flood-prone corridors"
                    ]
            else:
                reason_codes.append("TRAVELLER_CLEAR_ITINERARY")
                risk_summary = "Clear weather with good transit visibility."
                if is_tamil:
                    headline = "பயணத்திற்கான சாதகமான வானிலை"
                    advisory_text = "பயணங்களுக்கு வானிலை சாதகமாக உள்ளது."
                    precautions = ["வழக்கமான பயண ஏற்பாடுகள் போதுமானது"]
                elif is_hindi:
                    headline = "यात्रा के लिए अनुकूल मौसम"
                    advisory_text = "यात्रा और आउटडोर गतिविधियों के लिए मौसम अच्छा है।"
                    precautions = ["सामान्य यात्रा कार्यक्रम लागू होता है"]
                else:
                    headline = "Favorable Travel Conditions"
                    advisory_text = "Favorable conditions for intercity and outdoor travel."
                    precautions = ["Standard travel itinerary applies"]

        # ---------------- DISASTER RESPONSE PERSONA ----------------
        elif resolved_persona == PersonaEnum.DISASTER_RESPONSE:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or warning_present:
                reason_codes.append("DISASTER_RESPONSE_STANDBY_MOBILIZATION")
                risk_summary = "High-impact disaster hazard active or impending; emergency preparedness required."
                if is_tamil:
                    headline = "பேரிடர் மேலாண்மை தயார்நிலை எச்சரிக்கை"
                    advisory_text = "தீவிர வானிலை காரணமாக உடனடி மீட்பு மற்றும் நிவாரண குழுக்கள் தயார்நிலையில் இருக்க வேண்டும்."
                    precautions = [
                        "பாதிக்கப்படக்கூடிய தாழ்வான பகுதிகளைக் கண்காணிக்கவும்",
                        "நீர் இறைக்கும் இயந்திரங்கள் மற்றும் தற்காலிக முகாம்களைத் தயார் செய்யவும்",
                        "IMD மற்றும் மாநில அவசர கட்டுப்பாட்டு மைய அறிவிப்புகளைத் தொடர்ந்து கண்காணிக்கவும்"
                    ]
                elif is_hindi:
                    headline = "आपदा प्रबंधन सतर्कता चेतावनी"
                    advisory_text = "गंभीर मौसम के प्रभाव को देखते हुए आपातकालीन दल स्टैंडबाय पर रहें।"
                    precautions = [
                        "निचले संवेदनशील क्षेत्रों की निगरानी करें",
                        "जल निकासी पंप और राहत सामग्री तैयार रखें",
                        "IMD रडार और आधिकारिक चेतावनी बुलेटिन ट्रैक करें"
                    ]
                else:
                    headline = "Disaster Response Alert — Standby Mobilization"
                    advisory_text = "High-impact hazard criteria met. Pre-position emergency dewatering and rescue assets."
                    precautions = [
                        "Activate standby response protocols for designated vulnerable sectors",
                        "Ensure emergency dewatering pumps and relief supplies are positioned",
                        "Continuously monitor real-time IMD radar feeds and official emergency bulletins"
                    ]
            else:
                reason_codes.append("DISASTER_RESPONSE_SITUATIONAL_MONITORING")
                risk_summary = "Baseline calm conditions; situational monitoring standard."
                if is_tamil:
                    headline = "இயல்பான பேரிடர் கண்காணிப்பு"
                    advisory_text = "தற்போது தீவிர வானிலை அச்சுறுத்தல்கள் இல்லை. வழக்கமான கண்காணிப்பு தொடர்கிறது."
                    precautions = ["வழக்கமான கண்காணிப்பு நடைமுறைகளைப் பின்பற்றவும்"]
                elif is_hindi:
                    headline = "सामान्य निगरानी स्थिति"
                    advisory_text = "कोई सक्रिय आपदा खतरा नहीं है। नियमित निगरानी जारी रखें।"
                    precautions = ["मानक स्थिति निगरानी बनाए रखें", "कोई आपातकालीन लामबंदी आवश्यक नहीं"]
                else:
                    headline = "Routine Situational Monitoring"
                    advisory_text = "No active disaster hazards detected. Maintain routine background surveillance."
                    precautions = ["Standard situational monitoring standard", "No emergency response mobilization required"]

        # ---------------- GENERAL / GENERAL_USER PERSONA (DEFAULT) ----------------
        else:
            if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) or warning_present:
                reason_codes.append("GENERAL_SEVERE_WEATHER_ALERT")
                risk_summary = "Severe weather conditions active; personal outdoor safety precautions required."
                if is_tamil:
                    headline = "தீவிர வானிலை எச்சரிக்கை"
                    advisory_text = "மோசமான வானிலை நிலவுகிறது. அவசியமற்ற பயணங்களைத் தவிர்த்து பாதுகாப்புடன் இருக்கவும்."
                    precautions = [
                        "Stay indoors during peak storm activity",
                        "Keep emergency lights and phones charged",
                        "Follow official government guidelines"
                    ]
                elif is_hindi:
                    headline = "गंभीर मौसम चेतावनी सक्रिय"
                    advisory_text = "खराब मौसम की स्थिति बनी हुई है। अनावश्यक यात्रा से बचें और स्थानीय प्रशासन के निर्देशों का पालन करें।"
                    precautions = [
                        "तूफान के दौरान घर के अंदर रहें",
                        "इमरजेंसी लाइट और फोन चार्ज रखें",
                        "सरकारी दिशा-निर्देशों का पालन करें"
                    ]
                else:
                    headline = "Severe Weather Alert Active"
                    advisory_text = "Adverse weather conditions detected. Avoid non-essential travel and follow local authority advisories."
                    precautions = [
                        "Stay indoors during peak storm activity",
                        "Keep emergency lights and phones charged",
                        "Follow official government guidelines"
                    ]
            elif risk == RiskLevelEnum.MEDIUM:
                reason_codes.append("GENERAL_MODERATE_WEATHER")
                risk_summary = "Moderate weather variations; minor precautions advised."
                if is_tamil:
                    headline = "மிதமான வானிலை எச்சரிக்கை"
                    advisory_text = "வானிலையில் மாற்றங்கள் உள்ளன. எச்சரிக்கையுடன் செயல்படவும்."
                    precautions = ["குடை எடுத்துச் செல்லவும்", "வானிலை மாற்றங்களைக் கவனிக்கவும்"]
                elif is_hindi:
                    headline = "मध्यम मौसम सलाह"
                    advisory_text = "मौसम में बदलाव संभव है। बुनियादी सावधानी बरतें।"
                    precautions = ["छाता साथ रखें", "मौसम पर नजर रखें"]
                else:
                    headline = "Moderate Weather Conditions"
                    advisory_text = "Variable weather conditions expected. Carry basic outdoor protection."
                    precautions = ["Carry an umbrella or rain cover", "Plan outdoor activities around peak weather hours"]
            else:
                reason_codes.append("GENERAL_NORMAL_WEATHER")
                risk_summary = "Conditions are pleasant and within comfortable climatological bounds."
                if is_tamil:
                    headline = "மிதமான வானிலை"
                    advisory_text = "தீவிர வானிலை ஆபத்துகள் ஏதுமில்லை."
                    precautions = ["Standard outdoor precautions"]
                elif is_hindi:
                    headline = "सुखद / सामान्य मौसम"
                    advisory_text = "आपके क्षेत्र में कोई गंभीर मौसम खतरा नहीं है।"
                    precautions = ["मानक बाहरी सावधानियां"]
                else:
                    headline = "Pleasant / Moderate Weather"
                    advisory_text = "No severe weather hazards detected for your area."
                    precautions = ["Standard outdoor precautions"]

        # If source conflict detected, append conservative note to risk summary
        if "SOURCE_DISAGREEMENT" in reason_codes:
            if is_tamil:
                risk_summary += " (குறிப்பு: வானிலை தகவல் மூலங்களுக்கிடையே முரண்பாடு உள்ளது; எச்சரிக்கையுடன் செயல்படவும்.)"
            elif is_hindi:
                risk_summary += " (नोट: मौसम स्रोतों के बीच भिन्नता पाई गई है; सतर्कता बरतने की सलाह दी जाती है।)"
            else:
                risk_summary += " (Note: Disagreement detected across observation sources; exercising conservative caution.)"

        timestamp_str = f"Data updated {reasoning.data_age_minutes}m ago ({reasoning.freshness.value})"
        source_str = f"Source: {', '.join(reasoning.sources_used) if reasoning.sources_used else 'IMD'}"

        return DecisionAdvisory(
            persona=resolved_persona,
            risk_level=risk,
            headline=headline,
            advisory_text=advisory_text,
            key_precautions=precautions,
            official_warning_present=warning_present,
            official_warning_title=active_warning.title if active_warning else None,
            source_attribution=source_str,
            timestamp_info=timestamp_str,
            advisory_type=advisory_type,
            priority=priority,
            time_context=time_context,
            reason_codes=reason_codes,
            risk_summary=risk_summary,
            action_guidance=precautions,
            source_basis=source_basis,
            evidence=evidence,
        )
