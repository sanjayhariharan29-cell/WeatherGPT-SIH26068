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
            if p_str in ("disaster_response", "disaster", "emergency", "safety", "disaster_safety"):
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
    def _parse_hour(cls, time_str: Optional[str]) -> Optional[int]:
        """Parses hour (0-23) from time string representation."""
        if not time_str:
            return None
        import re
        s = str(time_str).strip()
        m_hour = re.search(r"(\d{1,2}):\d{2}", s)
        if m_hour:
            h = int(m_hour.group(1))
            if "pm" in s.lower() and h < 12:
                h += 12
            elif "am" in s.lower() and h == 12:
                h = 0
            return h
        m_ampm = re.search(r"\b(\d{1,2})\s*(am|pm)\b", s, re.IGNORECASE)
        if m_ampm:
            h = int(m_ampm.group(1))
            meridiem = m_ampm.group(2).lower()
            if meridiem == "pm" and h < 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            return h
        m_single = re.match(r"^(\d{1,2})$", s)
        if m_single:
            h = int(m_single.group(1))
            if 0 <= h <= 23:
                return h
        lower = s.lower()
        if "morning" in lower:
            return 8
        if "noon" in lower:
            return 12
        if "afternoon" in lower:
            return 14
        if "evening" in lower:
            return 17
        if "night" in lower:
            return 21
        return None

    @classmethod
    def _matches_hour(cls, fc_item: Any, target_hour: int, label: str) -> bool:
        """Checks whether a forecast item corresponds to the requested hour/window."""
        t_str = str(getattr(fc_item, "time", getattr(fc_item, "forecast_time", "")))
        h = cls._parse_hour(t_str)
        if h is not None and abs(h - target_hour) <= 1:
            return True
        if label and label.lower() in t_str.lower():
            return True
        return False

    @classmethod
    def _evaluate_schedule_windows(
        cls,
        nlu: Optional[NLUResult],
        forecast: Optional[List[ForecastItem]],
        weather: Optional[WeatherRecord],
        reasoning: WeatherReasoningResult
    ) -> Dict[str, Any]:
        """Deterministically evaluates commute schedule and rainfall risk for departure/return periods."""
        import re
        raw_text = (nlu.original_text.lower() if nlu and nlu.original_text else "")
        entities = getattr(nlu, "entities", None)

        dep_time_str = getattr(entities, "departure_time", None)
        ret_time_str = getattr(entities, "return_time", None)

        # Check entities.time if departure or return
        gen_time = getattr(entities, "time", None) if entities else None
        if not dep_time_str and gen_time and any(k in raw_text for k in ["morning", "leave", "depart", "going"]):
            dep_time_str = gen_time
        if not ret_time_str and gen_time and any(k in raw_text for k in ["evening", "back", "return", "night"]):
            ret_time_str = gen_time

        # Infer from text if not on entities
        if not dep_time_str:
            dep_m = re.search(r"\b(?:leave|depart|going|at)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", raw_text)
            if dep_m and "am" in dep_m.group(1).lower():
                dep_time_str = dep_m.group(1).upper()
            elif dep_m and any(k in raw_text for k in ["morning", "leave", "depart"]):
                val = dep_m.group(1).strip()
                h = cls._parse_hour(val)
                if h is not None:
                    dep_time_str = f"{h}:00 AM" if h <= 12 else f"{h}:00"

        if not ret_time_str:
            ret_m = re.search(r"\b(?:return|back|reach|at)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", raw_text)
            if ret_m:
                val = ret_m.group(1).strip()
                if "pm" in val.lower():
                    ret_time_str = val.upper()
                elif any(k in raw_text for k in ["back", "return", "evening", "after college"]):
                    h = cls._parse_hour(val)
                    if h is not None:
                        if 1 <= h <= 11:
                            ret_time_str = f"{h}:00 PM"
                        else:
                            ret_time_str = f"{h}:00"

        has_explicit_schedule = bool(dep_time_str or ret_time_str) or ("8 am" in raw_text and "5 pm" in raw_text)
        is_leave_college = any(k in raw_text for k in ["leave college", "leaving college", "after college", "from college"])

        dep_str = dep_time_str or ("8:00 AM" if (has_explicit_schedule or "commute" in raw_text) else "8:00 AM")
        ret_str = ret_time_str or ("5:00 PM" if (has_explicit_schedule or is_leave_college or "commute" in raw_text) else "5:00 PM")

        dep_hour = cls._parse_hour(dep_str) or 8
        ret_hour = cls._parse_hour(ret_str) or 17

        fc_list = forecast or []
        dep_items = [fc for fc in fc_list if cls._matches_hour(fc, dep_hour, "morning")]
        ret_items = [fc for fc in fc_list if cls._matches_hour(fc, ret_hour, "evening")]

        if not dep_items and fc_list:
            dep_items = [fc_list[0]]
        if not ret_items and fc_list:
            ret_items = [fc_list[-1]] if len(fc_list) > 1 else [fc_list[0]]

        weather_prob = float(weather.rain_probability or 0.0) if weather else 0.0

        dep_prob = max([float(fc.rain_probability or 0.0) for fc in dep_items], default=weather_prob)
        ret_prob = max([float(fc.rain_probability or 0.0) for fc in ret_items], default=weather_prob)

        REASONING_THRESHOLD = 30.0

        dep_has_rain = dep_prob >= REASONING_THRESHOLD or any("rain" in str(getattr(fc, "condition", "")).lower() for fc in dep_items)
        ret_has_rain = ret_prob >= REASONING_THRESHOLD or any("rain" in str(getattr(fc, "condition", "")).lower() for fc in ret_items)

        warning_present = bool(reasoning.active_warnings)
        recommend_umbrella = dep_has_rain or ret_has_rain or warning_present

        if is_leave_college and not has_explicit_schedule:
            if ret_has_rain or warning_present:
                rationale = f"Rain is expected when you leave college (~{ret_str}) with a {ret_prob:.0f}% precipitation chance. Carrying an umbrella is strongly recommended."
            else:
                rationale = f"Dry conditions expected when you leave college (~{ret_str}) with a {ret_prob:.0f}% precipitation chance. Carrying an umbrella is not strictly required."
        elif warning_present:
            rationale = "Official severe weather alert is active. Carrying an umbrella and protective rain gear is mandatory for your commute."
        elif dep_has_rain and ret_has_rain:
            rationale = f"Rain is forecast during both your morning departure at {dep_str} ({dep_prob:.0f}%) and evening return at {ret_str} ({ret_prob:.0f}%). Carrying an umbrella is strongly recommended."
        elif not dep_has_rain and ret_has_rain:
            rationale = f"Dry conditions for morning departure at {dep_str} ({dep_prob:.0f}%), but rain is forecast during your evening return at {ret_str} ({ret_prob:.0f}%). Carrying an umbrella is recommended for your return trip."
        elif dep_has_rain and not ret_has_rain:
            rationale = f"Rain is forecast during your morning departure at {dep_str} ({dep_prob:.0f}%). Carrying an umbrella is recommended."
        else:
            rationale = f"Dry conditions expected during both your departure at {dep_str} ({dep_prob:.0f}%) and return at {ret_str} ({ret_prob:.0f}%). Carrying an umbrella is not strictly required."

        return {
            "has_schedule": has_explicit_schedule or is_leave_college,
            "departure_time": dep_str,
            "return_time": ret_str,
            "departure_prob": dep_prob,
            "return_prob": ret_prob,
            "departure_has_rain": dep_has_rain,
            "return_has_rain": ret_has_rain,
            "recommend_umbrella": recommend_umbrella,
            "umbrella_rationale": rationale,
            "departure_risk": "high" if dep_prob >= 70 else ("moderate" if dep_prob >= 30 else "low"),
            "return_risk": "high" if ret_prob >= 70 else ("moderate" if ret_prob >= 30 else "low"),
        }

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

            from ai.decision.personal_decision import PersonalDecisionEngine
            raw_msg = (nlu.original_text if nlu else "")
            unavail_dec = PersonalDecisionEngine.evaluate(
                nlu=nlu,
                weather=weather,
                forecast=forecast,
                reasoning=reasoning,
                target_language=target_language,
                message=raw_msg,
                schedule_decision=None,
            )
            unavail_dec_dict = unavail_dec.to_dict()

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
                personal_decision=unavail_dec_dict,
                language=target_language,
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
        schedule_decision = cls._evaluate_schedule_windows(nlu, forecast, weather, reasoning)

        from ai.decision.personal_decision import PersonalDecisionEngine
        raw_msg = (nlu.original_text if nlu else "")
        personal_decision_res = PersonalDecisionEngine.evaluate(
            nlu=nlu,
            weather=weather,
            forecast=forecast,
            reasoning=reasoning,
            target_language=target_language,
            message=raw_msg,
            schedule_decision=schedule_decision,
        )
        personal_decision_dict = personal_decision_res.to_dict()
        evidence.append(f"Personal Decision: {personal_decision_res.verdict.value} - {personal_decision_res.recommended_action}")

        # ---------------- STUDENT PERSONA ----------------
        if resolved_persona == PersonaEnum.STUDENT:
            if warning_present:
                reason_codes.append("OFFICIAL_WARNING_STUDENT_ALERT")
                reason_codes.append("STUDENT_COMMUTE_SAFETY")
                risk_summary = f"Official warning active: {active_warning.title} ({active_warning.severity.value}). Commute hazard present."
                if is_tamil:
                    headline = f"⚠️ [அதிகாரப்பூர்வ எச்சரிக்கை] {active_warning.title}"
                    advisory_text = (
                        f"அதிகாரப்பூர்வ IMD எச்சரிக்கை நிலவுகிறது: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "கல்லூரி/பள்ளி மாணவர்களுக்கான ஆலோசனை: தேவையற்ற பயணங்களைத் தவிர்க்கவும். "
                        "வகுப்புகள் மற்றும் தேர்வுகள் குறித்த அதிகாரப்பூர்வ கல்வி நிறுவன அறிவிப்புகளைச் சரிபார்க்கவும். குடை அல்லது மழைக்கால பாதுகாப்பு எடுத்துச் செல்லவும்."
                    )
                    precautions = [
                        f"அதிகாரப்பூர்வ எச்சரிக்கை வழிகாட்டுதல்: {active_warning.title}",
                        "மழைக்கோட்டு அல்லது குடை எடுத்துச் செல்லவும்",
                        "நீர் தேங்கிய சாலைகள் மற்றும் தாழ்வான பகுதிகளைத் தவிர்க்கவும்",
                        "அதிகாரப்பூர்வ கல்வி நிறுவன அறிவிப்புகளைத் தொடர்ந்து கண்காணிக்கவும்"
                    ]
                elif is_hindi:
                    headline = f"⚠️ [आधिकारिक चेतावनी] {active_warning.title}"
                    advisory_text = (
                        f"आधिकारिक IMD चेतावनी सक्रिय है: {active_warning.title} ({active_warning.severity.value})। "
                        f"{active_warning.description}। "
                        "छात्रों के लिए सलाह: अनावश्यक यात्रा से बचें। "
                        "संस्थान की आधिकारिक सूचनाएं देखें (WeatherGPT छुट्टियां घोषित नहीं करता)। छाता या रेनकोट साथ रखें।"
                    )
                    precautions = [
                        f"आधिकारिक चेतावनी निर्देश: {active_warning.title}",
                        "रेनकोट या छाता साथ रखें",
                        "जलभराव वाले रास्तों और खुले नालों से बचें",
                        "संस्थान की आधिकारिक सूचनाएं देखें (WeatherGPT छुट्टियां घोषित नहीं करता)"
                    ]
                else:
                    headline = f"⚠️ [OFFICIAL IMD WARNING] {active_warning.title}"
                    advisory_text = (
                        f"OFFICIAL IMD WARNING ACTIVE: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "For students: Verify institutional circulars regarding class schedules and exams. "
                        "Do not commute through flooded corridors or waterlogged underpasses. Carrying rain protection is strongly recommended."
                    )
                    precautions = [
                        f"Official Warning Protocol: {active_warning.title}",
                        "Carry rain protection (waterproof bag, umbrella, raincoat)",
                        "Avoid waterlogged commuter corridors and open storm drains",
                        "Check official institutional notifications (WeatherGPT does not declare holidays)"
                    ]
            elif schedule_decision["recommend_umbrella"] or risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
                reason_codes.append("STUDENT_COMMUTE_SAFETY")
                reason_codes.append("SCHEDULE_RAIN_PROTECTION_RECOMMENDED")
                risk_summary = f"Precipitation expected during commute window ({schedule_decision['return_prob']:.0f}% return chance)."
                if is_tamil:
                    headline = "பயண நேரத்தில் மழை வாய்ப்பு — குடை எடுத்துச் செல்லவும்"
                    advisory_text = (
                        f"கல்லூரி பயண நேரத்தில் மழை பெய்ய வாய்ப்புள்ளது ({schedule_decision['return_prob']:.0f}%). "
                        "குடை அல்லது மழைக்கோட்டு எடுத்துச் செல்வது அவசியமாகும். தாழ்வான சாலைகளைத் தவிர்க்கவும். "
                        "பள்ளி/கல்லூரி வகுப்புகள் குறித்த கல்வி நிறுவன அதிகாரப்பூர்வ அறிவிப்புகளைச் சரிபார்க்கவும்."
                    )
                    precautions = [
                        "குடை அல்லது மழைக்கோட்டு எடுத்துச் செல்லவும்",
                        "நீர் தேங்கிய சாலைகள் மற்றும் தாழ்வான பகுதிகளைத் தவிர்க்கவும்",
                        "அதிகாரப்பூர்வ கல்வி நிறுவன அறிவிப்புகளைத் தொடர்ந்து கண்காணிக்கவும்"
                    ]
                elif is_hindi:
                    headline = "यात्रा में बारिश की संभावना — छाता साथ रखें"
                    advisory_text = (
                        f"कॉलेज यात्रा के समय बारिश की संभावना है ({schedule_decision['return_prob']:.0f}%)। "
                        "छाता या रेनकोट साथ रखना आवश्यक है। जलभराव वाले रास्तों से बचें। "
                        "संस्थान की आधिकारिक सूचनाएं देखें (WeatherGPT छुट्टियां घोषित नहीं करता)।"
                    )
                    precautions = [
                        "रेनकोट या छाता साथ रखें",
                        "जलभराव वाले रास्तों और खुले नालों से बचें",
                        "संस्थान की आधिकारिक सूचनाएं देखें (WeatherGPT छुट्टियां घोषित नहीं करता)"
                    ]
                else:
                    headline = "Rain Expected During Commute — Umbrella Recommended"
                    advisory_text = (
                        f"{schedule_decision['umbrella_rationale']} "
                        "Prioritize personal safety, avoid waterlogged corridors, and verify institutional notices regarding class schedules."
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
                    advisory_text = f"{schedule_decision['umbrella_rationale']} Anticipate minor transit delays during morning/evening commute."
                    precautions = ["Keep an umbrella handy", "Allow extra commute time"]
            else:
                reason_codes.append("STUDENT_NORMAL_ROUTINE")
                reason_codes.append("SCHEDULE_DRY_COMMUTE")
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
                    advisory_text = f"{schedule_decision['umbrella_rationale']} Weather conditions are stable for travel and outdoor campus activities."
                    precautions = ["Standard commuter routine applies", "Umbrella not strictly required for dry forecast"]

        # ---------------- COMMUTER PERSONA ----------------
        elif resolved_persona == PersonaEnum.COMMUTER:
            is_commute_rain = (
                (weather and (weather.rain_probability or 0) >= 30.0)
                or schedule_decision["recommend_umbrella"]
                or risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME)
                or any("rain" in h.hazard_type.lower() for h in all_hazards)
            )
            has_fog = any("fog" in h.hazard_type.lower() or "visibility" in h.hazard_type.lower() for h in all_hazards)
            w_spd = (weather.wind_speed or 0) if weather else 0

            if warning_present:
                reason_codes.append("OFFICIAL_WARNING_COMMUTER_ALERT")
                reason_codes.append("COMMUTER_SEVERE_TRANSIT_DISRUPTION")
                risk_summary = f"Official warning active: {active_warning.title}. Hazardous corridor transit conditions."
                if is_tamil:
                    headline = f"⚠️ [அதிகாரப்பூர்வ எச்சரிக்கை] {active_warning.title}"
                    advisory_text = (
                        f"அதிகாரப்பூர்வ IMD எச்சரிக்கை நிலவுகிறது: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "பயணிகளுக்கான ஆலோசனை: சாலைகளில் நீர் தேங்குதல் மற்றும் கடுமையான போக்குவரத்து தாமதங்கள் ஏற்படும். பயணத்திற்கு 20-30 நிமிடங்கள் கூடுதல் நேரம் ஒதுக்கவும்."
                    )
                    precautions = [
                        f"அதிகாரப்பூர்வ எச்சரிக்கை வழிகாட்டுதல்: {active_warning.title}",
                        "பயணத்திற்கு 20-30 நிமிடங்கள் கூடுதல் நேரம் ஒதுக்கவும்",
                        "தாழ்வான பாலங்கள் மற்றும் நீர் தேங்கிய சுரங்கப்பாதைகளைத் தவிர்க்கவும்",
                        "மழைக்கால பாதுகாப்பு கியர் மற்றும் குடையை உடன் வைத்திருக்கவும்"
                    ]
                elif is_hindi:
                    headline = f"⚠️ [आधिकारिक चेतावनी] {active_warning.title}"
                    advisory_text = (
                        f"आधिकारिक IMD चेतावनी सक्रिय है: {active_warning.title} ({active_warning.severity.value})। "
                        f"{active_warning.description}। "
                        "यात्रियों के लिए सलाह: सड़क और रेल यातायात में भारी देरी की आशंका है। यात्रा के लिए 20-30 मिनट अतिरिक्त समय लें।"
                    )
                    precautions = [
                        f"आधिकारिक चेतावनी निर्देश: {active_warning.title}",
                        "यात्रा के लिए 20-30 मिनट अतिरिक्त समय लें",
                        "जलभराव वाले अंडरपास, सबवे और खुले नालों से बचें",
                        "रेनकोट या छाता साथ रखें"
                    ]
                else:
                    headline = f"⚠️ [OFFICIAL IMD WARNING] {active_warning.title}"
                    advisory_text = (
                        f"OFFICIAL IMD WARNING ACTIVE: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "For commuters: Severe transit delays and corridor waterlogging expected. Allow 20-30 minutes extra travel time. Avoid flooded underpasses."
                    )
                    precautions = [
                        f"Official Warning Protocol: {active_warning.title}",
                        "Allow 20-30 minutes extra travel time",
                        "Avoid waterlogged underpasses, subway corridors, and open storm drains",
                        "Carry waterproof gear and umbrella"
                    ]
            elif is_commute_rain:
                reason_codes.append("COMMUTER_SEVERE_TRANSIT_DISRUPTION" if risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) else "COMMUTER_RAIN_TRANSIT_DELAY")
                risk_summary = "Wet roadways and commuter bottlenecks expected."
                if is_tamil:
                    headline = "போக்குவரத்து எச்சரிக்கை — பயண தாமதம் மற்றும் நீர் தேங்குதல் வாய்ப்பு"
                    advisory_text = "கனமழை / மழை காரணமாக சாலைகளில் நீர் தேங்க வாய்ப்புள்ளது. பயணத்திற்கு 20-30 நிமிடங்கள் கூடுதல் நேரம் ஒதுக்கவும்."
                    precautions = [
                        "பயணத்திற்கு 20-30 நிமிடங்கள் கூடுதல் நேரம் ஒதுக்கவும்",
                        "தாழ்வான பாலங்கள் மற்றும் நீர் தேங்கிய சுரங்கப்பாதைகளைத் தவிர்க்கவும்",
                        "மழைக்கால பாதுகாப்பு கியர் மற்றும் குடையை உடன் வைத்திருக்கவும்"
                    ]
                elif is_hindi:
                    headline = "यातायात चेतावनी — भारी बारिश और जलभराव का खतरा"
                    advisory_text = "बारिश के कारण सड़कों पर जलभराव और फिसलन हो सकती है। यात्रा के लिए 20-30 मिनट अतिरिक्त समय लें।"
                    precautions = [
                        "यात्रा के लिए 20-30 मिनट अतिरिक्त समय लें",
                        "जलभराव वाले अंडरपास, सबवे और खुले नालों से बचें",
                        "छाता या रेनकोट साथ रखें"
                    ]
                else:
                    headline = "Commute Alert — Travel Delays & Waterlogging Risk"
                    advisory_text = "Wet roadway surfaces and commuter traffic slowdowns expected. Allow 20-30 minutes extra travel time. Avoid waterlogged underpasses and carry rain protection."
                    precautions = [
                        "Allow 20-30 minutes extra travel time (buffer time for transit)",
                        "Avoid waterlogged underpasses, subway corridors, and open drains",
                        "Keep rain protection handy (waterproof gear and umbrella)",
                        "Check public transit and metro status updates before departure"
                    ]
            elif has_fog:
                reason_codes.append("COMMUTER_VISIBILITY_CAUTION")
                risk_summary = "Reduced visibility / fog along transit corridors."
                headline = "Commute Advisory — Reduced Visibility / Fog"
                advisory_text = "Reduced visibility conditions detected along travel corridors. Drive with low-beam headlights on, maintain safe braking distance, and reduce highway speeds."
                precautions = [
                    "Drive with low-beam headlights on",
                    "Maintain safe braking distance and observe speed limits"
                ]
            elif w_spd > 30.0:
                reason_codes.append("COMMUTER_CROSSWIND_HAZARD")
                risk_summary = "Strong crosswinds on elevated transit corridors."
                headline = "Commute Advisory — Strong Crosswinds"
                advisory_text = f"Strong crosswinds ({w_spd:.0f} km/h) reported along flyovers and open expressways. Two-wheeler riders should exercise extra caution."
                precautions = [
                    "Exercise caution on bridges, flyovers, and open expressways",
                    "Two-wheeler riders should reduce speed and brace for gusts"
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
            w_spd = (weather.wind_speed or 0) if weather else 0

            if warning_present:
                reason_codes.append("OFFICIAL_WARNING_FISHERMAN_ALERT")
                reason_codes.append("FISHERMAN_SEA_VENTURING_PROHIBITION")
                risk_summary = f"Official warning active: {active_warning.title}. Total sea venturing prohibition."
                if is_tamil:
                    headline = f"⚠️ [அதிகாரப்பூர்வ எச்சரிக்கை] {active_warning.title}"
                    advisory_text = (
                        f"அதிகாரப்பூர்வ IMD கடல் எச்சரிக்கை நிலவுகிறது: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "மீனவர்களுக்கான உத்தரவு: மீனவர்கள் கடலுக்குள் செல்ல வேண்டாம் என திட்டவட்டமாக எச்சரிக்கப்படுகிறார்கள். படகுகளைப் பாதுகாப்பான மேடான இடங்களில் கட்டவும்."
                    )
                    precautions = [
                        f"அதிகாரப்பூர்வ எச்சரிக்கை உத்தரவு: {active_warning.title}",
                        "ஆழ்கடல் மீன்பிடிப்பைத் தவிர்க்கவும்",
                        "படகு மற்றும் வலைகளைப் பாதுகாப்பான மேடான இடங்களில் கட்டவும்",
                        "மீன்வளத்துறை மற்றும் IMD வானிலை எச்சரிக்கைகளைக் கேட்கவும்"
                    ]
                elif is_hindi:
                    headline = f"⚠️ [आधिकारिक समुद्री चेतावनी] {active_warning.title}"
                    advisory_text = (
                        f"आधिकारिक IMD समुद्री चेतावनी सक्रिय है: {active_warning.title} ({active_warning.severity.value})। "
                        f"{active_warning.description}। "
                        "मछुआरों को समुद्र में न जाने की सख्त सलाह दी जाती है। नावों और जालों को सुरक्षित ऊंचे स्थानों पर बांधें।"
                    )
                    precautions = [
                        f"आधिकारिक चेतावनी निर्देश: {active_warning.title}",
                        "गहरे समुद्र में मछली पकड़ने न जाएं",
                        "नावों और जालों को सुरक्षित ऊंचे स्थानों पर बांधें",
                        "तटीय रेडियो और IMD समुद्री बुलेटिन को सुनते रहें"
                    ]
                else:
                    headline = f"⚠️ [OFFICIAL IMD WARNING] {active_warning.title}"
                    advisory_text = (
                        f"OFFICIAL IMD WARNING ACTIVE: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "For fishermen: Strictly prohibited from venturing into open or deep sea waters. Secure all small craft and equipment at safe moorings."
                    )
                    precautions = [
                        f"Authoritative IMD Warning Directive: {active_warning.title}",
                        "Do not venture into open sea",
                        "Secure all small craft and fishing equipment at designated safe moorings",
                        "Monitor coastal radio broadcasts for IMD marine bulletins"
                    ]
            elif w_spd > 40.0 or any("wind" in h.hazard_type.lower() or "cyclone" in h.hazard_type.lower() for h in all_hazards) or risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
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
                        f"Squally weather with hazardous wind gusts ({w_spd:.0f} km/h) and rough seas expected. "
                        "Fishermen are strictly advised not to venture into deep sea or coastal waters."
                    )
                    precautions = [
                        "Do not venture into open sea",
                        "Secure all small craft and fishing equipment at designated safe moorings",
                        "Monitor coastal radio broadcasts for IMD marine bulletins"
                    ]
            elif w_spd >= 25.0:
                reason_codes.append("FISHERMAN_COASTAL_CAUTION")
                risk_summary = "Choppy coastal waters with moderate wind speeds."
                headline = "Marine Caution — Choppy Coastal Waters"
                advisory_text = f"Moderate squally winds ({w_spd:.0f} km/h). Avoid deep sea venturing; remain within coastal range with verified VHF equipment."
                precautions = [
                    "Avoid venturing into deep offshore waters",
                    "Ensure mandatory life jackets and communication equipment on board"
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
                    advisory_text = f"Wind speed ({w_spd:.0f} km/h) and sea state are currently within normal safe operating limits."
                    precautions = ["Maintain standard onboard communication and life jacket safety", "Safe for coastal fishing operations"]

        # ---------------- FARMER PERSONA ----------------
        elif resolved_persona == PersonaEnum.FARMER:
            is_farm_rain = (weather and (weather.rain_probability or 0) >= 40.0) or any((fc.rain_probability or 0) >= 40.0 for fc in (forecast or [])) or any("rain" in h.hazard_type.lower() for h in all_hazards)
            w_spd = (weather.wind_speed or 0) if weather else 0
            t_val = (weather.temperature or 0) if weather else 25

            if warning_present:
                reason_codes.append("OFFICIAL_WARNING_FARMER_ALERT")
                reason_codes.append("FARMER_CROP_AND_DRAINAGE_PROTECTION")
                risk_summary = f"Official warning active: {active_warning.title}. Crop and field inundation hazard."
                if is_tamil:
                    headline = f"⚠️ [அதிகாரப்பூர்வ எச்சரிக்கை] {active_warning.title}"
                    advisory_text = (
                        f"அதிகாரப்பூர்வ IMD எச்சரிக்கை நிலவுகிறது: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "விவசாயிகளுக்கான ஆலோசனை: பாசனத்தை உடனடியாக நிறுத்தவும். உரங்கள் அல்லது பூச்சிக்கொல்லி தெளிப்பதை ஒத்திவைக்கவும். அறுவடை செய்த பயிர்களைப் பாதுகாப்பான இடங்களில் சேமிக்கவும்."
                    )
                    precautions = [
                        f"அதிகாரப்பூர்வ எச்சரிக்கை வழிகாட்டுதல்: {active_warning.title}",
                        "வயல்களில் பாசனம் செய்வதைத் தவிர்க்கவும்",
                        "உரங்கள் அல்லது பூச்சிக்கொல்லி தெளிப்பதை ஒத்திவைக்கவும்",
                        "அறுவடை செய்த பயிர்களைப் பாதுகாப்பான இடங்களில் சேமிக்கவும்"
                    ]
                elif is_hindi:
                    headline = f"⚠️ [आधिकारिक कृषि चेतावनी] {active_warning.title}"
                    advisory_text = (
                        f"आधिकारिक IMD चेतावनी सक्रिय है: {active_warning.title} ({active_warning.severity.value})। "
                        f"{active_warning.description}। "
                        "किसानों के लिए सलाह: सिंचाई तुरंत रोक दें। उर्वरक और कीटनाशक छिड़काव स्थगित करें। कटी हुई फसलों को सुरक्षित ढके हुए स्थान पर रखें।"
                    )
                    precautions = [
                        f"आधिकारिक चेतावनी निर्देश: {active_warning.title}",
                        "सिंचाई तुरंत रोक दें",
                        "उर्वरक और कीटनाशक छिड़काव स्थगित करें",
                        "कटी हुई फसलों को सुरक्षित ढके हुए स्थान पर रखें"
                    ]
                else:
                    headline = f"⚠️ [OFFICIAL IMD WARNING] {active_warning.title}"
                    advisory_text = (
                        f"OFFICIAL IMD WARNING ACTIVE: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "For farmers: Suspend all irrigation immediately. Postpone fertilizer and pesticide applications to prevent runoff. Clear field drainage channels and secure harvested produce."
                    )
                    precautions = [
                        f"Official Warning Protocol: {active_warning.title}",
                        "Suspend irrigation immediately",
                        "Postpone fertilizer and pesticide applications to prevent runoff",
                        "Clear field drainage channels and secure harvested produce under cover"
                    ]
            elif is_farm_rain:
                reason_codes.append("FARMER_CROP_AND_DRAINAGE_PROTECTION")
                risk_summary = "Precipitation expected; suspend irrigation to prevent field inundation and nutrient wash-off."
                if is_tamil:
                    headline = "விவசாய ஆலோசனை — பாசனத்தை நிறுத்தவும்"
                    advisory_text = "கனமழை / மழை எதிர்பார்க்கப்படுவதால் நீர் தேங்குவதைத் தடுக்க பாசனத்தை உடனடியாக நிறுத்தவும். உரங்கள் தெளிப்பதை ஒத்திவைக்கவும்."
                    precautions = [
                        "வயல்களில் பாசனம் செய்வதைத் தவிர்க்கவும்",
                        "உரங்கள் அல்லது பூச்சிக்கொல்லி தெளிப்பதை ஒத்திவைக்கவும்",
                        "அறுவடை செய்த பயிர்களைப் பாதுகாப்பான இடங்களில் சேமிக்கவும்"
                    ]
                elif is_hindi:
                    headline = "कृषि सलाह — सिंचाई स्थगित करें"
                    advisory_text = "भारी बारिश के कारण खेतों में जलभराव हो सकता है। सिंचाई तुरंत रोक दें और कीटनाशक छिड़काव स्थगित करें।"
                    precautions = [
                        "सिंचाई तुरंत रोक दें",
                        "उर्वरक और कीटनाशक छिड़काव स्थगित करें",
                        "कटी हुई फसलों को सुरक्षित ढके हुए स्थान पर रखें"
                    ]
                else:
                    headline = "Agricultural Advisory — Rain Ahead: Suspend Irrigation"
                    advisory_text = "Precipitation expected across agricultural fields. Suspend irrigation immediately to prevent root inundation. Postpone fertilizer and pesticide applications to prevent chemical wash-off and environmental runoff."
                    precautions = [
                        "Suspend irrigation immediately — natural precipitation sufficient",
                        "Postpone fertilizer and pesticide spraying until fields dry",
                        "Ensure field drainage channels are clear of debris",
                        "Secure harvested produce under waterproof tarpaulins"
                    ]
                if w_spd > 25.0:
                    advisory_text += f" Strong winds ({w_spd:.0f} km/h) also detected; secure tall crops against lodging."
                    precautions.append("Provide staking or earthing-up for tall crops against strong winds")
            elif w_spd > 25.0 or any("wind" in h.hazard_type.lower() for h in all_hazards):
                reason_codes.append("FARMER_WIND_SPRAY_DRIFT")
                risk_summary = "High wind speeds increasing spray drift hazard."
                headline = "Agricultural Advisory — High Winds: Postpone Spraying"
                advisory_text = f"Elevated wind speeds ({w_spd:.0f} km/h) detected. Postpone aerial and foliar spraying to prevent chemical drift loss. Provide staking for tall standing crops."
                precautions = [
                    "Postpone aerial and foliar spraying due to chemical drift hazard",
                    "Inspect tall crops and provide mechanical support/earthing-up"
                ]
            elif t_val > 35.0:
                reason_codes.append("FARMER_HEAT_STRESS_IRRIGATION")
                risk_summary = "Elevated temperatures increasing crop heat stress."
                headline = "Agricultural Advisory — Heat Stress: Regulate Irrigation"
                advisory_text = f"Elevated temperatures ({t_val:.0f}°C). Provide light, frequent irrigation during early morning or late evening to prevent crop moisture stress."
                precautions = [
                    "Schedule irrigation during early morning or late evening hours",
                    "Apply mulch to reduce root-zone moisture evaporation"
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
                    precautions = ["Proceed with standard irrigation schedule", "Routine field operations favorable"]

        # ---------------- TRAVELLER PERSONA ----------------
        elif resolved_persona == PersonaEnum.TRAVELLER:
            if warning_present:
                reason_codes.append("OFFICIAL_WARNING_TRAVELLER_ALERT")
                reason_codes.append("TRAVELLER_SEVERE_WEATHER_ALERT")
                risk_summary = f"Official warning active: {active_warning.title}. Intercity travel disruptions."
                if is_tamil:
                    headline = f"⚠️ [அதிகாரப்பூர்வ எச்சரிக்கை] {active_warning.title}"
                    advisory_text = (
                        f"அதிகாரப்பூர்வ IMD எச்சரிக்கை நிலவுகிறது: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "பயணிகளுக்கான ஆலோசனை: மோசமான வானிலை காரணமாக நீண்ட தூர பயணங்களைத் தள்ளிப்போடவும்."
                    )
                    precautions = [
                        f"அதிகாரப்பூர்வ எச்சரிக்கை வழிகாட்டுதல்: {active_warning.title}",
                        "விமானம் மற்றும் ரயில் அட்டவணை மாற்றங்களைச் சரிபார்க்கவும்",
                        "நெடுஞ்சாலை பயணங்களின் போது வேகத்தைக் குறைத்து ஓட்டவும்"
                    ]
                elif is_hindi:
                    headline = f"⚠️ [आधिकारिक यात्रा चेतावनी] {active_warning.title}"
                    advisory_text = (
                        f"आधिकारिक IMD चेतावनी सक्रिय है: {active_warning.title} ({active_warning.severity.value})। "
                        f"{active_warning.description}। "
                        "मौसम खराब होने के कारण लंबी दूरी की यात्रा में रुकावट आ सकती है।"
                    )
                    precautions = [
                        f"आधिकारिक चेतावनी निर्देश: {active_warning.title}",
                        "हाइवे और ट्रेन के ताजा शेड्यूल चेक करें",
                        "गाड़ी चलाते समय गति धीमी रखें"
                    ]
                else:
                    headline = f"⚠️ [OFFICIAL IMD WARNING] {active_warning.title}"
                    advisory_text = (
                        f"OFFICIAL IMD WARNING ACTIVE: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "For travelers: Severe weather conditions detected across transit corridors. Delay non-essential travel."
                    )
                    precautions = [
                        f"Official Warning Protocol: {active_warning.title}",
                        "Verify highway road status and train schedules before departure",
                        "Expect significant speed restrictions and transit delays"
                    ]
            elif risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
                reason_codes.append("TRAVELLER_SEVERE_WEATHER_ALERT")
                risk_summary = "Severe weather conditions posing risks to intercity transit."
                headline = "Travel Alert — Severe Weather Ahead"
                advisory_text = "Severe weather conditions detected across travel corridors. Significant transit delays anticipated."
                precautions = [
                    "Verify highway road status and train schedules before departure",
                    "Expect significant speed restrictions and transit delays",
                    "Avoid non-essential transit across flood-prone corridors"
                ]
            else:
                reason_codes.append("TRAVELLER_CLEAR_ITINERARY")
                risk_summary = "Clear weather with good transit visibility."
                headline = "Favorable Travel Conditions"
                advisory_text = "Favorable conditions for intercity and outdoor travel."
                precautions = ["Standard travel itinerary applies"]

        # ---------------- DISASTER RESPONSE PERSONA ----------------
        elif resolved_persona == PersonaEnum.DISASTER_RESPONSE:
            if warning_present:
                reason_codes.append("OFFICIAL_WARNING_DISASTER_ALERT")
                reason_codes.append("DISASTER_RESPONSE_STANDBY_MOBILIZATION")
                risk_summary = f"Official warning active: {active_warning.title} ({active_warning.severity.value}). Standby mobilization required."
                if is_tamil:
                    headline = f"⚠️ [அதிகாரப்பூர்வ எச்சரிக்கை] {active_warning.title}"
                    advisory_text = (
                        f"அதிகாரப்பூர்வ IMD எச்சரிக்கை நிலவுகிறது: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "பேரிடர் மேலாண்மை தயார்நிலை: உடனடி மீட்பு மற்றும் நிவாரண குழுக்கள் தயார்நிலையில் இருக்க வேண்டும்."
                    )
                    precautions = [
                        f"அதிகாரப்பூர்வ எச்சரிக்கை வழிகாட்டுதல்: {active_warning.title}",
                        "பாதிக்கப்படக்கூடிய தாழ்வான பகுதிகளைக் கண்காணிக்கவும்",
                        "நீர் இறைக்கும் இயந்திரங்கள் மற்றும் தற்காலிக முகாம்களைத் தயார் செய்யவும்",
                        "IMD மற்றும் மாநில அவசர கட்டுப்பாட்டு மைய அறிவிப்புகளைத் தொடர்ந்து கண்காணிக்கவும்"
                    ]
                elif is_hindi:
                    headline = f"⚠️ [आधिकारिक आपदा चेतावनी] {active_warning.title}"
                    advisory_text = (
                        f"आधिकारिक IMD चेतावनी सक्रिय है: {active_warning.title} ({active_warning.severity.value})। "
                        f"{active_warning.description}। "
                        "आपदा प्रबंधन सतर्कता: आपातकालीन दल स्टैंडबाय पर रहें और जल निकासी पंप तैयार रखें।"
                    )
                    precautions = [
                        f"आधिकारिक चेतावनी निर्देश: {active_warning.title}",
                        "निचले संवेदनशील क्षेत्रों की निगरानी करें",
                        "जल निकासी पंप और राहत सामग्री तैयार रखें",
                        "IMD रडार और आधिकारिक चेतावनी बुलेटिन ट्रैक करें"
                    ]
                else:
                    headline = f"⚠️ [OFFICIAL IMD WARNING] {active_warning.title}"
                    advisory_text = (
                        f"OFFICIAL IMD WARNING ACTIVE: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "For emergency teams: High-impact hazard criteria met. Pre-position emergency dewatering pumps, rescue teams, and relief assets."
                    )
                    precautions = [
                        f"Official Warning Protocol: {active_warning.title}",
                        "Activate standby response protocols for designated vulnerable sectors",
                        "Ensure emergency dewatering pumps and relief supplies are positioned",
                        "Continuously monitor real-time IMD radar feeds and official emergency bulletins"
                    ]
            elif risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
                reason_codes.append("DISASTER_RESPONSE_STANDBY_MOBILIZATION")
                risk_summary = "High-impact disaster hazard active or impending; emergency preparedness required."
                headline = "Disaster Response Alert — Standby Mobilization"
                advisory_text = "High-impact hazard criteria met. Pre-position emergency dewatering and rescue assets in designated sectors."
                precautions = [
                    "Activate standby response protocols for designated vulnerable sectors",
                    "Ensure emergency dewatering pumps and relief supplies are positioned",
                    "Continuously monitor real-time IMD radar feeds and official emergency bulletins"
                ]
            elif risk == RiskLevelEnum.MEDIUM:
                reason_codes.append("DISASTER_RESPONSE_HEIGHTENED_MONITORING")
                risk_summary = "Moderate weather hazards; heightened surveillance standard."
                headline = "Disaster Management — Heightened Monitoring"
                advisory_text = "Moderate risks detected. Maintain heightened surveillance across low-lying flood corridors and civic drain networks."
                precautions = [
                    "Inspect critical stormwater outfalls and pump stations",
                    "Maintain direct communication with civic emergency teams"
                ]
            else:
                reason_codes.append("DISASTER_RESPONSE_SITUATIONAL_MONITORING")
                risk_summary = "Baseline calm conditions; situational monitoring standard."
                headline = "Routine Situational Monitoring"
                advisory_text = "No active disaster hazards detected. Maintain routine background surveillance."
                precautions = [
                    "Standard situational monitoring standard",
                    "No emergency response mobilization required"
                ]

        # ---------------- GENERAL / GENERAL_USER PERSONA (DEFAULT) ----------------
        else:
            if warning_present:
                reason_codes.append("OFFICIAL_WARNING_GENERAL_ALERT")
                risk_summary = f"Official warning active: {active_warning.title} ({active_warning.severity.value})."
                if is_tamil:
                    headline = f"⚠️ [அதிகாரப்பூர்வ எச்சரிக்கை] {active_warning.title}"
                    advisory_text = (
                        f"அதிகாரப்பூர்வ IMD எச்சரிக்கை நிலவுகிறது: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "பொதுமக்கள் பாதுகாப்பு ஆலோசனை: அவசியமற்ற பயணங்களைத் தவிர்த்து பாதுகாப்புடன் இருக்கவும்."
                    )
                    precautions = [
                        f"அதிகாரப்பூர்வ எச்சரிக்கை வழிகாட்டுதல்: {active_warning.title}",
                        "மழை / புயலின் போது பாதுகாப்பான இடங்களில் இருக்கவும்",
                        "அரசு அறிவிப்புகளைத் தொடர்ந்து பின்பற்றவும்"
                    ]
                elif is_hindi:
                    headline = f"⚠️ [आधिकारिक चेतावनी] {active_warning.title}"
                    advisory_text = (
                        f"आधिकारिक IMD चेतावनी सक्रिय है: {active_warning.title} ({active_warning.severity.value})। "
                        f"{active_warning.description}। "
                        "सामान्य जनता के लिए सलाह: अनावश्यक यात्रा से बचें और सुरक्षित स्थानों पर रहें।"
                    )
                    precautions = [
                        f"आधिकारिक चेतावनी निर्देश: {active_warning.title}",
                        "तूफान के दौरान घर के अंदर रहें",
                        "स्थानीय प्रशासन के निर्देशों का पालन करें"
                    ]
                else:
                    headline = f"⚠️ [OFFICIAL IMD WARNING] {active_warning.title}"
                    advisory_text = (
                        f"OFFICIAL IMD WARNING ACTIVE: {active_warning.title} ({active_warning.severity.value}). "
                        f"{active_warning.description}. "
                        "Adverse weather conditions detected. Avoid non-essential travel and follow local authority advisories."
                    )
                    precautions = [
                        f"Official Warning Protocol: {active_warning.title}",
                        "Stay indoors during peak storm activity",
                        "Follow official government guidelines"
                    ]
            elif risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
                reason_codes.append("GENERAL_SEVERE_WEATHER_ALERT")
                risk_summary = "Severe weather conditions active; personal outdoor safety precautions required."
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
                headline = "Moderate Weather Conditions"
                advisory_text = "Variable weather conditions expected. Carry basic outdoor protection."
                precautions = [
                    "Carry an umbrella or rain cover",
                    "Plan outdoor activities around peak weather hours"
                ]
            else:
                reason_codes.append("GENERAL_NORMAL_WEATHER")
                risk_summary = "Conditions are pleasant and within comfortable climatological bounds."
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
            schedule_decision=schedule_decision,
            personal_decision=personal_decision_dict,
            language=target_language,
        )
