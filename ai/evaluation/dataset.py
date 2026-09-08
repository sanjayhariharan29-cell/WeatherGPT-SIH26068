"""Dataset Loader and Schema Validators for Phase 10 AI Evaluation."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai.evaluation.schemas import (
    AdvisoryEvalCase,
    HazardEvalCase,
    NLUEvalCase,
    SafetyEvalCase,
)
from ai.models import (
    ForecastItem,
    LocationInfo,
    OfficialAlert,
    RiskLevelEnum,
    WeatherRecord,
)

DATA_DIR = Path(__file__).resolve().parent / "data"


def load_nlu_dataset(path: Optional[Path] = None) -> List[NLUEvalCase]:
    """Loads and validates the golden NLU evaluation dataset."""
    filepath = path or (DATA_DIR / "golden_nlu_dataset.json")
    with open(filepath, "r", encoding="utf-8") as f:
        raw_items = json.load(f)
    return [NLUEvalCase.model_validate(item) for item in raw_items]


def load_hazard_dataset(path: Optional[Path] = None) -> List[HazardEvalCase]:
    """Loads and validates the golden hazard evaluation dataset."""
    filepath = path or (DATA_DIR / "golden_hazard_dataset.json")
    with open(filepath, "r", encoding="utf-8") as f:
        raw_items = json.load(f)
    return [HazardEvalCase.model_validate(item) for item in raw_items]


def load_advisory_dataset(path: Optional[Path] = None) -> List[AdvisoryEvalCase]:
    """Loads and validates the golden advisory evaluation dataset."""
    filepath = path or (DATA_DIR / "golden_advisory_dataset.json")
    with open(filepath, "r", encoding="utf-8") as f:
        raw_items = json.load(f)
    return [AdvisoryEvalCase.model_validate(item) for item in raw_items]


def load_safety_dataset(path: Optional[Path] = None) -> List[SafetyEvalCase]:
    """Loads and validates the golden safety/anti-hallucination dataset."""
    filepath = path or (DATA_DIR / "golden_safety_dataset.json")
    with open(filepath, "r", encoding="utf-8") as f:
        raw_items = json.load(f)
    return [SafetyEvalCase.model_validate(item) for item in raw_items]


def build_weather_record_from_dict(d: Dict[str, Any], location_name: str = "Coimbatore") -> WeatherRecord:
    """Helper to convert JSON weather fixture into a typed WeatherRecord."""
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=LocationInfo(name=location_name, latitude=11.0168, longitude=76.9558, state="Tamil Nadu"),
        observed_at=now - timedelta(minutes=10),
        retrieved_at=now,
        temperature=float(d.get("temperature", 28.0)),
        humidity=float(d.get("humidity", 60.0)),
        rain_probability=float(d.get("rain_probability", 20.0)),
        wind_speed=float(d.get("wind_speed", 15.0)),
        rainfall_amount_mm=float(d.get("rainfall_amount_mm", 0.0)),
        weather_condition=str(d.get("weather_condition", "Clear")),
        source=str(d.get("source", "IMD")),
    )


def build_alerts_from_list(alerts: Optional[List[Dict[str, Any]]]) -> List[OfficialAlert]:
    """Helper to convert JSON alert fixtures into typed OfficialAlerts."""
    if not alerts:
        return []
    now = datetime.now(timezone.utc)
    res = []
    for a in alerts:
        sev_str = a.get("severity", "high").lower()
        sev_enum = RiskLevelEnum(sev_str) if sev_str in [r.value for r in RiskLevelEnum] else RiskLevelEnum.HIGH
        res.append(
            OfficialAlert(
                type=a.get("type", "heavy_rain"),
                severity=sev_enum,
                title=a.get("title", "Official IMD Alert"),
                description=a.get("description", "Advisory active."),
                source=a.get("source", "IMD"),
                issued_at=now - timedelta(hours=1),
                expires_at=now + timedelta(hours=8),
                affected_locations=["Coimbatore", "Tamil Nadu"],
            )
        )
    return res


def build_forecast_from_list(items: Optional[List[Dict[str, Any]]]) -> List[ForecastItem]:
    """Helper to convert JSON forecast fixtures into ForecastItems."""
    if not items:
        return []
    now = datetime.now(timezone.utc)
    res = []
    for idx, it in enumerate(items):
        res.append(
            ForecastItem(
                time=it.get("time", (now + timedelta(hours=idx + 1)).isoformat()),
                temperature=float(it.get("temperature", 28.0)),
                rain_probability=float(it.get("rain_probability", 20.0)),
                wind_speed=float(it.get("wind_speed", 15.0)),
                condition=str(it.get("condition", "Partly Cloudy")),
                rainfall_amount_mm=float(it.get("rainfall_amount_mm", 0.0)),
            )
        )
    return res
