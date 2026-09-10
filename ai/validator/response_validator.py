"""Response Validation and Anti-Hallucination Safety Gate for WeatherGPT.

Ensures LLM/generated outputs are strictly grounded in retrieved meteorological facts,
never violate official warning mandates per docs/09_AI_Design.md:553, and preserve
all data quality, hazard, temporal, location, source, and advisory invariants.
"""

import re
from typing import Any, List, Optional, Set
from ai.models import (
    AdvisoryPriorityEnum,
    DecisionAdvisory,
    ForecastItem,
    LanguageEnum,
    NLUResult,
    RiskLevelEnum,
    SourceAgreementEnum,
    FreshnessStatusEnum,
    TimeContextEnum,
    ValidationCategoryEnum,
    ValidationResult,
    ValidationStatusEnum,
    WeatherReasoningResult,
    WeatherRecord,
)


class ResponseValidator:
    """Rigorous final AI safety gate and anti-hallucination engine for WeatherGPT.

    Evaluates generated response text against structured ground-truth data:
    - Live & forecast telemetry (temperatures, rainfall, probability, wind speed)
    - Official IMD warnings (no omission, contradiction, or downgrade)
    - Calibrated hazards & severity thresholds
    - Temporal scopes (now vs today vs tomorrow)
    - Location attribution & whitelisted sources
    - Uncertainty preservation (source conflict, stale data, missing metrics)
    - Action guidance integrity (preserving Phase 7 DecisionAdvisory)
    - Multilingual scripts & unit validity
    """

    @classmethod
    def validate_response(
        cls,
        response_text: str,
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None,
        advisory: Optional[DecisionAdvisory] = None,
        nlu: Optional[NLUResult] = None,
        target_language: Optional[LanguageEnum] = None,
        grounded_context: Optional[Any] = None,
        historical_weather: Optional[Any] = None,
    ) -> ValidationResult:
        """Performs comprehensive grounding and safety checks on generated response text."""
        issues: List[str] = []
        violations: List[str] = []
        warnings: List[str] = []
        verified_claims: List[str] = []
        violation_categories: List[str] = []
        checked_fields: List[str] = [
            "official_warnings",
            "hazards",
            "numbers",
            "units",
            "temporal",
            "location",
            "source",
            "uncertainty",
            "missing_data",
            "advisory",
            "language",
        ]

        # ---------------------------------------------------------
        # 0. Empty / Malformed Output Check
        # ---------------------------------------------------------
        if not response_text or len(response_text.strip()) < 5:
            msg = "Empty or malformed generated response."
            issues.append(msg)
            violations.append(msg)
            violation_categories.append(ValidationCategoryEnum.FABRICATED_DATA.value)
            return ValidationResult(
                is_valid=False,
                hallucination_detected=True,
                warning_consistency_passed=False,
                issues=issues,
                verified_claims=[],
                status=ValidationStatusEnum.FALLBACK,
                violations=violations,
                warnings=warnings,
                checked_fields=checked_fields,
                fallback_required=True,
                violation_categories=violation_categories,
            )

        lower_text = response_text.lower()

        # ---------------------------------------------------------
        # 1. Official Warning Integrity & Protection (Highest Priority)
        # ---------------------------------------------------------
        if reasoning.active_warnings:
            active_alert = reasoning.active_warnings[0]

            # 1a. Contradiction Check
            contradictory_phrases = [
                "no warning", "no warnings", "no active warning", "no official warning",
                "completely safe", "no danger", "no precautions needed", "no precautions necessary",
                "weather is safe", "safe weather", "weather should be mostly safe",
                "warning has been cancelled", "warning is cancelled", "alert is false",
                "ignore the warning", "ignore all warnings", "all clear",
                # Tamil
                "எச்சரிக்கை இல்லை", "ஆபத்து இல்லை", "முற்றிலும் பாதுகாப்பானது",
                "எச்சரிக்கையை புறக்கணிக்கவும்", "பயப்பட தேவையில்லை", "பாதுகாப்பாக உள்ளது",
                "பயமில்லை", "எச்சரிக்கை ரத்து",
                # Hindi
                "कोई चेतावनी नहीं", "कोई खतरा नहीं", "बिल्कुल सुरक्षित", "चेतावनी रद्द",
                "चेतावनी को नजरअंदाज करें", "मौसम पूरी तरह सुरक्षित है", "सब ठीक है",
                "सुरक्षित मौसम", "घबराने की जरूरत नहीं"
            ]
            if any(phrase in lower_text for phrase in contradictory_phrases):
                msg = f"Warning Contradiction: Active alert '{active_alert.title}' exists, but response claims conditions are safe or warning is absent/cancelled."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.WARNING_CONTRADICTION.value)

            # 1b. Omission Check
            warning_mentions = [
                "warning", "alert", "caution", "danger", "precaution", "emergency", "cyclone",
                "heavy rain", "flood", "high sea", "storm",
                # Tamil
                "எச்சரிக்கை", "கவனம்", "பாதுகாப்பு", "புயல்", "அலர்ட்", "மழை", "வெள்ளம்",
                # Hindi
                "चेतावनी", "अलर्ट", "सावधानी", "खतरा", "तूफान", "बाढ़", "बारिश"
            ]
            # Also allow alert title tokens
            title_tokens = [t.lower() for t in re.findall(r"\w+", active_alert.title) if len(t) > 3]
            acknowledged = any(w in lower_text for w in warning_mentions) or any(t in lower_text for t in title_tokens)
            if not acknowledged:
                msg = f"Warning Omission: Active alert '{active_alert.title}' is not acknowledged in response."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.MISSING_WARNING.value)

            # 1c. Severity Downgrade Check
            if active_alert.severity in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
                downgrade_phrases = [
                    "minor warning", "low risk", "low severity", "minimal risk", "yellow alert",
                    "minor alert", "negligible threat", "mild weather",
                    "குறைந்த ஆபத்து", "சிறிய எச்சரிக்கை",
                    "मामूली खतरा", "कम जोखिम", "हल्का खतरा"
                ]
                if any(p in lower_text for p in downgrade_phrases):
                    msg = f"Severity Downgrade: Active alert '{active_alert.title}' ({active_alert.severity.value}) was downgraded to low/minor severity in response."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.SEVERITY_DOWNGRADE.value)

            # 1e. Warning Suppression via Consistency Check (Phase 9 Requirement 5)
            # A high generic forecast consistency score must NEVER suppress an official IMD warning.
            suppression_patterns = [
                r"\b(?:models?|sources?|forecast|consistency)\b.*?\b(?:agree|consistent|high)\b.*?\b(?:no\s+need\s+to\s+worry|ignore\s+(?:the\s+)?warning|warning\s+is\s+unnecessary|safe\s+despite|conditions\s+are\s+safe|safe\s+conditions)\b",
                r"\b(?:high\s+consistency\s+score|consistent\s+forecast)\s+(?:overrides?|cancels?|invalidates?)\s+(?:the\s+)?warning\b",
                r"\b(?:conditions?\s+(?:are|is)\s+safe|no\s+danger)\s+(?:because|since|as)\s+(?:models?|sources?)\b",
                r"\bno\s+need\s+to\s+worry\s+about\s+(?:the\s+)?warning\b",
                r"\bconditions\s+are\s+safe\b",
            ]
            for pat in suppression_patterns:
                if re.search(pat, lower_text):
                    msg = "Warning Suppression: High forecast consistency was used to suppress or dismiss an active official IMD warning."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.WARNING_CONTRADICTION.value)
                    break
        else:
            # No official warning active: Response must not fabricate phantom official alerts
            phantom_warning_phrases = [
                "official red alert", "official cyclone warning", "imd red alert", "imd orange alert",
                "official evacuation order", "official warning active", "active official warning",
                "official warning issued", "there is an official warning",
                "சிவப்பு எச்சரிக்கை", "ரெட் அலர்ட்", "ஆரஞ்சு எச்சரிக்கை", "அதிகாரப்பூர்வ வெளியேற்ற உத்தரவு",
                "रेड अलर्ट", "लाल चेतावनी", "ऑरेंज अलर्ट", "आधिकारिक निकासी आदेश"
            ]
            negations = ["no official", "no active", "not an official", "no red alert", "எச்சரிக்கை இல்லை", "कोई चेतावनी नहीं"]
            if any(p in lower_text for p in phantom_warning_phrases) and not any(neg in lower_text for neg in negations):
                msg = "Phantom Warning: Response claims an active official warning when none exists in ground truth."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.FABRICATED_DATA.value)

            # 1d. Historical Warning Confusion Check (Phase 8 Requirement 4)
            # Historical data cannot become a current warning when no active warning exists.
            historical_confusion_patterns = [
                r"\b(?:flooding|flood|cyclone|storm|heavy\s+rain)\s+is\s+expected\s+today\b",
                r"\b(?:due\s+to\s+last\s+year|because\s+last\s+year|as\s+last\s+year)\b.*?\b(?:expected|warning|danger)\b",
                r"\b(?:flood|cyclone|storm)\s+warning\s+(?:is\s+active|in\s+effect|issued)\s+today\b",
            ]
            for pat in historical_confusion_patterns:
                if re.search(pat, lower_text):
                    msg = (
                        "Historical Warning Confusion: Historical hazard was converted into an active present-day warning "
                        "or declared expected today without an active official IMD alert."
                    )
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.FABRICATED_DATA.value)
                    break

        # ---------------------------------------------------------
        # 2. Hazard & Severity Validation
        # ---------------------------------------------------------
        all_hazards = reasoning.detected_hazards + reasoning.ai_detected_hazards
        severe_hazards = [h for h in all_hazards if h.severity in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME)]

        for h in severe_hazards:
            ht_lower = h.hazard_type.lower()
            if "rain" in ht_lower or "flood" in ht_lower:
                rain_denial_phrases = [
                    "no significant rain", "no rain expected", "dry weather", "completely dry",
                    "clear skies and dry", "மழை பெய்யாது", "மழை இல்லை", "बारिश नहीं होगी"
                ]
                if any(p in lower_text for p in rain_denial_phrases):
                    msg = f"Hazard Erasure: Detected severe hazard '{h.hazard_type}' erased by response claiming dry/no rain conditions."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_HAZARD.value)
            elif "wind" in ht_lower or "cyclone" in ht_lower:
                wind_denial_phrases = [
                    "calm winds", "no wind danger", "gentle breeze only", "காற்று ஆபத்து இல்லை"
                ]
                if any(p in lower_text for p in wind_denial_phrases):
                    msg = f"Hazard Erasure: Severe wind hazard '{h.hazard_type}' denied in response."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_HAZARD.value)

        # Overall risk severity downgrade check
        if reasoning.overall_risk in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME):
            downgrade_overall = [
                "low overall risk", "risk is low", "minimal danger", "safe and calm",
                "பாதுகாப்பான சூழல்", "जोखिम कम है"
            ]
            if any(p in lower_text for p in downgrade_overall):
                msg = f"Severity Downgrade: Overall risk is {reasoning.overall_risk.value} but response claims low risk."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.SEVERITY_DOWNGRADE.value)

        # Severe hazard fabrication check:
        # If no severe hazard exists in ground truth, response should not invent extreme disaster
        has_severe_hazard = any(h.severity in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME) for h in all_hazards)
        if not has_severe_hazard:
            extreme_fabrications = [
                "super cyclone", "cyclone is making landfall", "destructive cyclone",
                "catastrophic flood", "severe heatwave",
                "சூப்பர் புயல்", "புயல் கரையை கடக்கிறது",
                "विनाशकारी चक्रवात", "महाचक्रवात"
            ]
            if any(ef in lower_text for ef in extreme_fabrications):
                msg = "Hazard Fabrication: Response asserts extreme hazard not present in detected hazards."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_HAZARD.value)

        # ---------------------------------------------------------
        # 3. Numeric Claim Validation & Anti-Confusion
        # ---------------------------------------------------------
        valid_temps: Set[float] = set()
        valid_rain_probs: Set[float] = set()
        valid_winds: Set[float] = set()
        valid_rainfalls: Set[float] = set()
        valid_humidities: Set[float] = set()
        valid_all_numbers: Set[float] = set()

        if weather:
            if weather.temperature is not None:
                valid_temps.add(round(float(weather.temperature), 1))
                valid_all_numbers.add(round(float(weather.temperature), 1))
                valid_all_numbers.add(float(round(weather.temperature)))
            if weather.humidity is not None:
                valid_humidities.add(round(float(weather.humidity), 1))
                valid_all_numbers.add(round(float(weather.humidity), 1))
            if weather.rain_probability is not None:
                valid_rain_probs.add(round(float(weather.rain_probability), 1))
                valid_all_numbers.add(round(float(weather.rain_probability), 1))
            if weather.wind_speed is not None:
                valid_winds.add(round(float(weather.wind_speed), 1))
                valid_all_numbers.add(round(float(weather.wind_speed), 1))
            if weather.rainfall_amount_mm is not None:
                valid_rainfalls.add(round(float(weather.rainfall_amount_mm), 1))
                valid_all_numbers.add(round(float(weather.rainfall_amount_mm), 1))

        if forecast:
            for item in forecast:
                valid_temps.add(round(float(item.temperature), 1))
                valid_all_numbers.add(round(float(item.temperature), 1))
                valid_rain_probs.add(round(float(item.rain_probability), 1))
                valid_all_numbers.add(round(float(item.rain_probability), 1))
                valid_winds.add(round(float(item.wind_speed), 1))
                valid_all_numbers.add(round(float(item.wind_speed), 1))
                if item.rainfall_amount_mm is not None:
                    valid_rainfalls.add(round(float(item.rainfall_amount_mm), 1))
                    valid_all_numbers.add(round(float(item.rainfall_amount_mm), 1))

        consistency_score = float(reasoning.consistency_score)
        valid_all_numbers.add(consistency_score)
        valid_all_numbers.add(float(reasoning.data_age_minutes))
        valid_all_numbers.update({0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 12.0, 24.0, 48.0, 100.0})

        # 3a. Temperature Mentions
        temp_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:°\s*c|°c|celsius|degrees\s*c\b)", lower_text)
        for m in temp_matches:
            try:
                t_val = round(float(m), 1)
                if t_val > 65.0 or t_val < -60.0:
                    msg = f"Unphysical Temperature: Claimed {t_val}°C is outside plausible meteorological bounds."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
                elif valid_temps and not any(abs(t_val - vt) <= 1.5 for vt in valid_temps):
                    msg = f"Unsupported Temperature: Claimed {t_val}°C not found in ground truth (valid: {sorted(list(valid_temps))})."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
                else:
                    verified_claims.append(f"Temperature {t_val}°C verified in ground truth.")
            except ValueError:
                continue

        # 3b. Rain Probability Claims & Consistency Score Confusion
        rain_prob_matches = (
            re.findall(r"(\d{1,3})\s*%(?:\s*(?:chance of rain|rain probability|probability of rain|rain chance|மழை வாய்ப்பு|बारिश की संभावना))", lower_text)
            + re.findall(r"(?:chance of rain|rain probability|probability of rain|rain chance)\s*(?:is|of|:)?\s*(\d{1,3})\s*%", lower_text)
        )
        for rp in rain_prob_matches:
            try:
                p_val = int(rp)
                if p_val > 100 or p_val < 0:
                    msg = f"Impossible Percentage: Rain probability {p_val}% is invalid."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
                # Anti-confusion check: consistency score confused with rain probability
                elif p_val == round(consistency_score) and (not valid_rain_probs or not any(abs(p_val - vr) <= 2.0 for vr in valid_rain_probs)):
                    msg = f"Metric Confusion: Forecast Consistency Score ({int(consistency_score)}%) was confused with Rain Probability ({p_val}%)."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
                elif valid_rain_probs and not any(abs(p_val - vr) <= 5.0 for vr in valid_rain_probs):
                    msg = f"Unsupported Rain Probability: Claimed {p_val}% not found in ground truth (valid: {sorted(list(valid_rain_probs))})."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
                else:
                    verified_claims.append(f"Rain probability {p_val}% verified in ground truth.")
            except ValueError:
                continue

        # 3c. General Percentages
        percentages = [int(p) for p in re.findall(r"\b(\d{1,3})\s*%", response_text)]
        for p in percentages:
            if p > 100 or p < 0:
                msg = f"Impossible Percentage: {p}% exceeds plausible limits."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
            else:
                matching = any(abs(p - g) <= 5 for g in valid_all_numbers)
                if matching:
                    verified_claims.append(f"Percentage {p}% verified in ground truth.")
                else:
                    issues.append(f"Unverified Metric: Mentioned {p}% not found in retrieved weather records.")
                    if valid_all_numbers and not any(abs(p - g) <= 15 for g in valid_all_numbers):
                        msg = f"Unsupported Percentage: Claimed {p}% is not supported by telemetry."
                        violations.append(msg)
                        violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)

        # 3d. Scientific Probability Overclaim Check (Phase 9 Requirement 3)
        # Consistency score is an application-level indicator, not certified scientific probability.
        overclaim_patterns = [
            r"\b(?:certified\s+meteorological\s+probability|scientifically\s+validated\s+probability|certified\s+probability)\b",
            r"\b(?:guaranteed\s+scientific\s+certainty)\b",
        ]
        for pat in overclaim_patterns:
            if re.search(pat, lower_text):
                msg = "Scientific Overclaim: Forecast consistency was claimed as certified meteorological probability."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.FABRICATED_DATA.value)
                break

        # 3e. Rainfall Amount Claims
        rainfall_matches = re.findall(r"(\d+(?:\.\d+)?)\s*mm\b", lower_text)
        imd_thresholds = {64.5, 115.5, 204.4}
        for rm in rainfall_matches:
            try:
                rf_val = round(float(rm), 1)
                is_imd_threshold = any(abs(rf_val - th) <= 1.0 for th in imd_thresholds) and any(
                    k in lower_text for k in ["threshold", "imd", "category", "heavy", "எல்லை", "श्रेणी"]
                )
                if is_imd_threshold:
                    verified_claims.append(f"Rainfall threshold {rf_val} mm verified as IMD category standard.")
                elif valid_rainfalls and not any(abs(rf_val - vr) <= 3.0 or (vr > 0 and abs(rf_val - vr) / vr <= 0.2) for vr in valid_rainfalls):
                    msg = f"Unsupported Rainfall Amount: Claimed {rf_val} mm not found in ground truth ({sorted(list(valid_rainfalls))})."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
                else:
                    verified_claims.append(f"Rainfall {rf_val} mm verified in ground truth.")
            except ValueError:
                continue

        # 3e. Wind Speed Claims
        wind_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:km/h|kmph|km\/h)\b", lower_text)
        for wm in wind_matches:
            try:
                w_val = round(float(wm), 1)
                if w_val < 0.0 or w_val > 400.0:
                    msg = f"Unphysical Wind Speed: {w_val} km/h is implausible."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
                elif valid_winds and not any(abs(w_val - vw) <= 4.0 for vw in valid_winds):
                    msg = f"Unsupported Wind Speed: Claimed {w_val} km/h not found in ground truth ({sorted(list(valid_winds))})."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_NUMBER.value)
                else:
                    verified_claims.append(f"Wind speed {w_val} km/h verified in ground truth.")
            except ValueError:
                continue

        # ---------------------------------------------------------
        # 4. Unit Validation
        # ---------------------------------------------------------
        if re.search(r"\b\d+(?:\.\d+)?\s*(?:mph|miles\s*per\s*hour)\b", lower_text):
            msg = "Unit Mismatch: Wind speed reported in mph instead of km/h."
            violations.append(msg)
            issues.append(msg)
            violation_categories.append(ValidationCategoryEnum.UNIT_MISMATCH.value)

        if re.search(r"\b\d+(?:\.\d+)?\s*(?:inches|in\.)\s*(?:of\s*rain|rainfall)?\b", lower_text):
            msg = "Unit Mismatch: Rainfall reported in inches instead of mm."
            violations.append(msg)
            issues.append(msg)
            violation_categories.append(ValidationCategoryEnum.UNIT_MISMATCH.value)

        if re.search(r"\b\d+(?:\.\d+)?\s*(?:°\s*f|fahrenheit)\b", lower_text):
            msg = "Unit Mismatch: Temperature reported in Fahrenheit instead of Celsius."
            violations.append(msg)
            issues.append(msg)
            violation_categories.append(ValidationCategoryEnum.UNIT_MISMATCH.value)

        # ---------------------------------------------------------
        # 5. Location Validation
        # ---------------------------------------------------------
        grounded_locations: Set[str] = {reasoning.location.lower()}
        if weather and weather.location and weather.location.name:
            grounded_locations.add(weather.location.name.lower())
        if nlu and nlu.entities.location:
            grounded_locations.add(nlu.entities.location.lower())
        if reasoning.active_warnings:
            for al in reasoning.active_warnings:
                for aff in al.affected_locations:
                    grounded_locations.add(aff.lower())

        major_cities = [
            "coimbatore", "chennai", "madurai", "nagapattinam", "bengaluru",
            "mumbai", "delhi", "kolkata", "hyderabad", "kanchipuram", "salem", "trichy"
        ]
        for city in major_cities:
            if city in lower_text:
                is_grounded_loc = any(city in gl for gl in grounded_locations)
                is_query_loc = nlu and city in nlu.original_text.lower()
                if not is_grounded_loc and not is_query_loc:
                    msg = f"Unsupported Location: Response mentions '{city.title()}' which is not in grounded location context."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_LOCATION.value)

        # ---------------------------------------------------------
        # 6. Source Attribution Validation
        # ---------------------------------------------------------
        allowed_sources: Set[str] = {s.lower() for s in reasoning.sources_used}
        allowed_sources.update(["imd", "open-meteo", "ncmrwf", "cpc", "moes"])
        if weather and weather.source:
            allowed_sources.add(weather.source.lower())

        unsupported_third_party = [
            "accuweather", "weather channel", "bbc weather", "skymet",
            "weather underground", "wunderground", "dark sky"
        ]
        for src in unsupported_third_party:
            if src in lower_text and src not in allowed_sources:
                msg = f"Unsupported Source Attribution: Response cites '{src.title()}' which is not an authorized data provider."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_SOURCE.value)

        # ---------------------------------------------------------
        # 7. Temporal Scope Validation
        # ---------------------------------------------------------
        is_tomorrow_scope = (
            (advisory and advisory.time_context == TimeContextEnum.TOMORROW)
            or (nlu and nlu.entities.date == "tomorrow")
        )
        if is_tomorrow_scope:
            present_tense_storm_phrases = [
                "heavy rain is occurring right now",
                "currently pouring",
                "torrential rain is falling right now",
                "storm is hitting right now",
                "தற்போது அடைமழை பெய்து கொண்டிருக்கிறது",
                "இப்போது மழை பெய்கிறது",
                "अभी भारी बारिश हो रही है"
            ]
            if any(p in lower_text for p in present_tense_storm_phrases):
                msg = "Temporal Contradiction: Tomorrow's forecast event is claimed as occurring right now."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.UNSUPPORTED_TIME.value)

        # ---------------------------------------------------------
        # 8. Uncertainty & Missing Data Validation
        # ---------------------------------------------------------
        uncertainty_present = (
            reasoning.source_agreement == SourceAgreementEnum.LOW
            or reasoning.freshness == FreshnessStatusEnum.STALE
            or len(reasoning.contradictions) > 0
        )
        if uncertainty_present:
            false_certainty_phrases = [
                "will definitely occur", "100% certain", "100% guaranteed",
                "zero chance of deviation", "absolutely certain", "completely confident",
                "கண்டிப்பாக நடக்கும்", "நிச்சயமாக நடக்கும்", "निश्चित रूप से होगा"
            ]
            if any(p in lower_text for p in false_certainty_phrases):
                msg = "False Certainty: Expressed definitive certainty despite source disagreement, contradictions, or stale telemetry."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.FALSE_CERTAINTY.value)

        # Source conflict misrepresentation
        if reasoning.source_agreement == SourceAgreementEnum.LOW:
            agreement_claims = [
                "sources completely agree", "all sources agree", "both providers match exactly",
                "அனைத்து ஆதாரங்களும் ஒத்துப்போகின்றன", "सभी स्रोत सहमत हैं"
            ]
            if any(p in lower_text for p in agreement_claims):
                msg = "Source Disagreement Misrepresentation: Claimed sources agree when source agreement is LOW."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.FALSE_CERTAINTY.value)

        # Stale data misrepresentation
        if reasoning.freshness == FreshnessStatusEnum.STALE:
            freshness_claims = [
                "data is completely fresh", "just updated right now", "real-time live update",
                "புதிய தகவல்", "ताज़ा जानकारी"
            ]
            if any(p in lower_text for p in freshness_claims):
                msg = "Stale Data Misrepresentation: Claimed data is completely fresh when telemetry is STALE."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.FABRICATED_DATA.value)

        # Missing telemetry fabrication
        if "wind_speed" in reasoning.missing_fields or (weather and weather.wind_speed is None):
            if re.search(r"\b\d+\s*(?:km/h|kmph)\b", lower_text):
                msg = "Fabricated Data: Wind speed is unavailable in telemetry but a specific value was generated."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.FABRICATED_DATA.value)

        if "humidity" in reasoning.missing_fields or (weather and weather.humidity is None):
            if re.search(r"(?:humidity|ஈரப்பதம்|आर्द्रता)\s*(?:is|of|:)?\s*\d+\s*%", lower_text):
                msg = "Fabricated Data: Humidity is unavailable in telemetry but a specific value was generated."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.FABRICATED_DATA.value)

        # ---------------------------------------------------------
        # 9. Advisory & Dangerous Action Protection
        # ---------------------------------------------------------
        # 9a. Institutional Closure Claim Check (SIH Demo Rule)
        unauthorized_holiday_claims = [
            "college will be closed", "colleges will be closed", "school is closed", "schools will be closed",
            "holiday declared", "schools and colleges are closed",
            "கல்லூரிக்கு விடுமுறை", "பள்ளிக்கு விடுமுறை", "விடுமுறை அறிவிக்கப்பட்டுள்ளது",
            "स्कूल बंद रहेंगे", "कॉलेज बंद रहेगा", "छुट्टी घोषित"
        ]
        if any(claim in lower_text for claim in unauthorized_holiday_claims):
            msg = "Unauthorized Institutional Declaration: WeatherGPT must advise checking official announcements instead of declaring school/college closure."
            violations.append(msg)
            issues.append(msg)
            violation_categories.append(ValidationCategoryEnum.UNAUTHORIZED_DECLARATION.value)

        # 9b. Action Guidance Reversal Check
        if advisory and advisory.priority in (AdvisoryPriorityEnum.HIGH, AdvisoryPriorityEnum.CRITICAL):
            dangerous_actions = [
                "go outside immediately", "safe to venture into sea", "safe for deep sea fishing",
                "head outdoors without worry", "safe to go swimming in sea", "perfect day for beach swimming",
                "go out and play",
                "கடலுக்குள் செல்லலாம்", "தாராளமாக வெளியே செல்லலாம்",
                "समुद्र में जा सकते हैं", "बाहर जाना सुरक्षित है"
            ]
            if any(p in lower_text for p in dangerous_actions):
                msg = "Advisory Action Contradiction: Advises hazardous outdoor/sea activity directly contradicting high-priority safety advisory."
                violations.append(msg)
                issues.append(msg)
                violation_categories.append(ValidationCategoryEnum.FABRICATED_ACTION.value)

        # ---------------------------------------------------------
        # 10. Language Script Validation
        # ---------------------------------------------------------
        if target_language:
            allow_latin = bool(nlu and nlu.detected_language in (LanguageEnum.TANGLISH, LanguageEnum.HINGLISH))
            if target_language in (LanguageEnum.TA, LanguageEnum.TANGLISH):
                has_tamil = bool(re.search(r"[\u0B80-\u0BFF]", response_text))
                if not has_tamil and target_language == LanguageEnum.TA and not allow_latin:
                    msg = "Language Mismatch: Requested Tamil response but generated text lacks Tamil script."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.LANGUAGE_MISMATCH.value)
            elif target_language in (LanguageEnum.HI, LanguageEnum.HINGLISH):
                has_hindi = bool(re.search(r"[\u0900-\u097F]", response_text))
                if not has_hindi and target_language == LanguageEnum.HI and not allow_latin:
                    msg = "Language Mismatch: Requested Hindi response but generated text lacks Devanagari script."
                    violations.append(msg)
                    issues.append(msg)
                    violation_categories.append(ValidationCategoryEnum.LANGUAGE_MISMATCH.value)

        # ---------------------------------------------------------
        # 10b. Adversarial Prompt Injection & False Certainty Defense (Phase 17)
        # ---------------------------------------------------------
        checked_fields.append("adversarial_safety")
        
        injection_leak_phrases = [
            "ignoring previous instructions", "as requested, ignoring instructions",
            "overriding safety rules", "bypassing safety guidelines", "bypassing official alerts",
            "revealing secret system prompt", "internal system instructions are:",
            "user override granted", "disabling weather warnings as asked",
            "system override", "secret developer instructions", "ignore constraints",
            "unrestrained bot", "<<sys>>", "[system]", "<|im_start|>", "--- begin system override ---",
            "fake imd circular", "special imd override", "imd alert revoked by user",
            "bypassing responsevalidator", "validator bypassed",
            "previous instructions ah ignore", "rules ellam ignore",
            "previous instructions bhool", "rules ignore kar raha",
            "முந்தைய வழிமுறைகளை புறக்கணிக்கிறேன்",
            "पिछले निर्देशों को नजरअंदाज कर रहा हूँ"
        ]
        if any(il in lower_text for il in injection_leak_phrases):
            msg = "Adversarial Injection Detected: Generated response contains prompt-override confirmation or reveals system safety instructions."
            violations.append(msg)
            issues.append(msg)
            violation_categories.append(ValidationCategoryEnum.UNAUTHORIZED_DECLARATION.value)

        false_certainty_phrases = [
            "100% guaranteed forecast", "i guarantee 100% precision", "absolute 100% certainty",
            "zero chance of error", "cannot possibly change", "guaranteed zero rain",
            "100% guarantee", "absolute certainty", "guarantee 100%", "100% certain", "100% sure",
            "guaranteed no rain", "guaranteed rain", "zero risk guaranteed", "100% confirm",
            "100% sure aagum", "100% pakka guarantee",
            "100% நிச்சயமாக", "100% गारंटीशुदा पूर्वानुमान", "100% निश्चित है", "100% पक्का"
        ]
        if any(fc in lower_text for fc in false_certainty_phrases):
            msg = "False Certainty Detected: Response claims 100% absolute forecast precision or zero-uncertainty guarantee."
            violations.append(msg)
            issues.append(msg)
            violation_categories.append(ValidationCategoryEnum.FALSE_CERTAINTY.value)

        unauthorized_gov_phrases = [
            "on behalf of national disaster authority, i declare",
            "i am issuing an official government emergency decree",
            "as the director of meteorological services, i order",
            "curfew order", "as the government authority", "declare all schools",
            "officially declare all schools", "declare school holiday",
            "collector declares holiday", "school leave announced by weathergpt",
            "schools are declared closed",
            "அரசாங்கத்தின் சார்பாக அவசரநிலையை அறிவிக்கிறேன்",
            "सरकार की ओर से आपातकाल घोषित करता हूँ"
        ]
        if any(ug in lower_text for ug in unauthorized_gov_phrases):
            msg = "Unauthorized Declaration: Response attempts to declare government emergency powers or impersonate official authorities."
            violations.append(msg)
            issues.append(msg)
            violation_categories.append(ValidationCategoryEnum.UNAUTHORIZED_DECLARATION.value)

        # ---------------------------------------------------------
        # 11. Final Status Resolution & Policy Gate
        # ---------------------------------------------------------
        # Deduplicate issues while preserving insertion order
        all_issues = list(dict.fromkeys(issues + violations))

        has_violations = len(violations) > 0
        hallucination_detected = any(
            cat in [
                ValidationCategoryEnum.UNSUPPORTED_NUMBER.value,
                ValidationCategoryEnum.UNSUPPORTED_LOCATION.value,
                ValidationCategoryEnum.UNSUPPORTED_SOURCE.value,
                ValidationCategoryEnum.FABRICATED_DATA.value,
                ValidationCategoryEnum.UNSUPPORTED_HAZARD.value,
            ]
            for cat in violation_categories
        )
        warning_consistency_passed = not any(
            cat in [
                ValidationCategoryEnum.WARNING_CONTRADICTION.value,
                ValidationCategoryEnum.MISSING_WARNING.value,
                ValidationCategoryEnum.SEVERITY_DOWNGRADE.value,
            ]
            for cat in violation_categories
        )

        if has_violations:
            status = ValidationStatusEnum.REJECT
            is_valid = False
            fallback_required = True
        elif len(warnings) > 0:
            status = ValidationStatusEnum.PASS_WITH_WARNING
            is_valid = True
            fallback_required = False
        else:
            status = ValidationStatusEnum.PASS
            is_valid = True
            fallback_required = False

        return ValidationResult(
            is_valid=is_valid,
            hallucination_detected=hallucination_detected,
            warning_consistency_passed=warning_consistency_passed,
            issues=all_issues,
            verified_claims=verified_claims,
            status=status,
            violations=violations,
            warnings=warnings,
            checked_fields=checked_fields,
            fallback_required=fallback_required,
            violation_categories=violation_categories,
        )

    @classmethod
    def validate(cls, *args, **kwargs) -> ValidationResult:
        """Alias for validate_response."""
        return cls.validate_response(*args, **kwargs)
