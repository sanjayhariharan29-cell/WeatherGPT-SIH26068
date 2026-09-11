"""Deterministic Personal Decision Engine for SkyZen Personal Weather AI.

Evaluates user goals and questions into actionable, structured decisions:
- College Commute
- General Travel
- Bike Travel
- Umbrella Decision
- Outdoor Activity
- Sports Activity
- Fishing / Marine Safety
- Clothing Advice
- General "Can I go?" Decisions

Strict Rules:
- Grounded solely in verified telemetry, IMD warnings, and reasoner hazards.
- NEVER guesses safety-critical information.
- Provides concise, direct recommendations in English, Tamil, and Hindi.
"""

from typing import Any, Dict, List, Optional
import re

from ai.models import (
    ForecastItem,
    HazardDetection,
    IntentEnum,
    LanguageEnum,
    NLUResult,
    OfficialAlert,
    RiskLevelEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.decision.models import (
    DecisionTypeEnum,
    DecisionVerdictEnum,
    PersonalDecisionResult,
    StructuredEvidence,
)


class PersonalDecisionEngine:
    """Deterministic evaluation engine converting verified weather evidence into direct personal decisions."""

    @classmethod
    def identify_decision_type(cls, nlu: Optional[NLUResult], message: str = "") -> Optional[DecisionTypeEnum]:
        """Identifies what specific decision the user is attempting to make."""
        clean = (message or (nlu.original_text if nlu else "")).lower().strip()
        intent_str = str(getattr(nlu.intent, "value", nlu.intent or "")).lower() if nlu else ""

        # 1. College Commute
        if intent_str == "college_commute" or any(k in clean for k in ["college", "school", "campus", "கல்லூரி", "பள்ளி", "कॉलेज", "स्कूल"]):
            if any(k in clean for k in ["go", "leave", "attend", "reach", "pogalama", "polama", "mudiyuma", "ja sakte", "போகலாமா", "போலாமா", "जा सकते"]):
                return DecisionTypeEnum.COLLEGE_COMMUTE

        # 2. Bike Travel
        if intent_str == "bike_travel" or any(k in clean for k in [
            "bike", "motorcycle", "scooter", "two-wheeler", "two wheeler", "ride", "பைக்", "டூவீலர்", "बाइक", "स्कूटर"
        ]):
            return DecisionTypeEnum.BIKE_TRAVEL

        # 3. Umbrella Decision & Wetness Inquiries
        if intent_str == "umbrella_decision" or any(k in clean for k in [
            "umbrella", "kudai", "குடை", "chhata", "छाता", "छतरी",
            "get wet", "will i get wet", "wet", "nananjiduvena", "nanaiyuma", "நனைய", "भीग", "bheeg"
        ]):
            return DecisionTypeEnum.UMBRELLA

        # 4. Sports Activity
        if intent_str == "sports_activity" or any(k in clean for k in [
            "cricket", "football", "match", "play", "game", "badminton", "tennis",
            "விளையாட", "கிரிக்கெட்", "क्रिकेट", "फुटबॉल", "खेल"
        ]):
            return DecisionTypeEnum.SPORTS

        # 5. Fishing / Marine Trip
        if intent_str in ("fishing_decision", "marine_safety") or any(k in clean for k in [
            "fishing", "fish", "marine", "sea", "ocean", "boat", "மீன்", "மீன்பிடி", "கடல்", "मछली", "समुद्र"
        ]):
            return DecisionTypeEnum.FISHING_MARINE

        # 6. Clothing Advice
        if intent_str == "clothing_advice" or any(k in clean for k in [
            "wear", "clothes", "jacket", "sweater", "raincoat", "warm clothes", "அணிய", "உடை", "पहनना", "कपड़े"
        ]):
            return DecisionTypeEnum.CLOTHING

        # 7. General Travel / Highway Outstation
        if intent_str == "travel_decision" or any(k in clean for k in [
            "travel", "trip", "highway", "drive to", "payanam", "பயணம்", "safar", "यात्रा"
        ]):
            return DecisionTypeEnum.GENERAL_TRAVEL

        # 8. Outdoor Activity ("Can I go outside?", "go out")
        if any(k in clean for k in [
            "go outside", "go out", "safe to go out", "bahar ja sakte", "வெளியே செல்லலாமா",
            "வெளிய போகலாமா", "can i go out", "outside"
        ]):
            return DecisionTypeEnum.OUTDOOR_ACTIVITY

        # 9. General "Can I go?" decisions
        if intent_str == "outdoor_activity" or any(k in clean for k in [
            "can i go", "should i go", "safe to go", "pogalama", "polama", "poga mudiyuma",
            "போகலாமா", "போலாமா", "செல்லலாமா", "ja sakte", "jaana chahiye", "जा सकते"
        ]):
            return DecisionTypeEnum.GENERAL_GO

        # Fallback to general travel if travel advisory
        if intent_str == "travel_advisory":
            return DecisionTypeEnum.GENERAL_TRAVEL

        return None

    @classmethod
    def evaluate(
        cls,
        nlu: Optional[NLUResult],
        weather: Optional[WeatherRecord],
        forecast: Optional[List[ForecastItem]],
        reasoning: WeatherReasoningResult,
        target_language: LanguageEnum = LanguageEnum.EN,
        message: str = "",
        schedule_decision: Optional[Dict[str, Any]] = None,
    ) -> PersonalDecisionResult:
        """Deterministically evaluates weather evidence into a structured personal decision."""
        msg = message or (nlu.original_text if nlu else "")
        dec_type = cls.identify_decision_type(nlu, msg) or DecisionTypeEnum.GENERAL_GO

        # Gather Verified Meteorological Evidence
        temp_c = getattr(weather, "temperature", None) if weather else None
        rain_prob = float(getattr(weather, "rain_probability", 0.0) or 0.0) if weather else 0.0
        rain_mm = float(getattr(weather, "rainfall_amount_mm", 0.0) or getattr(weather, "rain_amount", 0.0) or 0.0) if weather else 0.0
        wind_spd = float(getattr(weather, "wind_speed", 0.0) or 0.0) if weather else 0.0
        weather_cond = str(getattr(weather, "weather_condition", "Clear") or "Clear") if weather else "Unknown"

        fc_list = forecast or []
        fc_max_rain = max([float(fc.rain_probability or 0.0) for fc in fc_list], default=rain_prob)
        fc_max_wind = max([float(fc.wind_speed or 0.0) for fc in fc_list], default=wind_spd)
        fc_has_rain = any("rain" in str(getattr(fc, "condition", "")).lower() for fc in fc_list)

        is_rain_expected = rain_prob >= 35.0 or fc_max_rain >= 35.0 or fc_has_rain or any("rain" in h.hazard_type.lower() for h in reasoning.detected_hazards)

        warning_titles = [w.title for w in reasoning.active_warnings]
        has_warning = len(warning_titles) > 0
        primary_warning = reasoning.active_warnings[0] if has_warning else None
        hazard_names = [h.hazard_type for h in reasoning.detected_hazards]

        # Schedule transit probabilities
        dep_prob = None
        ret_prob = None
        dep_time = None
        ret_time = None
        if schedule_decision:
            dep_prob = schedule_decision.get("departure_prob")
            ret_prob = schedule_decision.get("return_prob")
            dep_time = schedule_decision.get("departure_time")
            ret_time = schedule_decision.get("return_time")

        reasons: List[str] = []
        if has_warning:
            reasons.append(f"Official IMD Warning active: {primary_warning.title} ({primary_warning.severity.value})")
        if is_rain_expected:
            reasons.append(f"Precipitation probability is {max(rain_prob, fc_max_rain):.0f}%")
        if wind_spd >= 35.0 or fc_max_wind >= 35.0:
            reasons.append(f"High wind speeds up to {max(wind_spd, fc_max_wind):.0f} km/h")
        if hazard_names:
            reasons.append(f"Active hazard signals: {', '.join(hazard_names[:2])}")

        evidence = StructuredEvidence(
            temperature_c=temp_c,
            rain_probability=max(rain_prob, fc_max_rain),
            rainfall_mm=rain_mm,
            wind_speed_kmh=max(wind_spd, fc_max_wind),
            weather_condition=weather_cond,
            is_rain_expected=is_rain_expected,
            active_warnings=warning_titles,
            hazards_detected=hazard_names,
            transit_departure_prob=dep_prob,
            transit_return_prob=ret_prob,
            transit_departure_time=dep_time,
            transit_return_time=ret_time,
            reasons=reasons,
        )

        effective_loc = reasoning.location if reasoning.location != "Unknown" else (getattr(nlu.entities, "location", None) if nlu and nlu.entities else "your area")
        time_window = "today"
        if nlu and nlu.entities:
            time_window = nlu.entities.time or nlu.entities.date or "today"

        # Determine Decision Rules per Type
        if dec_type == DecisionTypeEnum.COLLEGE_COMMUTE:
            return cls._evaluate_college_commute(evidence, reasoning, effective_loc, time_window, schedule_decision)
        elif dec_type == DecisionTypeEnum.BIKE_TRAVEL:
            return cls._evaluate_bike_travel(evidence, reasoning, effective_loc, time_window, schedule_decision)
        elif dec_type == DecisionTypeEnum.UMBRELLA:
            return cls._evaluate_umbrella(evidence, reasoning, effective_loc, time_window, schedule_decision)
        elif dec_type == DecisionTypeEnum.SPORTS:
            return cls._evaluate_sports(evidence, reasoning, effective_loc, time_window)
        elif dec_type == DecisionTypeEnum.FISHING_MARINE:
            return cls._evaluate_marine_fishing(evidence, reasoning, effective_loc, time_window)
        elif dec_type == DecisionTypeEnum.CLOTHING:
            return cls._evaluate_clothing(evidence, reasoning, effective_loc, time_window)
        elif dec_type == DecisionTypeEnum.GENERAL_TRAVEL:
            return cls._evaluate_general_travel(evidence, reasoning, effective_loc, time_window)
        elif dec_type == DecisionTypeEnum.OUTDOOR_ACTIVITY:
            return cls._evaluate_general_go(evidence, reasoning, effective_loc, time_window, dec_type=DecisionTypeEnum.OUTDOOR_ACTIVITY)
        else:
            # GENERAL_GO
            return cls._evaluate_general_go(evidence, reasoning, effective_loc, time_window, dec_type=DecisionTypeEnum.GENERAL_GO)

    # -------------------------------------------------------------------------
    # 1. COLLEGE COMMUTE
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_college_commute(
        cls,
        ev: StructuredEvidence,
        reasoning: WeatherReasoningResult,
        loc: str,
        time_win: str,
        sched: Optional[Dict[str, Any]] = None
    ) -> PersonalDecisionResult:
        has_warning = len(ev.active_warnings) > 0
        ret_rain = ev.transit_return_prob if ev.transit_return_prob is not None else ev.rain_probability

        if has_warning or reasoning.overall_risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
            verdict = DecisionVerdictEnum.CAUTION
            action = f"Check official college notices before leaving. Official IMD alert is active ({ev.active_warnings[0] if ev.active_warnings else 'Adverse Weather'}). Carry waterproof protection."
            primary = "Active official severe weather alert in effect"
            ans_en = f"You should check official college notices before departing {loc}. An active IMD warning is in effect. Avoid non-essential transit through waterlogged corridors, and carry waterproof rain gear."
            ans_ta = f"{loc} பகுதியில் அதிகாரப்பூர்வ IMD எச்சரிக்கை நிலவுவதால் கல்லூரி நிர்வாகத்தின் அறிவிப்புகளைச் சரிபார்க்கவும். நீர் தேங்கிய சாலைகளைத் தவிர்க்கவும், குடை அல்லது ரெயின்கோட் எடுத்துச் செல்லவும்."
            ans_hi = f"{loc} में आधिकारिक IMD चेतावनी सक्रिय होने के कारण कॉलेज निकलने से पहले आधिकारिक सूचना देखें। जलभराव वाले रास्तों से बचें और छाता या रेनकोट साथ रखें।"
            precautions = ["Check official institutional announcements", "Carry waterproof bag and raincoat", "Avoid flooded low-lying underpasses"]
        elif ret_rain >= 35.0 or ev.is_rain_expected:
            verdict = DecisionVerdictEnum.GO
            action = f"Yes, safe to attend college, but carry an umbrella or raincoat as rain is likely ({ret_rain:.0f}% chance)."
            primary = f"Precipitation expected during transit window ({ret_rain:.0f}% chance)"
            ans_en = f"Yes, you can go to college today in {loc}. However, rain is expected during your commute ({ret_rain:.0f}% chance), so carrying an umbrella or raincoat is strongly recommended."
            ans_ta = f"ஆம், இன்று {loc}ல் கல்லூரிக்கு செல்லலாம். ஆனால் உங்கள் பயண நேரத்தில் மழைக்கு {ret_rain:.0f}% வாய்ப்புள்ளதால், குடை அல்லது ரெயின்கோட் எடுத்துச் செல்வது அவசியமாகும்."
            ans_hi = f"हाँ, आज {loc} में कॉलेज जा सकते हैं। हालांकि आपकी यात्रा के दौरान बारिश की संभावना ({ret_rain:.0f}%) है, इसलिए छाता या रेनकोट साथ रखना आवश्यक है।"
            precautions = ["Carry an umbrella or raincoat", "Allow a few minutes extra travel time", "Keep electronics in waterproof covers"]
        else:
            verdict = DecisionVerdictEnum.GO
            action = f"Yes, conditions are clear and safe for your college commute in {loc}."
            primary = f"Clear and dry conditions ({ev.weather_condition}, {ev.rain_probability:.0f}% rain)"
            ans_en = f"Yes, you can go to college today in {loc}. Weather conditions are clear and dry with no disruption expected for your commute."
            ans_ta = f"ஆம், இன்று {loc}ல் கல்லூரிக்கு செல்லலாம். வானிலை தெளிவாகவும் சாதகமாகவும் உள்ளது; பயணத்திற்கு எவ்வித இடையூறும் இல்லை."
            ans_hi = f"हाँ, आज {loc} में कॉलेज जाने के लिए मौसम पूरी तरह अनुकूल और साफ है। यात्रा में किसी रुकावट की संभावना नहीं है।"
            precautions = ["Standard commute routine"]

        return PersonalDecisionResult(
            decision_type=DecisionTypeEnum.COLLEGE_COMMUTE,
            verdict=verdict,
            recommended_action=action,
            primary_factor=primary,
            risk_level=reasoning.overall_risk,
            confidence="HIGH" if reasoning.consistency_score >= 70 else "MEDIUM",
            location=loc,
            time_window=time_win,
            evidence=ev,
            precautions=precautions,
            concise_answer_en=ans_en,
            concise_answer_ta=ans_ta,
            concise_answer_hi=ans_hi,
        )

    # -------------------------------------------------------------------------
    # 2. BIKE TRAVEL
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_bike_travel(
        cls,
        ev: StructuredEvidence,
        reasoning: WeatherReasoningResult,
        loc: str,
        time_win: str,
        sched: Optional[Dict[str, Any]] = None
    ) -> PersonalDecisionResult:
        has_warning = len(ev.active_warnings) > 0
        has_storm = any(any(k in h for k in ("thunderstorm", "gale", "cyclone")) for h in ev.hazards_detected)
        wind_high = ev.wind_speed_kmh >= 35.0

        if has_warning or has_storm or (ev.is_rain_expected and ev.rain_probability >= 60.0) or wind_high:
            verdict = DecisionVerdictEnum.NOT_RECOMMENDED
            reason_str = "high winds and severe rain" if (wind_high and ev.is_rain_expected) else ("high crosswinds (>35 km/h)" if wind_high else "rain and slick road hazards")
            action = f"Avoid taking your two-wheeler in {loc}. Hazardous riding conditions expected ({reason_str}); opt for a four-wheeler or public transit."
            primary = f"Two-wheeler safety risk: {reason_str}"
            ans_en = f"Avoid taking your bike today in {loc}. {reason_str.capitalize()} create hazardous riding conditions and slippery roads. A closed vehicle or public transit is recommended."
            ans_ta = f"இன்று {loc}ல் பைக் எடுப்பதை தவிர்க்கவும். பலத்த காற்று மற்றும் மழை காரணமாக சாலைகளில் வழுக்கும் தன்மை ஏற்படும்; பொதுப்போக்குவரத்து அல்லது நான்கு சக்கர வாகனத்தை பயன்படுத்துவது சிறந்தது."
            ans_hi = f"आज {loc} में बाइक ले जाने से बचें। तेज हवाओं और बारिश के कारण सड़कें फिसलन भरी हो सकती हैं। सार्वजनिक परिवहन या चार पहिया वाहन का उपयोग करें।"
            precautions = ["Opt for bus, train, or four-wheeler", "Avoid open two-wheeler transit during heavy gusts", "Wear high-visibility raincoat if riding is unavoidable"]
        elif ev.is_rain_expected or ev.rain_probability >= 30.0:
            verdict = DecisionVerdictEnum.CAUTION
            action = f"You can ride your bike, but ride with extra caution in {loc}; carry a raincoat as wet road conditions are likely ({ev.rain_probability:.0f}% rain)."
            primary = f"Moderate rain chance ({ev.rain_probability:.0f}%) and wet roads"
            ans_en = f"You can take your bike in {loc}, but exercise caution. There is a {ev.rain_probability:.0f}% chance of rain. Carry a raincoat, wear a helmet, and brake gently on wet surfaces."
            ans_ta = f"{loc}ல் பைக் எடுத்துச் செல்லலாம், ஆனால் கவனமாக ஓட்டவும். {ev.rain_probability:.0f}% மழை வாய்ப்புள்ளது; ரெயின்கோட் எடுத்துச் செல்லவும், நிதானமாக இயக்கவும்."
            ans_hi = f"{loc} में बाइक ले जा सकते हैं, लेकिन सावधानी बरतें। {ev.rain_probability:.0f}% बारिश की संभावना है। रेनकोट साथ रखें और गति नियंत्रित रखें।"
            precautions = ["Wear helmet and carry raincoat", "Reduce speed on curves and wet roads", "Check tire traction before setting off"]
        else:
            verdict = DecisionVerdictEnum.RECOMMENDED
            action = f"Yes, safe to ride your bike today in {loc}. Winds and road conditions are clear."
            primary = f"Dry roads and favorable winds ({ev.wind_speed_kmh:.0f} km/h)"
            ans_en = f"Yes, you can safely take your bike today in {loc}. Road conditions are dry and winds are calm ({ev.wind_speed_kmh:.0f} km/h)."
            ans_ta = f"ஆம், இன்று {loc}ல் தாராளமாக பைக் எடுத்துச் செல்லலாம். வானிலை தெளிவாகவும் சாலைகள் உலர்ந்த நிலையிலும் உள்ளன."
            ans_hi = f"हाँ, आज {loc} में सुरक्षित रूप से बाइक ले जा सकते हैं। सड़कें सूखी हैं और मौसम पूरी तरह साफ है।"
            precautions = ["Standard helmet and safe riding guidelines"]

        return PersonalDecisionResult(
            decision_type=DecisionTypeEnum.BIKE_TRAVEL,
            verdict=verdict,
            recommended_action=action,
            primary_factor=primary,
            risk_level=reasoning.overall_risk,
            confidence="HIGH" if reasoning.consistency_score >= 70 else "MEDIUM",
            location=loc,
            time_window=time_win,
            evidence=ev,
            precautions=precautions,
            concise_answer_en=ans_en,
            concise_answer_ta=ans_ta,
            concise_answer_hi=ans_hi,
        )

    # -------------------------------------------------------------------------
    # 3. UMBRELLA DECISION
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_umbrella(
        cls,
        ev: StructuredEvidence,
        reasoning: WeatherReasoningResult,
        loc: str,
        time_win: str,
        sched: Optional[Dict[str, Any]] = None
    ) -> PersonalDecisionResult:
        prob = ev.transit_return_prob if (ev.transit_return_prob is not None and ev.transit_return_prob > 0) else ev.rain_probability

        if ev.is_rain_expected or prob >= 30.0 or len(ev.active_warnings) > 0:
            verdict = DecisionVerdictEnum.RECOMMENDED
            action = f"Yes, carrying an umbrella is recommended in {loc} ({prob:.0f}% rain chance)."
            primary = f"Precipitation expected ({prob:.0f}% probability)"
            ans_en = f"Yes, you should take an umbrella today in {loc}. There is a {prob:.0f}% chance of rain during your day."
            ans_ta = f"ஆம், இன்று {loc}ல் குடை எடுத்துச் செல்வது அவசியமாகும். {prob:.0f}% மழை பெய்ய வாய்ப்புள்ளது."
            ans_hi = f"हाँ, आज {loc} में छाता साथ रखना आवश्यक है। लगभग {prob:.0f}% बारिश की संभावना है।"
            precautions = ["Carry a compact umbrella or raincoat", "Ensure school/college bags are zipped in rain cover"]
        else:
            verdict = DecisionVerdictEnum.NOT_RECOMMENDED
            action = f"No, an umbrella is not required today in {loc} as dry conditions are forecast ({prob:.0f}% rain chance)."
            primary = f"Dry conditions forecast ({prob:.0f}% rain probability)"
            ans_en = f"No, you do not need an umbrella today in {loc}. The forecast indicates dry and clear conditions with only a {prob:.0f}% rain chance."
            ans_ta = f"இல்லை, இன்று {loc}ல் குடை தேவையில்லை. வானிலை உலர்ந்த நிலையிலும் தெளிவாகவும் இருக்கும் ({prob:.0f}% மழை வாய்ப்பு)."
            ans_hi = f"नहीं, आज {loc} में छाते की आवश्यकता नहीं है। मौसम साफ और सूखा रहने का अनुमान है (केवल {prob:.0f}% बारिश की संभावना)।"
            precautions = ["Standard outdoor routine"]

        return PersonalDecisionResult(
            decision_type=DecisionTypeEnum.UMBRELLA,
            verdict=verdict,
            recommended_action=action,
            primary_factor=primary,
            risk_level=reasoning.overall_risk,
            confidence="HIGH" if reasoning.consistency_score >= 70 else "MEDIUM",
            location=loc,
            time_window=time_win,
            evidence=ev,
            precautions=precautions,
            concise_answer_en=ans_en,
            concise_answer_ta=ans_ta,
            concise_answer_hi=ans_hi,
        )

    # -------------------------------------------------------------------------
    # 4. SPORTS ACTIVITY
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_sports(
        cls,
        ev: StructuredEvidence,
        reasoning: WeatherReasoningResult,
        loc: str,
        time_win: str
    ) -> PersonalDecisionResult:
        has_warning = len(ev.active_warnings) > 0
        has_storm = any("thunderstorm" in h for h in ev.hazards_detected)

        if has_warning or has_storm or (ev.is_rain_expected and ev.rain_probability >= 40.0):
            verdict = DecisionVerdictEnum.NO_GO
            action = f"Outdoor sports are not recommended in {loc} due to expected rain ({ev.rain_probability:.0f}%) and wet outfield conditions."
            primary = f"Wet ground and precipitation hazard ({ev.rain_probability:.0f}% rain chance)"
            ans_en = f"Outdoor sports are not recommended this {time_win} in {loc}. Rain ({ev.rain_probability:.0f}% chance) and damp outfield conditions will disrupt play and increase injury risk."
            ans_ta = f"இன்று {time_win} {loc}ல் வெளிப்புற விளையாட்டுகளைத் தவிர்க்கவும். மழை ({ev.rain_probability:.0f}%) மற்றும் ஈரமான தரை காரணமாக விளையாட்டு பாதிக்கப்படலாம்."
            ans_hi = f"आज {time_win} {loc} में आउटडोर खेल खेलने की सलाह नहीं दी जाती। बारिश ({ev.rain_probability:.0f}%) और गीले मैदान के कारण खेल में रुकावट आ सकती है।"
            precautions = ["Postpone match to dry window", "Opt for indoor training or gym workouts"]
        elif ev.temperature_c and ev.temperature_c >= 38.0:
            verdict = DecisionVerdictEnum.CAUTION
            action = f"Exercise caution playing sports in {loc}; high temperature ({ev.temperature_c:.1f}°C). Stay well hydrated."
            primary = f"High thermal stress ({ev.temperature_c:.1f}°C)"
            ans_en = f"You can play, but take heat precautions in {loc}. Temperatures reach {ev.temperature_c:.1f}°C. Schedule matches during early morning or late evening and hydrate frequently."
            ans_ta = f"{loc}ல் விளையாடலாம், ஆனால் அதிக வெப்பநிலை ({ev.temperature_c:.1f}°C) உள்ளதால் போதுமான தண்ணீர் குடிக்கவும்; காலை அல்லது மாலை வேளையில் விளையாடவும்."
            ans_hi = f"{loc} में खेल सकते हैं, लेकिन उच्च तापमान ({ev.temperature_c:.1f}°C) को देखते हुए खूब पानी पिएं और सुबह या शाम को ही खेलें।"
            precautions = ["Frequent hydration breaks", "Avoid peak afternoon sun (12 PM - 3 PM)"]
        else:
            verdict = DecisionVerdictEnum.GO
            action = f"Yes, great conditions to play sports in {loc}! Pitch and weather are dry and stable."
            primary = f"Pleasant conditions ({ev.weather_condition}, {ev.rain_probability:.0f}% rain)"
            ans_en = f"Yes, conditions are great to play cricket and outdoor sports this {time_win} in {loc}! The weather is clear and outfield conditions are dry."
            ans_ta = f"ஆம், இன்று {time_win} {loc}ல் தாராளமாக கிரிக்கெட் உள்ளிட்ட விளையாட்டுகளை விளையாடலாம்! வானிலை சாதகமாகவும் தரை உலர்ந்த நிலையிலும் உள்ளது."
            ans_hi = f"हाँ, आज {time_win} {loc} में क्रिकेट और अन्य खेल खेलने के लिए मौसम बहुत बढ़िया है! मैदान सूखा और मौसम साफ है।"
            precautions = ["Carry water bottle", "Standard sports warm-up"]

        return PersonalDecisionResult(
            decision_type=DecisionTypeEnum.SPORTS,
            verdict=verdict,
            recommended_action=action,
            primary_factor=primary,
            risk_level=reasoning.overall_risk,
            confidence="HIGH" if reasoning.consistency_score >= 70 else "MEDIUM",
            location=loc,
            time_window=time_win,
            evidence=ev,
            precautions=precautions,
            concise_answer_en=ans_en,
            concise_answer_ta=ans_ta,
            concise_answer_hi=ans_hi,
        )

    # -------------------------------------------------------------------------
    # 5. FISHING & MARINE SAFETY
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_marine_fishing(
        cls,
        ev: StructuredEvidence,
        reasoning: WeatherReasoningResult,
        loc: str,
        time_win: str
    ) -> PersonalDecisionResult:
        has_warning = len(ev.active_warnings) > 0
        is_squally = ev.wind_speed_kmh >= 45.0 or any("cyclone" in h or "wind" in h for h in ev.hazards_detected)

        if has_warning or is_squally:
            verdict = DecisionVerdictEnum.NO_GO
            action = f"Fishermen are strictly advised not to venture into the sea off {loc}. Squally winds ({ev.wind_speed_kmh:.0f} km/h) and rough sea conditions."
            primary = f"Rough sea warning and squally winds ({ev.wind_speed_kmh:.0f} km/h)"
            ans_en = f"Fishermen are strictly advised not to venture into the sea off {loc} {time_win}. Severe squally weather and rough sea conditions are active with wind gusts up to {ev.wind_speed_kmh:.0f} km/h."
            ans_ta = f"{loc} கடல் பகுதியில் பலத்த சூறாவளிக் காற்று ({ev.wind_speed_kmh:.0f} கி.மீ/மணி) மற்றும் கடல் சீற்றம் நிலவுவதால் மீனவர்கள் கடலுக்குச் செல்ல வேண்டாம் என எச்சரிக்கப்படுகிறார்கள்."
            ans_hi = f"{loc} के तटीय क्षेत्रों में {ev.wind_speed_kmh:.0f} किमी/घंटा की तेज हवाओं और समुद्र में अशांत स्थिति के कारण मछुआरों को समुद्र में न जाने की सख्त सलाह दी जाती है।"
            precautions = ["Heed IMD and INCOIS coastal advisories", "Secure boats and fishing gear at harbor", "Monitor port danger signals"]
        elif ev.wind_speed_kmh >= 30.0 or ev.is_rain_expected:
            verdict = DecisionVerdictEnum.CAUTION
            action = f"Exercise caution in coastal waters off {loc}; moderate wave action and winds ({ev.wind_speed_kmh:.0f} km/h)."
            primary = f"Moderate coastal wind ({ev.wind_speed_kmh:.0f} km/h)"
            ans_en = f"Fishermen should exercise caution off {loc}. Winds are moderate around {ev.wind_speed_kmh:.0f} km/h with choppy waves. Keep communication sets active."
            ans_ta = f"{loc} கடலில் மிதமான காற்று ({ev.wind_speed_kmh:.0f} கி.மீ/மணி) வீசுவதால் கவனத்துடன் செயல்படவும். தகவல் தொடர்பு கருவிகளை தயார் நிலையில் வைக்கவும்."
            ans_hi = f"{loc} के समुद्र में मध्यम हवाएं ({ev.wind_speed_kmh:.0f} किमी/घंटा) चल रही हैं। गहरे समुद्र में जाने से पहले सतर्कता बरतें और संचार उपकरण चालू रखें।"
            precautions = ["Keep VHF radio and life jackets ready", "Monitor real-time INCOIS wave forecast"]
        else:
            verdict = DecisionVerdictEnum.GO
            action = f"Sea conditions are calm and favorable for fishing off {loc}."
            primary = f"Calm sea and mild winds ({ev.wind_speed_kmh:.0f} km/h)"
            ans_en = f"Yes, sea conditions off {loc} are calm and favorable for fishing {time_win}. Winds are mild at {ev.wind_speed_kmh:.0f} km/h."
            ans_ta = f"ஆம், {loc} கடல் பகுதியில் வானிலை சாதகமாகவும் அலைகள் இயல்பான நிலையிலும் உள்ளன. மீன்பிடிக்க செல்லலாம்."
            ans_hi = f"हाँ, {loc} में समुद्र शांत है और मौसम मछली पकड़ने के लिए पूरी तरह अनुकूल है। हवाएं सामान्य हैं।"
            precautions = ["Standard maritime safety protocol"]

        return PersonalDecisionResult(
            decision_type=DecisionTypeEnum.FISHING_MARINE,
            verdict=verdict,
            recommended_action=action,
            primary_factor=primary,
            risk_level=reasoning.overall_risk,
            confidence="HIGH" if reasoning.consistency_score >= 70 else "MEDIUM",
            location=loc,
            time_window=time_win,
            evidence=ev,
            precautions=precautions,
            concise_answer_en=ans_en,
            concise_answer_ta=ans_ta,
            concise_answer_hi=ans_hi,
        )

    # -------------------------------------------------------------------------
    # 6. CLOTHING ADVICE
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_clothing(
        cls,
        ev: StructuredEvidence,
        reasoning: WeatherReasoningResult,
        loc: str,
        time_win: str
    ) -> PersonalDecisionResult:
        temp = ev.temperature_c if ev.temperature_c is not None else 28.0

        if temp <= 18.0:
            verdict = DecisionVerdictEnum.RECOMMENDED
            action = f"Wear warm layers or a light jacket in {loc} as temperatures are cool ({temp:.1f}°C)."
            primary = f"Cool temperatures ({temp:.1f}°C)"
            ans_en = f"Wear warm clothing or a light jacket today in {loc}. The temperature is currently cool at {temp:.1f}°C."
            ans_ta = f"{loc}ல் குளிர்ச்சியான வானிலை நிலவுவதால் ({temp:.1f}°C), லேசான ஸ்வெட்டர் அல்லது ஜாகெட் அணிவது நல்லது."
            ans_hi = f"{loc} में तापमान कम ({temp:.1f}°C) होने के कारण हल्के गर्म कपड़े या जैकेट पहनना बेहतर रहेगा।"
            precautions = ["Carry a light sweater or jacket for morning/evening"]
        elif temp >= 34.0:
            verdict = DecisionVerdictEnum.RECOMMENDED
            action = f"Wear light, breathable cotton clothing and sunglasses in {loc} due to high heat ({temp:.1f}°C)."
            primary = f"High heat ({temp:.1f}°C)"
            ans_en = f"Wear light, loose-fitting cotton clothing in {loc}. It is warm at {temp:.1f}°C, so remember sun protection and hydration."
            ans_ta = f"{loc}ல் வெயில் அதிகமாக இருப்பதால் ({temp:.1f}°C), மெல்லிய பருத்தி உடைகளை அணிவது வசதியாக இருக்கும்."
            ans_hi = f"{loc} में गर्मी ({temp:.1f}°C) को देखते हुए हल्के सूती कपड़े पहनें और धूप से बचाव रखें।"
            precautions = ["Wear light-colored cotton fabrics", "Carry sunglasses or a cap"]
        elif ev.is_rain_expected:
            verdict = DecisionVerdictEnum.RECOMMENDED
            action = f"Wear water-resistant footwear and carry a raincoat or umbrella in {loc}."
            primary = f"Wet weather expected ({ev.rain_probability:.0f}% rain chance)"
            ans_en = f"Wear water-resistant footwear and carry rain gear in {loc}. Rain is expected ({ev.rain_probability:.0f}% chance)."
            ans_ta = f"{loc}ல் மழை வாய்ப்புள்ளதால், மழைக்கால காலணிகள் மற்றும் ரெயின்கோட் அல்லது குடையுடன் செல்லவும்."
            ans_hi = f"{loc} में बारिश की संभावना को देखते हुए वाटरप्रूफ जूते पहनें और रेनकोट या छाता साथ रखें।"
            precautions = ["Avoid canvas shoes on wet days", "Keep rain jacket handy"]
        else:
            verdict = DecisionVerdictEnum.RECOMMENDED
            action = f"Standard comfortable casual wear is suitable for {loc} ({temp:.1f}°C)."
            primary = f"Pleasant temperature ({temp:.1f}°C)"
            ans_en = f"Standard comfortable casual wear is completely suitable for {loc} today. The temperature is a comfortable {temp:.1f}°C."
            ans_ta = f"{loc}ல் வானிலை சீராக உள்ளதால் ({temp:.1f}°C), வழக்கமான வசதியான உடைகள் போதுமானது."
            ans_hi = f"{loc} में मौसम सुखद ({temp:.1f}°C) है, सामान्य आरामदायक कपड़े पहनना उपयुक्त है।"
            precautions = ["Standard attire"]

        return PersonalDecisionResult(
            decision_type=DecisionTypeEnum.CLOTHING,
            verdict=verdict,
            recommended_action=action,
            primary_factor=primary,
            risk_level=reasoning.overall_risk,
            confidence="HIGH" if reasoning.consistency_score >= 70 else "MEDIUM",
            location=loc,
            time_window=time_win,
            evidence=ev,
            precautions=precautions,
            concise_answer_en=ans_en,
            concise_answer_ta=ans_ta,
            concise_answer_hi=ans_hi,
        )

    # -------------------------------------------------------------------------
    # 7. GENERAL TRAVEL
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_general_travel(
        cls,
        ev: StructuredEvidence,
        reasoning: WeatherReasoningResult,
        loc: str,
        time_win: str
    ) -> PersonalDecisionResult:
        has_warning = len(ev.active_warnings) > 0

        if has_warning or reasoning.overall_risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
            verdict = DecisionVerdictEnum.NO_GO
            action = f"Non-essential highway travel is not recommended in {loc} due to an active IMD alert ({ev.active_warnings[0] if ev.active_warnings else 'Hazard'})."
            primary = "Severe weather travel advisory active"
            ans_en = f"Non-essential travel is not recommended in {loc} {time_win}. An official IMD weather alert is active. Hazardous highway transit and road waterlogging may occur."
            ans_ta = f"அதிகாரப்பூர்வ IMD எச்சரிக்கை நிலவுவதால் {loc} பகுதியில் அத்தியாவசியமற்ற நீண்ட தூர பயணங்களைத் தவிர்க்கவும்."
            ans_hi = f"आधिकारिक IMD चेतावनी के कारण {loc} में अनावश्यक यात्रा से बचें। मार्गों पर जलभराव और बाधा की आशंका है।"
            precautions = ["Postpone non-essential highway journeys", "Check state highway traffic updates"]
        elif ev.is_rain_expected or ev.rain_probability >= 40.0:
            verdict = DecisionVerdictEnum.CAUTION
            action = f"Travel with caution in {loc}; rain expected ({ev.rain_probability:.0f}% chance). Allow extra travel time."
            primary = f"Wet highway conditions and transit delay risk ({ev.rain_probability:.0f}% rain)"
            ans_en = f"You can travel, but proceed with caution in {loc}. Rain ({ev.rain_probability:.0f}% chance) may cause minor transit delays and slick highway conditions."
            ans_ta = f"{loc}ல் பயணம் மேற்கொள்ளலாம், ஆனால் எச்சரிக்கையுடன் செல்லவும். மழை காரணமாக போக்குவரத்து காலதாமதம் ஏற்படலாம் (20-30 நிமிடம் கூடுதல் நேரம் ஒதுக்கவும்)."
            ans_hi = f"{loc} में यात्रा कर सकते हैं, लेकिन सतर्कता बरतें। बारिश के कारण यात्रा में थोड़ी देरी हो सकती है।"
            precautions = ["Allow 20-30 minutes extra travel time", "Drive with headlights on low beam during downpours"]
        else:
            verdict = DecisionVerdictEnum.GO
            action = f"Yes, conditions are favorable and safe for travel in {loc}."
            primary = f"Favorable travel conditions ({ev.weather_condition})"
            ans_en = f"Yes, conditions are safe and favorable for travel in {loc} {time_win}. Highways are dry and visibility is good."
            ans_ta = f"ஆம், {loc}ல் பயணம் செய்ய வானிலை சாதகமாகவும் பாதுகாப்பாகவும் உள்ளது."
            ans_hi = f"हाँ, {loc} में यात्रा करने के लिए मौसम पूरी तरह सुरक्षित और अनुकूल है।"
            precautions = ["Standard safe driving practices"]

        return PersonalDecisionResult(
            decision_type=DecisionTypeEnum.GENERAL_TRAVEL,
            verdict=verdict,
            recommended_action=action,
            primary_factor=primary,
            risk_level=reasoning.overall_risk,
            confidence="HIGH" if reasoning.consistency_score >= 70 else "MEDIUM",
            location=loc,
            time_window=time_win,
            evidence=ev,
            precautions=precautions,
            concise_answer_en=ans_en,
            concise_answer_ta=ans_ta,
            concise_answer_hi=ans_hi,
        )

    # -------------------------------------------------------------------------
    # 8. OUTDOOR ACTIVITY & GENERAL "CAN I GO?"
    # -------------------------------------------------------------------------
    @classmethod
    def _evaluate_general_go(
        cls,
        ev: StructuredEvidence,
        reasoning: WeatherReasoningResult,
        loc: str,
        time_win: str,
        dec_type: DecisionTypeEnum = DecisionTypeEnum.GENERAL_GO
    ) -> PersonalDecisionResult:
        has_warning = len(ev.active_warnings) > 0

        if has_warning or reasoning.overall_risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
            verdict = DecisionVerdictEnum.NO_GO
            action = f"Going outside is not advisable right now in {loc} due to an active weather alert ({ev.active_warnings[0] if ev.active_warnings else 'Severe Weather'})."
            primary = "Active weather alert in effect"
            ans_en = f"It is not advisable to go outside in {loc} {time_win}. Severe weather conditions and an official alert are active; staying indoors is recommended."
            ans_ta = f"கடுமையான வானிலை நிலவுவதால் இப்போது {loc}ல் வெளியே செல்வதை தவிர்க்கவும்; வீட்டிற்குள் பாதுகாப்பாக இருப்பது நல்லது."
            ans_hi = f"गंभीर मौसम की स्थिति को देखते हुए अभी {loc} में बाहर जाने से बचें और सुरक्षित स्थान पर रहें।"
            precautions = ["Stay indoors during intense weather", "Keep emergency supplies charged"]
        elif ev.is_rain_expected or ev.rain_probability >= 35.0:
            verdict = DecisionVerdictEnum.CAUTION
            action = f"You can go outside in {loc}, but carry an umbrella as rain is likely ({ev.rain_probability:.0f}% chance)."
            primary = f"Precipitation expected ({ev.rain_probability:.0f}% chance)"
            ans_en = f"You can go outside in {loc}, but carry an umbrella or raincoat as there is a {ev.rain_probability:.0f}% chance of rain."
            ans_ta = f"{loc}ல் வெளியே செல்லலாம், ஆனால் குடை எடுத்துச் செல்வது நல்லது ({ev.rain_probability:.0f}% மழை வாய்ப்பு)."
            ans_hi = f"{loc} में बाहर जा सकते हैं, लेकिन छाता साथ रखना बेहतर होगा ({ev.rain_probability:.0f}% बारिश की संभावना)।"
            precautions = ["Carry an umbrella or rain jacket"]
        else:
            verdict = DecisionVerdictEnum.GO
            action = f"Yes, you can comfortably go outside in {loc}. Weather is pleasant and stable."
            primary = f"Pleasant conditions ({ev.weather_condition}, {ev.rain_probability:.0f}% rain)"
            ans_en = f"Yes, you can comfortably go outside in {loc} {time_win}. The weather is clear and pleasant."
            ans_ta = f"ஆம், {loc}ல் தாராளமாக வெளியே செல்லலாம். வானிலை தெளிவாகவும் சாதகமாகவும் உள்ளது."
            ans_hi = f"हाँ, आज {loc} में बाहर जाने के लिए मौसम पूरी तरह अनुकूल और सुहावना है।"
            precautions = ["Standard outdoor precautions"]

        return PersonalDecisionResult(
            decision_type=dec_type,
            verdict=verdict,
            recommended_action=action,
            primary_factor=primary,
            risk_level=reasoning.overall_risk,
            confidence="HIGH" if reasoning.consistency_score >= 70 else "MEDIUM",
            location=loc,
            time_window=time_win,
            evidence=ev,
            precautions=precautions,
            concise_answer_en=ans_en,
            concise_answer_ta=ans_ta,
            concise_answer_hi=ans_hi,
        )


def build_why_this_answer(
    reasoning: WeatherReasoningResult,
    weather: Optional[WeatherRecord] = None,
    forecast: Optional[List[ForecastItem]] = None,
    advisory: Optional[DecisionAdvisory] = None,
    personal_decision: Optional[Dict[str, Any]] = None,
    language: Optional[LanguageEnum] = None,
) -> Dict[str, Any]:
    """Builds structured 'Why this answer?' detail path for evidence, freshness, and sources.

    Ensures complete explainability and auditing without cluttering the
    primary conversational personal assistant response.
    """
    conf_lvl = getattr(reasoning, "confidence_level", None)
    conf_lvl_str = conf_lvl.value if hasattr(conf_lvl, "value") else (str(conf_lvl) if conf_lvl else "HIGH")

    primary_factors: List[str] = []

    # 1. Official warning factor
    if reasoning.active_warnings:
        warn_titles = [getattr(w, "title", "Alert") for w in reasoning.active_warnings]
        primary_factors.append(f"Official IMD Warning: {', '.join(warn_titles[:2])}")

    # 2. Personal decision primary factor
    if personal_decision and personal_decision.get("primary_factor"):
        primary_factors.append(personal_decision["primary_factor"])
    elif personal_decision and personal_decision.get("recommended_action"):
        primary_factors.append(personal_decision["recommended_action"])

    # 3. Weather / rain factors
    rain_prob = float(getattr(weather, "rain_probability", 0.0) or 0.0) if weather else 0.0
    if weather and weather.temperature is not None:
        primary_factors.append(
            f"Current temperature {weather.temperature:.0f}°C with {rain_prob:.0f}% rain probability ({weather.weather_condition or 'Clear'})"
        )
    elif rain_prob > 0:
        primary_factors.append(f"Rain probability {rain_prob:.0f}%")

    # 4. Source agreement factor
    agreement_val = reasoning.source_agreement.value if hasattr(reasoning.source_agreement, "value") else str(reasoning.source_agreement)
    actual_sources = reasoning.sources_used or ([weather.source] if (weather and getattr(weather, "source", None)) else ["Weather Telemetry"])
    sources_str = ", ".join(actual_sources)
    if agreement_val in ("high", "consistent"):
        primary_factors.append(f"High multi-source consensus across {sources_str}")
    elif agreement_val == "low":
        primary_factors.append("Source divergence detected; conservative safety margin applied")

    # Evidence bundle
    ev_dict: Dict[str, Any] = {
        "temperature_c": getattr(weather, "temperature", None) if weather else None,
        "rain_probability": rain_prob,
        "weather_condition": getattr(weather, "weather_condition", "Clear") if weather else "Clear",
        "wind_speed_kmh": getattr(weather, "wind_speed", None) if weather else None,
        "active_warnings": [getattr(w, "title", "Alert") for w in reasoning.active_warnings],
        "hazards": [getattr(h, "hazard_type", "") for h in reasoning.detected_hazards],
    }

    if personal_decision and "evidence" in personal_decision:
        p_ev = personal_decision["evidence"]
        if isinstance(p_ev, dict):
            for k in ["transit_departure_prob", "transit_return_prob", "transit_departure_time", "transit_return_time"]:
                if k in p_ev:
                    ev_dict[k] = p_ev[k]

    # Summary sentence
    if personal_decision and personal_decision.get("primary_factor"):
        summary = f"Recommendation based on {personal_decision['primary_factor'].lower()} and verified {sources_str} observations."
    elif reasoning.active_warnings:
        summary = f"Recommendation directly driven by active official IMD warning ({reasoning.active_warnings[0].title})."
    else:
        summary = f"Recommendation deterministically computed from verified {sources_str} weather observations and multi-source consensus."

    return {
        "summary": summary,
        "verdict": personal_decision.get("verdict") if personal_decision else ("CAUTION" if reasoning.active_warnings else "GO"),
        "decision_type": personal_decision.get("decision_type") if personal_decision else "weather_guidance",
        "primary_factors": primary_factors,
        "evidence": ev_dict,
        "sources": actual_sources,
        "data_freshness": reasoning.freshness.value if hasattr(reasoning.freshness, "value") else str(reasoning.freshness),
        "data_age_minutes": reasoning.data_age_minutes,
        "consistency_score": reasoning.consistency_score,
        "confidence_level": conf_lvl_str,
        "precautions": personal_decision.get("precautions", []) if personal_decision else (advisory.key_precautions if advisory else []),
        "language": language.value if hasattr(language, "value") else str(language or "en"),
    }

