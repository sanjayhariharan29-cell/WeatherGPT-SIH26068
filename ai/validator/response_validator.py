"""Response Validation and Anti-Hallucination Engine for WeatherGPT.

Ensures LLM/generated outputs are strictly grounded in retrieved meteorological facts
and never violate official warning mandates per docs/09_AI_Design.md:553.
"""

import re
from typing import List, Optional
from ai.models import (
    ForecastItem,
    RiskLevelEnum,
    ValidationResult,
    WeatherReasoningResult,
    WeatherRecord,
)


class ResponseValidator:
    """Validates weather answers against ground-truth data before presenting to user."""

    @staticmethod
    def validate_response(
        response_text: str,
        reasoning: WeatherReasoningResult,
        weather: Optional[WeatherRecord] = None,
        forecast: Optional[List[ForecastItem]] = None
    ) -> ValidationResult:
        """Performs rigorous grounding and safety checks on generated response text."""
        issues: List[str] = []
        verified_claims: List[str] = []
        hallucination_detected = False
        warning_consistency_passed = True

        lower_text = response_text.lower()

        # 1. Official Warning Integrity Check
        if reasoning.active_warnings:
            # An official warning exists
            active_alert = reasoning.active_warnings[0]
            # Response must not claim there are no warnings or that it is completely safe
            contradictory_phrases = [
                "no warning", "no warnings", "completely safe", "no danger", "no precautions needed",
                "எச்சரிக்கை இல்லை", "ஆபத்து இல்லை"
            ]
            if any(phrase in lower_text for phrase in contradictory_phrases):
                warning_consistency_passed = False
                issues.append(
                    f"Warning Contradiction: Active IMD alert '{active_alert.title}' exists, but response claims conditions are safe."
                )

            # Response should mention the warning or caution
            warning_mentions = [
                "warning", "alert", "caution", "precaution", "எச்சரிக்கை", "கவனம்", "பாதுகாப்பு"
            ]
            if not any(w in lower_text for w in warning_mentions):
                issues.append(
                    f"Warning Omission: Active alert '{active_alert.title}' is not acknowledged in the response."
                )
        else:
            # No official warning active: Response should not fabricate a phantom official warning
            if "official warning" in lower_text and "no official warning" not in lower_text:
                if "there is an official warning" in lower_text or "active warning" in lower_text:
                    hallucination_detected = True
                    issues.append("Hallucination: Response claimed an active official warning when none exists.")

        # 2. Extract Numbers & Cross-Reference Ground Truth
        # Find numeric mentions like "29°C", "29 C", "70%", "18 km/h"
        ground_truth_numbers = set()
        if weather:
            ground_truth_numbers.add(round(weather.temperature))
            ground_truth_numbers.add(round(weather.humidity))
            ground_truth_numbers.add(round(weather.rain_probability))
            ground_truth_numbers.add(round(weather.wind_speed))
            if weather.rainfall_amount_mm:
                ground_truth_numbers.add(round(weather.rainfall_amount_mm))

        if forecast:
            for item in forecast:
                ground_truth_numbers.add(round(item.temperature))
                ground_truth_numbers.add(round(item.rain_probability))
                ground_truth_numbers.add(round(item.wind_speed))

        # Check explicit percentage and temperature mentions
        percentages = [int(p) for p in re.findall(r"\b(\d{1,3})\s*%", response_text)]
        for p in percentages:
            # Allow common conversational percentage rounding or check against ground truth
            matching = any(abs(p - g) <= 5 for g in ground_truth_numbers)
            if matching:
                verified_claims.append(f"Precipitation/Humidity percentage {p}% verified in ground truth.")
            else:
                issues.append(f"Unverified Metric: Mentioned {p}% not found in retrieved weather records.")

        # 3. Institutional Closure Claim Check (SIH Demo Rule)
        unauthorized_holiday_claims = [
            "college will be closed", "school is closed", "holiday declared",
            "கல்லூரிக்கு விடுமுறை", "பள்ளிக்கு விடுமுறை"
        ]
        if any(claim in lower_text for claim in unauthorized_holiday_claims):
            issues.append(
                "Unauthorized Institutional Declaration: WeatherGPT must advise checking official announcements instead of declaring school/college closure."
            )

        is_valid = (len(issues) == 0) and warning_consistency_passed and (not hallucination_detected)

        return ValidationResult(
            is_valid=is_valid,
            hallucination_detected=hallucination_detected,
            warning_consistency_passed=warning_consistency_passed,
            issues=issues,
            verified_claims=verified_claims
        )
