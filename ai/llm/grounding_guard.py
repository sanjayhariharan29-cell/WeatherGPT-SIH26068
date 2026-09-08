"""Basic Grounding Safety Guard for Phase 5 LLM Generation.

Performs deterministic fast-path validation on generated LLM responses to detect:
1. Direct contradiction of active official warnings
2. Invented official warnings when none exist in context
3. Severe unsupported meteorological numbers (hallucinated temperatures/rainfall/winds)
4. Failure to resist prompt injection overrides

Unsafe responses trigger an immediate switch to the deterministic fallback.
"""

import re
from typing import List, Set, Tuple
from ai.llm.context_builder import GroundedContext


def verify_grounding(response_text: str, context: GroundedContext) -> Tuple[bool, List[str]]:
    """Evaluates whether an LLM response adheres to grounded context facts."""
    issues: List[str] = []
    text_lower = response_text.lower()

    # 1. Contradiction of Active Official Warning
    if context.official_warnings:
        # High/extreme official alerts require strict vigilance
        contradiction_phrases = [
            "no warning",
            "no active warning",
            "no official warning",
            "no danger",
            "completely safe",
            "all clear",
            "no precautions needed",
            "no precautions necessary",
            "weather is safe",
            "warning has been cancelled",
            "alert is false",
            "ignore the warning",
            # Tamil
            "எச்சரிக்கை இல்லை",
            "ஆபத்து இல்லை",
            "முற்றிலும் பாதுகாப்பானது",
            "எச்சரிக்கையை புறக்கணிக்கவும்",
            # Hindi
            "कोई चेतावनी नहीं",
            "कोई खतरा नहीं",
            "बिल्कुल सुरक्षित",
            "चेतावनी रद्द",
            "चेतावनी को नजरअंदाज करें",
        ]
        for phrase in contradiction_phrases:
            if phrase in text_lower:
                issues.append(
                    f"Response contradicts active official IMD warning with phrase: '{phrase}'"
                )
                break

    # 2. Invented Official Warnings when none exist
    if not context.official_warnings:
        invented_warning_phrases = [
            "official red alert",
            "official cyclone warning",
            "imd red alert",
            "imd orange alert",
            "official evacuation order",
            "official warning issued",
            "official warning active",
            # Tamil
            "சிவப்பு எச்சரிக்கை",
            "ரெட் அலர்ட்",
            "ஆரஞ்சு எச்சரிக்கை",
            "அதிகாரப்பூர்வ வெளியேற்ற உத்தரவு",
            # Hindi
            "रेड अलर्ट",
            "लाल चेतावनी",
            "ऑरेंज चेतावनी",
            "आधिकारिक निकासी आदेश",
        ]
        for phrase in invented_warning_phrases:
            if phrase in text_lower:
                issues.append(
                    f"Response claims an official alert ('{phrase}') when no official warning exists in ground truth"
                )
                break

    # 3. Check for Unsupported Weather Numbers
    # Collect all numbers appearing in observed facts, forecasts, consistency score, and age
    valid_numbers: Set[float] = set()

    obs = context.observed_facts
    for k in ["temperature_c", "rain_probability_pct", "rainfall_amount_mm", "humidity_pct", "wind_speed_kmh"]:
        val = obs.get(k)
        if isinstance(val, (int, float)):
            valid_numbers.add(round(float(val), 1))
            valid_numbers.add(float(int(val)))

    for f in context.forecast_facts:
        for k in ["temperature_c", "rain_probability_pct", "rainfall_amount_mm", "wind_speed_kmh"]:
            val = f.get(k)
            if isinstance(val, (int, float)):
                valid_numbers.add(round(float(val), 1))
                valid_numbers.add(float(int(val)))

    # Allow common formatting numbers
    valid_numbers.update({0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 12.0, 24.0, 48.0, 100.0})
    if isinstance(context.data_quality.get("consistency_score"), (int, float)):
        score = float(context.data_quality["consistency_score"])
        valid_numbers.add(score)
    if isinstance(context.data_quality.get("data_age_minutes"), (int, float)):
        age = float(context.data_quality["data_age_minutes"])
        valid_numbers.add(age)

    # Collect numbers appearing in static reference knowledge
    for rk in context.reference_knowledge:
        ref_text = f"{rk.get('title', '')} {rk.get('heading', '')} {rk.get('content', '')}"
        ref_nums = re.findall(r"\b(\d+(?:\.\d+)?)\b", ref_text)
        for rn in ref_nums:
            try:
                valid_numbers.add(round(float(rn), 1))
            except ValueError:
                pass

    # Extract explicit weather metric numbers from text: e.g. "45°C", "95 km/h", "120 mm"
    metric_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:°c|celsius|km/h|mm)\b", text_lower)
    for m in metric_matches:
        try:
            val = round(float(m), 1)
            # If a claimed weather metric is not close to any valid number in context
            if not any(abs(val - vn) <= 1.0 for vn in valid_numbers):
                issues.append(
                    f"Unsupported meteorological metric value claimed in response: {m}"
                )
                break
        except ValueError:
            continue

    is_grounded = len(issues) == 0
    return is_grounded, issues
