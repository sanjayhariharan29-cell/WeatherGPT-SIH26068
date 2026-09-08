"""Grounded Prompt Engineering for WeatherGPT.

Constructs strictly bounded, traceable prompts adhering to
docs/01_PS_REQUIREMENTS.md:137 and docs/09_AI_Design.md:432.
"""

from typing import List, Optional
from ai.models import (
    DecisionAdvisory,
    ForecastItem,
    LanguageEnum,
    NLUResult,
    OfficialAlert,
    WeatherReasoningResult,
    WeatherRecord,
)

SYSTEM_INSTRUCTION = """You are WeatherGPT, an authoritative conversational meteorological decision assistant for the India Meteorological Department (IMD) and Ministry of Earth Sciences (MoES).

CRITICAL GROUNDING RULES:
1. USE ONLY THE SUPPLIED METEOROLOGICAL DATA: Do not guess, extrapolate, or invent temperatures, rain probabilities, wind speeds, or hazard levels.
2. OFFICIAL WARNINGS HAVE ABSOLUTE PRIORITY: If an official alert is active, highlight it immediately at the beginning. Never downplay or contradict an official warning.
3. CONVERSATIONAL LANGUAGE MATCH: Respond naturally in the user's preferred language ({target_language}). If the query is in Tanglish (Tamil written in English script), respond with natural colloquial Tamil or Tanglish as appropriate.
4. ACTIONABLE ADVISORY: State concise, practical guidance tailored to the user's persona ({persona}).
5. INSTITUTIONAL BOUNDARY: You do not declare school or college closures. Advise students to monitor official institutional notices.
6. SOURCE & FRESHNESS ATTRIBUTION: Explicitly reference the data source ({source}) and update timestamp.
"""


def build_grounded_prompt(
    nlu: NLUResult,
    weather: Optional[WeatherRecord],
    reasoning: WeatherReasoningResult,
    advisory: DecisionAdvisory,
    forecast: Optional[List[ForecastItem]] = None,
    safety_guidance: Optional[List[str]] = None
) -> str:
    """Builds the comprehensive grounded user prompt."""
    prompt_lines = [
        f"USER QUESTION: {nlu.original_text}",
        f"DETECTED INTENT: {nlu.intent.value}",
        f"DETECTED LANGUAGE: {nlu.detected_language.value}",
        f"USER PERSONA: {advisory.persona.value}",
        "",
        "--- GROUND TRUTH METEOROLOGICAL DATA ---",
        f"Location: {reasoning.location}",
        f"Data Freshness: {reasoning.freshness.value} (updated {reasoning.data_age_minutes} minutes ago)",
        f"Forecast Consistency Score: {reasoning.consistency_score}/100 ({reasoning.source_agreement.value})",
        f"Sources Used: {', '.join(reasoning.sources_used)}"
    ]

    if weather:
        prompt_lines.extend([
            f"Current Temperature: {weather.temperature:.1f}°C",
            f"Precipitation Probability: {weather.rain_probability:.0f}%",
            f"Relative Humidity: {weather.humidity:.0f}%",
            f"Wind Speed: {weather.wind_speed:.1f} km/h",
            f"Sky Condition: {weather.weather_condition}"
        ])

    if reasoning.active_warnings:
        prompt_lines.append("\n--- ACTIVE OFFICIAL IMD WARNINGS ---")
        for alert in reasoning.active_warnings:
            prompt_lines.append(
                f"[URGENT ALERT] Title: {alert.title} | Severity: {alert.severity.value.upper()} | Type: {alert.type} | Details: {alert.description}"
            )

    if forecast:
        prompt_lines.append("\n--- SHORT-TERM FORECAST ---")
        for f in forecast[:4]:
            prompt_lines.append(
                f"Time: {f.time} | Temp: {f.temperature:.1f}°C | Rain: {f.rain_probability:.0f}% | Wind: {f.wind_speed:.1f} km/h | Condition: {f.condition}"
            )

    prompt_lines.extend([
        "\n--- REASONER DECISION & ADVISORY ---",
        f"Overall Weather Risk: {reasoning.overall_risk.value.upper()}",
        f"Advisory Headline: {advisory.headline}",
        f"Precautionary Advice: {advisory.advisory_text}",
        f"Recommended Action Items: {'; '.join(advisory.key_precautions)}"
    ])

    if safety_guidance:
        prompt_lines.append("\n--- DOMAIN KNOWLEDGE & SAFETY GUIDANCE ---")
        for g in safety_guidance:
            prompt_lines.append(f"- {g}")

    prompt_lines.extend([
        "",
        "Please provide a grounded, empathetic, and direct answer adhering to the system rules above."
    ])

    return "\n".join(prompt_lines)
