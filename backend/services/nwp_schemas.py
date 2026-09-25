"""Numerical Weather Prediction (NWP) Schemas & Model Contracts.

Phase 27: NWP / GFS / WRF Integration Readiness.
Defines structured schemas for GFS (Global Forecast System) and WRF (Weather Research and Forecasting)
model products, preserving model run cycles, lead times, physical variables, provenance, and freshness.
Includes multi-model comparison structures adhering to the strict non-averaging principle.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class NWPModelName(str, Enum):
    """Supported Numerical Weather Prediction model identifiers."""
    GFS = "GFS"          # NOAA National Centers for Environmental Prediction (0.25° grid)
    WRF = "WRF"          # Weather Research and Forecasting Model (Regional High-Resolution 3km-9km)
    ECMWF = "ECMWF"      # European Centre for Medium-Range Weather Forecasts (IFS / AIFS)
    NCUM = "NCUM"        # NCMRWF Unified Model (India MoES Operational NWP)


class NWPVariables(BaseModel):
    """Physical atmospheric variables forecasted by an NWP model run."""
    temperature_c: float = Field(description="Surface 2m temperature in Celsius")
    temp_min_c: Optional[float] = Field(default=None, description="Minimum temperature in Celsius")
    temp_max_c: Optional[float] = Field(default=None, description="Maximum temperature in Celsius")
    precipitation_mm: float = Field(default=0.0, ge=0.0, description="Accumulated or period precipitation in mm")
    precip_total_mm: Optional[float] = Field(default=None, ge=0.0, description="Accumulated total precipitation in mm")
    precip_1h_mm: Optional[float] = Field(default=None, ge=0.0, description="1-hour precipitation accumulation in mm")
    rain_probability_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Derived or ensemble rain probability percentage")
    wind_speed_kmh: float = Field(ge=0.0, description="10m wind speed in km/h")
    wind_gust_kmh: Optional[float] = Field(default=None, ge=0.0, description="10m wind gust speed in km/h")
    wind_direction_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0, description="Wind direction in degrees (0-360)")
    pressure_hpa: Optional[float] = Field(default=None, description="Mean sea-level pressure in hPa")
    relative_humidity_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="2m relative humidity percentage")
    humidity_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Relative humidity percentage alias")
    cloud_cover_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Total cloud cover percentage")
    cape_jkg: Optional[float] = Field(default=None, ge=0.0, description="Convective Available Potential Energy in J/kg")
    condition: Optional[str] = Field(default="Clear", description="Physical condition string derived from cloud/precip")

    def __init__(self, **data: Any):
        if "humidity_pct" in data and "relative_humidity_pct" not in data:
            data["relative_humidity_pct"] = data["humidity_pct"]
        elif "relative_humidity_pct" in data and "humidity_pct" not in data:
            data["humidity_pct"] = data["relative_humidity_pct"]
        super().__init__(**data)

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.model_fields:
            return getattr(self, item)
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default


class NWPProvenance(BaseModel):
    """Detailed provenance tracking for Numerical Weather Prediction models."""
    provider_id: str = Field(description="Ingesting provider or source system")
    model_name: str = Field(description="Numerical model name e.g. GFS, WRF")
    model_run: Optional[str] = Field(default=None, description="Run cycle, e.g. '00Z', '06Z', '12Z', '18Z'")
    initialization_time: Optional[Union[datetime, str]] = None
    ingested_at: Optional[Union[datetime, str]] = None
    grid_resolution: Optional[str] = None
    institution: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        return self.metadata.get(item)

    def get(self, item: str, default: Any = None) -> Any:
        val = getattr(self, item, None)
        if val is not None:
            return val
        return self.metadata.get(item, default)


class NormalizedNWPForecastItem(BaseModel):
    """Normalized NWP forecast timestep with full provenance and run cycle metadata.

    Guarantees strict preservation of model-specific dynamics without blending or averaging.
    """
    model_name: Union[NWPModelName, str] = Field(description="Model identifier: GFS, WRF, NCUM, ECMWF")
    model_run: Optional[str] = Field(default=None, description="Run cycle identifier e.g., '2026-09-25T12:00:00Z' or '12Z'")
    initialization_time: Union[datetime, str] = Field(description="Model run initialization ISO 8601 UTC timestamp")
    forecast_lead_time_hours: int = Field(default=0, ge=0, description="Forecast step lead time from initialization in hours")
    valid_time: Union[datetime, str] = Field(description="Target valid time ISO 8601 UTC timestamp")
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    location_name: str = Field(default="Coimbatore")
    variables: NWPVariables = Field(description="Atmospheric parameter values at valid_time")
    source: str = Field(description="Authoritative source description e.g., 'NOAA NCEP GFS 0.25°'")
    freshness: str = Field(default="FRESH", description="Freshness: FRESH, AGING, STALE, UNAVAILABLE")
    provenance: Union[NWPProvenance, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Detailed provenance telemetry: grid resolution, model physics, cycle, ingest timestamp"
    )
    authority_level: str = Field(
        default="nwp_model_guidance",
        description="Data classification: distinct from primary_authoritative official warnings"
    )
    retrieved_at: Union[datetime, str] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Local ingestion timestamp"
    )

    def __init__(self, **data: Any):
        if "forecast_lead_hours" in data and "forecast_lead_time_hours" not in data:
            data["forecast_lead_time_hours"] = data.pop("forecast_lead_hours")

        # Ensure provenance is an NWPProvenance instance
        prov = data.get("provenance")
        m_val = data.get("model_name")
        m_str = m_val.value if hasattr(m_val, "value") else str(m_val)
        if not prov:
            data["provenance"] = NWPProvenance(
                provider_id=str(data.get("source", "NWP")),
                model_name=m_str,
                model_run=str(data.get("model_run", "CURRENT")),
                initialization_time=data.get("initialization_time")
            )
        elif isinstance(prov, dict):
            data["provenance"] = NWPProvenance(
                provider_id=prov.get("provider_id", str(data.get("source", "NWP"))),
                model_name=prov.get("model_name", m_str),
                model_run=prov.get("model_run", str(data.get("model_run", "CURRENT"))),
                initialization_time=prov.get("initialization_time", data.get("initialization_time")),
                metadata=prov
            )

        super().__init__(**data)

    @property
    def forecast_lead_hours(self) -> int:
        return self.forecast_lead_time_hours

    # Convenience properties for backward compatibility
    @property
    def temperature(self) -> float:
        return self.variables.temperature_c

    @property
    def precipitation(self) -> float:
        return self.variables.precipitation_mm

    @property
    def rain_probability(self) -> float:
        return self.variables.rain_probability_pct if self.variables.rain_probability_pct is not None else 0.0

    @property
    def wind_speed(self) -> float:
        return self.variables.wind_speed_kmh

    @property
    def condition(self) -> str:
        return self.variables.condition or "Clear"

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.model_fields:
            return getattr(self, item)
        if hasattr(self.variables, item):
            return getattr(self.variables, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.model_fields or hasattr(self.variables, item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def to_normalized_forecast_item(self):
        """Converts to general NormalizedForecastItem for standard forecast consumers."""
        from backend.services.schemas import NormalizedForecastItem
        v_time = self.valid_time.isoformat() if isinstance(self.valid_time, datetime) else str(self.valid_time)
        init_time = self.initialization_time.isoformat() if isinstance(self.initialization_time, datetime) else str(self.initialization_time)
        ret_time = self.retrieved_at.isoformat() if isinstance(self.retrieved_at, datetime) else str(self.retrieved_at)
        m_str = self.model_name.value if hasattr(self.model_name, "value") else str(self.model_name)

        return NormalizedForecastItem(
            forecast_time=v_time,
            forecast_for=v_time,
            temperature_c=self.variables.temperature_c,
            temp_min_c=self.variables.temp_min_c,
            temp_max_c=self.variables.temp_max_c,
            rain_probability_pct=self.variables.rain_probability_pct or (80.0 if self.variables.precipitation_mm > 5.0 else (40.0 if self.variables.precipitation_mm > 0.5 else 10.0)),
            rainfall_mm=self.variables.precipitation_mm,
            humidity_pct=self.variables.relative_humidity_pct or self.variables.humidity_pct,
            wind_speed_kmh=self.variables.wind_speed_kmh,
            wind_direction_deg=self.variables.wind_direction_deg,
            condition=self.variables.condition or "Clear",
            source=f"{self.source} ({m_str} +{self.forecast_lead_time_hours}h)",
            issued_at=init_time,
            retrieved_at=ret_time,
            freshness_status=self.freshness,
            completeness_status="COMPLETE"
        )

    def to_ai_forecast_item(self):
        """Converts to Person 1 AI reasoning model."""
        from ai.models import ForecastItem as AIForecastItem
        v_time = self.valid_time if isinstance(self.valid_time, datetime) else datetime.fromisoformat(str(self.valid_time))
        return AIForecastItem(
            time=v_time,
            temperature=self.variables.temperature_c,
            rain_probability=self.variables.rain_probability_pct or (80.0 if self.variables.precipitation_mm > 5.0 else (40.0 if self.variables.precipitation_mm > 0.5 else 10.0)),
            wind_speed=self.variables.wind_speed_kmh,
            condition=self.variables.condition or "Clear",
            rainfall_amount_mm=self.variables.precipitation_mm
        )


class NWPModelComparisonModelEntry(BaseModel):
    """Discrete single model entry at a specific valid timestep."""
    model_name: Union[NWPModelName, str]
    temperature_c: float
    precipitation_mm: float
    wind_speed_kmh: float
    condition: Optional[str] = None


class NWPModelComparisonItem(BaseModel):
    """Timestep comparison across multiple discrete NWP models.

    Values are NEVER averaged across models to preserve distinct physical atmospheric formulations.
    """
    lead_time_hours: int = 0
    valid_time: str
    models: List[NWPModelComparisonModelEntry] = Field(default_factory=list)
    model_values: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Discrete raw parameters per model (e.g. {'GFS': {...}, 'WRF': {...}})"
    )
    temperature_spread_c: float = Field(description="Max temperature - Min temperature across models")
    precipitation_spread_mm: float = Field(description="Max precipitation - Min precipitation across models")
    wind_speed_spread_kmh: float = Field(description="Max wind speed - Min wind speed across models")
    divergence_level: str = Field(description="LOW, MODERATE, or HIGH spread classification")
    divergence_detected: bool = False
    consensus_notes: List[str] = Field(default_factory=list, description="Diagnostic notes on model agreement/divergence")

    def __init__(self, **data: Any):
        div = data.get("divergence_level", "LOW")
        if "divergence_detected" not in data:
            data["divergence_detected"] = (div in ("HIGH", "MODERATE"))
        super().__init__(**data)


class NWPModelComparison(BaseModel):
    """Composite multi-model NWP spread and consensus report.

    Strict Non-Averaging Principle:
    Different models use distinct convective parameterization schemes (e.g., Kain-Fritsch vs Grell-Freitas)
    and horizontal grids. Blending them into an arithmetic mean produces unphysical artifacts.
    This report surfaces divergence and physical consensus rather than smoothed averages.
    """
    location_name: str
    latitude: float
    longitude: float
    compared_at: str
    models_evaluated: List[str] = Field(default_factory=list)
    models_compared: List[str] = Field(default_factory=list)
    lead_times: List[NWPModelComparisonItem] = Field(default_factory=list)
    comparisons: List[NWPModelComparisonItem] = Field(default_factory=list)
    temperature_max_spread_c: float = 0.0
    precipitation_max_spread_mm: float = 0.0
    wind_speed_max_spread_kmh: float = 0.0
    overall_divergence: str = "LOW"
    high_spread: bool = False
    spread_summary: str = ""
    consensus_summary: str = ""
    strictly_non_averaged: bool = True
    methodology: str = (
        "Strict Policy: NWP numerical forecasts are physically evaluated as discrete guidance. "
        "Strictly non-averaged: Models are never blindly averaged with each other or with empirical station observations "
        "to prevent dilution of extreme meteorological signals."
    )
    non_averaging_policy: str = (
        "Strict Policy: NWP numerical forecasts are physically evaluated as discrete guidance. "
        "Strictly non-averaged: Models are never blindly averaged with each other or with empirical station observations "
        "to prevent dilution of extreme meteorological signals."
    )
    official_warning_precedence: str = (
        "Safety Rule: Official IMD warnings supersede all NWP model guidance. "
        "Numerical guidance cannot downgrade or dismiss official warnings."
    )
    source: str = "NWP_MULTI_MODEL_COMPARISON"

    def __init__(self, **data: Any):
        if "models_evaluated" in data and "models_compared" not in data:
            data["models_compared"] = data["models_evaluated"]
        elif "models_compared" in data and "models_evaluated" not in data:
            data["models_evaluated"] = data["models_compared"]

        if "lead_times" in data and "comparisons" not in data:
            data["comparisons"] = data["lead_times"]
        elif "comparisons" in data and "lead_times" not in data:
            data["lead_times"] = data["comparisons"]

        if "consensus_summary" in data and "spread_summary" not in data:
            data["spread_summary"] = data["consensus_summary"]
        elif "spread_summary" in data and "consensus_summary" not in data:
            data["consensus_summary"] = data["spread_summary"]

        if "overall_divergence" in data and "high_spread" not in data:
            data["high_spread"] = (data["overall_divergence"] == "HIGH")

        super().__init__(**data)


class NWPStatusResponse(BaseModel):
    """Configuration readiness status of NWP provider infrastructure."""
    nwp_enabled: bool
    models: Dict[str, Dict[str, Any]] = Field(
        description="Status per model: 'NOT_CONFIGURED', 'HEALTHY', or 'DEGRADED'"
    )
    message: str
    safety_rule: str = "Official IMD warnings take unconditional priority over all NWP numerical guidance."
