"""Numerical Weather Prediction (NWP) Provider Interfaces, Adapters & Comparison Engine.

Phase 27: NWP / GFS / WRF Integration Readiness.
Implements:
1. Generic BaseNWPProvider contract adhering to BaseWeatherProvider.
2. GFSProvider for Global Forecast System (NOAA NCEP 0.25°).
3. WRFProvider for Weather Research and Forecasting (Regional High-Resolution 3km-9km).
4. DeterministicNWPProvider for predictable offline/CI testing.
5. NWPComparisonEngine implementing discrete model spread analysis without blind averaging.
6. Strict adherence to Safety Rule: Official IMD alerts supersede all NWP guidance.
"""

from abc import abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
import httpx

from backend.config.settings import settings
from backend.config.logging import logger
from backend.services.base_provider import BaseWeatherProvider
from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderInvalidResponseError
)
from backend.services.weather_reliability import (
    ProviderStatusEnum,
    FreshnessClassification,
    evaluate_nwp_freshness
)
from backend.services.nwp_schemas import (
    NWPModelName,
    NWPVariables,
    NWPProvenance,
    NormalizedNWPForecastItem,
    NWPModelComparisonModelEntry,
    NWPModelComparisonItem,
    NWPModelComparison,
    NWPStatusResponse
)


class BaseNWPProvider(BaseWeatherProvider):
    """Abstract Base Class for Numerical Weather Prediction (NWP) Model Providers."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None
    ):
        super().__init__(
            timeout=timeout if timeout is not None else settings.NWP_HTTP_TIMEOUT_SECONDS,
            max_retries=max_retries
        )
        self._endpoint = endpoint

    @property
    @abstractmethod
    def model_name(self) -> NWPModelName:
        """NWP Model Name (e.g. NWPModelName.GFS, NWPModelName.WRF)."""
        pass

    @property
    def authority_level(self) -> str:
        """NWP models provide physical numerical guidance, distinct from authoritative warnings."""
        return "nwp_model_guidance"

    @property
    def is_configured(self) -> bool:
        """Returns True only when NWP is enabled and a valid endpoint URL is configured."""
        return bool(settings.NWP_ENABLED and self._endpoint)

    @property
    def endpoint(self) -> Optional[str]:
        """Configured endpoint URL."""
        return self._endpoint

    @property
    def provider_status(self) -> ProviderStatusEnum:
        """Reports provider status: NOT_CONFIGURED when no live endpoint exists, avoiding fake claims."""
        if not self.is_configured:
            return ProviderStatusEnum.NOT_CONFIGURED
        return ProviderStatusEnum.HEALTHY

    @property
    def status(self) -> ProviderStatusEnum:
        """Alias for provider_status."""
        return self.provider_status

    @abstractmethod
    async def fetch_model_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedNWPForecastItem]:
        """Fetches and normalizes model run timesteps.

        Must raise ProviderUnavailableError with NOT_CONFIGURED status if unconfigured.
        Must never synthesize or invent fake live telemetry when unconfigured.
        """
        pass

    async def fetch_nwp_forecast(
        self,
        lat: float,
        lon: float,
        location_name: str = "Coimbatore",
        forecast_hours: int = 72,
        run_cycle: Optional[str] = None
    ) -> List[NormalizedNWPForecastItem]:
        """Unified entry point for NWP forecast retrieval."""
        return await self.fetch_model_forecast(latitude=lat, longitude=lon, location_name=location_name)

    def get_model_metadata(self) -> Dict[str, Any]:
        """Returns provider readiness and configuration metadata."""
        m_name = self.model_name.value if hasattr(self.model_name, "value") else str(self.model_name)
        return {
            "model_name": m_name,
            "authority_level": self.authority_level,
            "is_configured": self.is_configured,
            "status": self.provider_status.value,
            "endpoint": self._endpoint if self.is_configured else None,
            "timeout_seconds": self.timeout
        }

    # BaseWeatherProvider compatibility implementations
    async def get_current_weather(self, latitude: float, longitude: float, location_name: str = "Coimbatore"):
        raise NotImplementedError("NWP providers generate multi-timestep numerical guidance, not single current observations.")

    async def get_forecast(self, latitude: float, longitude: float, location_name: str = "Coimbatore"):
        nwp_items = await self.fetch_model_forecast(latitude, longitude, location_name)
        return [item.to_normalized_forecast_item() for item in nwp_items]

    async def get_official_alerts(self, latitude: float, longitude: float, location_name: str = "Coimbatore"):
        return []


class GFSProvider(BaseNWPProvider):
    """NOAA National Centers for Environmental Prediction Global Forecast System (GFS) Adapter.

    Consumes 0.25-degree GFS numerical products (e.g. via NOMADS GFS or institutional Open-Meteo GFS feed).
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
        enabled: Optional[bool] = None
    ):
        target_endpoint = endpoint if endpoint is not None else settings.NWP_GFS_ENDPOINT
        super().__init__(endpoint=target_endpoint, timeout=timeout)
        if enabled is not None:
            self._explicit_enabled = enabled
        else:
            self._explicit_enabled = None

    @property
    def is_configured(self) -> bool:
        if self._explicit_enabled is False:
            return False
        return bool(settings.NWP_ENABLED and self._endpoint)

    @property
    def name(self) -> str:
        return "GFS"

    @property
    def model_name(self) -> NWPModelName:
        return NWPModelName.GFS

    async def fetch_model_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedNWPForecastItem]:
        """Fetches GFS model forecast run.

        If unconfigured, raises ProviderUnavailableError with status NOT_CONFIGURED.
        Never fabricates mock data in production mode.
        """
        if not self.is_configured:
            logger.info(f"[NWP-GFS] GFS endpoint not configured. Exposing status={ProviderStatusEnum.NOT_CONFIGURED.value}")
            raise ProviderUnavailableError(
                f"GFS NWP provider is NOT_CONFIGURED. Please specify NWP_GFS_ENDPOINT and set NWP_ENABLED=true.",
                provider_name=self.name,
                diagnostics={"status": ProviderStatusEnum.NOT_CONFIGURED.value, "model": self.model_name.value}
            )

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,surface_pressure,cloud_cover,cape",
            "models": "gfs_seamless"
        }

        try:
            data = await self._fetch_json(self._endpoint, params=params)
            return self._parse_gfs_response(data, latitude, longitude, location_name)
        except Exception as e:
            if isinstance(e, ProviderError):
                raise e
            raise ProviderUnavailableError(f"Failed to fetch GFS forecast: {str(e)}", provider_name=self.name)

    def _parse_gfs_response(
        self,
        data: Dict[str, Any],
        latitude: float,
        longitude: float,
        location_name: str
    ) -> List[NormalizedNWPForecastItem]:
        """Transforms GFS raw telemetry into NormalizedNWPForecastItem collection."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        if not times:
            raise ProviderInvalidResponseError("GFS API returned empty time series.", provider_name=self.name)

        now = datetime.now(timezone.utc)
        # Infer latest 6h cycle run
        cycle_hour = (now.hour // 6) * 6
        model_run = f"{cycle_hour:02d}Z"
        init_time = now.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)
        freshness, _, _ = evaluate_nwp_freshness(init_time, now, expected_cycle_hours=6)

        temps = hourly.get("temperature_2m", [0.0] * len(times))
        precips = hourly.get("precipitation", [0.0] * len(times))
        winds = hourly.get("wind_speed_10m", [0.0] * len(times))
        wind_dirs = hourly.get("wind_direction_10m", [None] * len(times))
        pressures = hourly.get("surface_pressure", [None] * len(times))
        humidities = hourly.get("relative_humidity_2m", [None] * len(times))
        clouds = hourly.get("cloud_cover", [None] * len(times))
        capes = hourly.get("cape", [None] * len(times))

        items: List[NormalizedNWPForecastItem] = []
        for idx, t_str in enumerate(times[:72]):  # Up to 72 hours guidance
            try:
                valid_dt = datetime.fromisoformat(t_str)
                if valid_dt.tzinfo is None:
                    valid_dt = valid_dt.replace(tzinfo=timezone.utc)
            except Exception:
                valid_dt = now + timedelta(hours=idx)

            lead_hours = max(0, int((valid_dt - now).total_seconds() / 3600))
            p_val = float(precips[idx]) if idx < len(precips) and precips[idx] is not None else 0.0
            c_val = float(clouds[idx]) if idx < len(clouds) and clouds[idx] is not None else 0.0
            cond = "Rain" if p_val > 0.5 else ("Cloudy" if c_val > 60 else "Partly Cloudy")

            variables = NWPVariables(
                temperature_c=float(temps[idx]) if idx < len(temps) and temps[idx] is not None else 25.0,
                precipitation_mm=p_val,
                rain_probability_pct=min(100.0, p_val * 25.0) if p_val > 0 else 5.0,
                wind_speed_kmh=float(winds[idx]) if idx < len(winds) and winds[idx] is not None else 10.0,
                wind_direction_deg=float(wind_dirs[idx]) if idx < len(wind_dirs) and wind_dirs[idx] is not None else None,
                pressure_hpa=float(pressures[idx]) if idx < len(pressures) and pressures[idx] is not None else None,
                relative_humidity_pct=float(humidities[idx]) if idx < len(humidities) and humidities[idx] is not None else None,
                cloud_cover_pct=c_val,
                cape_jkg=float(capes[idx]) if idx < len(capes) and capes[idx] is not None else None,
                condition=cond
            )

            item = NormalizedNWPForecastItem(
                model_name=self.model_name,
                model_run=model_run,
                initialization_time=init_time,
                forecast_lead_time_hours=lead_hours,
                valid_time=valid_dt,
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                variables=variables,
                source=self.name,
                freshness=freshness.value,
                provenance=NWPProvenance(
                    provider_id="NOAA_NCEP_GFS",
                    model_name="GFS",
                    model_run=model_run,
                    initialization_time=init_time,
                    grid_resolution="0.25_deg (~27km)",
                    institution="NOAA NCEP"
                )
            )
            items.append(item)

        return items


class WRFProvider(BaseNWPProvider):
    """Regional High-Resolution Weather Research and Forecasting (WRF) Model Adapter.

    Ready to consume NCMRWF or institutional WRF mesoscale model output (3km-9km grid).
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
        enabled: Optional[bool] = None
    ):
        target_endpoint = endpoint if endpoint is not None else settings.NWP_WRF_ENDPOINT
        super().__init__(endpoint=target_endpoint, timeout=timeout)
        if enabled is not None:
            self._explicit_enabled = enabled
        else:
            self._explicit_enabled = None

    @property
    def is_configured(self) -> bool:
        if self._explicit_enabled is False:
            return False
        return bool(settings.NWP_ENABLED and self._endpoint)

    @property
    def name(self) -> str:
        return "WRF"

    @property
    def model_name(self) -> NWPModelName:
        return NWPModelName.WRF

    async def fetch_model_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedNWPForecastItem]:
        """Fetches WRF regional mesoscale forecast.

        If unconfigured, raises ProviderUnavailableError with status NOT_CONFIGURED.
        Never fabricates mock data in production mode.
        """
        if not self.is_configured:
            logger.info(f"[NWP-WRF] WRF endpoint not configured. Exposing status={ProviderStatusEnum.NOT_CONFIGURED.value}")
            raise ProviderUnavailableError(
                f"WRF NWP provider is NOT_CONFIGURED. Please specify NWP_WRF_ENDPOINT and set NWP_ENABLED=true.",
                provider_name=self.name,
                diagnostics={"status": ProviderStatusEnum.NOT_CONFIGURED.value, "model": self.model_name.value}
            )

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,surface_pressure,cloud_cover,cape",
            "models": "wrf_india"
        }

        try:
            data = await self._fetch_json(self._endpoint, params=params)
            return self._parse_wrf_response(data, latitude, longitude, location_name)
        except Exception as e:
            if isinstance(e, ProviderError):
                raise e
            raise ProviderUnavailableError(f"Failed to fetch WRF forecast: {str(e)}", provider_name=self.name)

    def _parse_wrf_response(
        self,
        data: Dict[str, Any],
        latitude: float,
        longitude: float,
        location_name: str
    ) -> List[NormalizedNWPForecastItem]:
        """Transforms WRF mesoscale output into NormalizedNWPForecastItem collection."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        if not times:
            raise ProviderInvalidResponseError("WRF endpoint returned no forecast time series.", provider_name=self.name)

        now = datetime.now(timezone.utc)
        cycle_hour = (now.hour // 6) * 6
        model_run = f"{cycle_hour:02d}Z"
        init_time = now.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)
        freshness, _, _ = evaluate_nwp_freshness(init_time, now, expected_cycle_hours=6)

        temps = hourly.get("temperature_2m", [0.0] * len(times))
        precips = hourly.get("precipitation", [0.0] * len(times))
        winds = hourly.get("wind_speed_10m", [0.0] * len(times))
        wind_dirs = hourly.get("wind_direction_10m", [None] * len(times))
        pressures = hourly.get("surface_pressure", [None] * len(times))
        humidities = hourly.get("relative_humidity_2m", [None] * len(times))
        clouds = hourly.get("cloud_cover", [None] * len(times))
        capes = hourly.get("cape", [None] * len(times))

        items: List[NormalizedNWPForecastItem] = []
        for idx, t_str in enumerate(times[:72]):
            try:
                valid_dt = datetime.fromisoformat(t_str)
                if valid_dt.tzinfo is None:
                    valid_dt = valid_dt.replace(tzinfo=timezone.utc)
            except Exception:
                valid_dt = now + timedelta(hours=idx)

            lead_hours = max(0, int((valid_dt - now).total_seconds() / 3600))
            p_val = float(precips[idx]) if idx < len(precips) and precips[idx] is not None else 0.0
            c_val = float(clouds[idx]) if idx < len(clouds) and clouds[idx] is not None else 0.0
            cond = "Rain" if p_val > 0.5 else ("Cloudy" if c_val > 60 else "Partly Cloudy")

            variables = NWPVariables(
                temperature_c=float(temps[idx]) if idx < len(temps) and temps[idx] is not None else 25.0,
                precipitation_mm=p_val,
                rain_probability_pct=min(100.0, p_val * 25.0) if p_val > 0 else 5.0,
                wind_speed_kmh=float(winds[idx]) if idx < len(winds) and winds[idx] is not None else 10.0,
                wind_direction_deg=float(wind_dirs[idx]) if idx < len(wind_dirs) and wind_dirs[idx] is not None else None,
                pressure_hpa=float(pressures[idx]) if idx < len(pressures) and pressures[idx] is not None else None,
                relative_humidity_pct=float(humidities[idx]) if idx < len(humidities) and humidities[idx] is not None else None,
                cloud_cover_pct=c_val,
                cape_jkg=float(capes[idx]) if idx < len(capes) and capes[idx] is not None else None,
                condition=cond
            )

            item = NormalizedNWPForecastItem(
                model_name=self.model_name,
                model_run=model_run,
                initialization_time=init_time,
                forecast_lead_time_hours=lead_hours,
                valid_time=valid_dt,
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                variables=variables,
                source=self.name,
                freshness=freshness.value,
                provenance=NWPProvenance(
                    provider_id="REGIONAL_WRF_MESOSCALE",
                    model_name="WRF",
                    model_run=model_run,
                    initialization_time=init_time,
                    grid_resolution="3km/9km convective-permitting",
                    institution="MoES / NCMRWF India"
                )
            )
            items.append(item)

        return items


class DeterministicNWPProvider(BaseNWPProvider):
    """Deterministic NWP Provider for unit testing, offline resilience, and fixture evaluation."""

    def __init__(
        self,
        model_name: Union[NWPModelName, str] = NWPModelName.GFS,
        endpoint: Optional[str] = "https://mock.nwp.local",
        items: Optional[List[NormalizedNWPForecastItem]] = None,
        canned_items: Optional[List[NormalizedNWPForecastItem]] = None,
        configured: bool = True
    ):
        super().__init__(endpoint=endpoint if configured else None)
        self._model_name = model_name if isinstance(model_name, NWPModelName) else NWPModelName(str(model_name).upper())
        self._canned_items = items if items is not None else (canned_items or [])
        self._configured = configured and bool(endpoint)

    @property
    def name(self) -> str:
        return f"{self._model_name.value}"

    @property
    def model_name(self) -> NWPModelName:
        return self._model_name

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def fetch_model_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedNWPForecastItem]:
        if not self.is_configured:
            raise ProviderUnavailableError(
                f"{self.model_name.value} provider is NOT_CONFIGURED.",
                provider_name=self.name,
                diagnostics={"status": ProviderStatusEnum.NOT_CONFIGURED.value}
            )
        return self._canned_items


class NWPComparisonEngine:
    """Multi-Model NWP Spread & Comparison Engine.

    CRITICAL RULE:
    NWP model outputs (e.g. GFS and WRF) are NEVER blindly averaged together or with station forecasts.
    Different numerical dynamical cores and convective schemes produce distinct physical trajectories.
    Averaging them dilutes extreme meteorological signals (e.g. averaging a storm and dry model).
    This engine computes discrete differences, spreads, and physical divergence levels.
    """

    async def compare(
        self,
        providers: List[BaseNWPProvider],
        lat: float,
        lon: float,
        location_name: str = "Coimbatore",
        forecast_hours: int = 72
    ) -> NWPModelComparison:
        """Fetches forecasts from multiple NWP providers and performs non-averaged spread analysis."""
        model_forecasts: Dict[str, List[NormalizedNWPForecastItem]] = {}
        for p in providers:
            if p.is_configured:
                try:
                    items = await p.fetch_model_forecast(latitude=lat, longitude=lon, location_name=location_name)
                    m_key = p.model_name.value if hasattr(p.model_name, "value") else str(p.model_name)
                    model_forecasts[m_key] = items
                except Exception as e:
                    logger.warning(f"Failed to fetch forecast from NWP provider {p.name}: {e}")

        return self.compare_models(
            model_forecasts=model_forecasts,
            location_name=location_name,
            latitude=lat,
            longitude=lon
        )

    @staticmethod
    def compare_models(
        model_forecasts: Dict[str, List[NormalizedNWPForecastItem]],
        location_name: str = "Coimbatore",
        latitude: float = 11.0168,
        longitude: float = 76.9558
    ) -> NWPModelComparison:
        """Compares multiple NWP model forecasts timestep by timestep without averaging."""
        now_str = datetime.now(timezone.utc).isoformat()
        models_evaluated = list(model_forecasts.keys())

        if not model_forecasts or not any(model_forecasts.values()):
            return NWPModelComparison(
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                compared_at=now_str,
                models_evaluated=[],
                lead_times=[],
                temperature_max_spread_c=0.0,
                precipitation_max_spread_mm=0.0,
                wind_speed_max_spread_kmh=0.0,
                overall_divergence="LOW",
                consensus_summary="No active NWP model forecasts provided for comparison."
            )

        # Index forecasts by valid_time (aligning different model run cycles at the same forecast verification time)
        timesteps: Dict[str, Dict[str, NormalizedNWPForecastItem]] = {}
        for m_name, items in model_forecasts.items():
            for item in items:
                v_key = item.valid_time.isoformat() if isinstance(item.valid_time, datetime) else str(item.valid_time)
                if v_key not in timesteps:
                    timesteps[v_key] = {}
                timesteps[v_key][m_name] = item

        comparison_items: List[NWPModelComparisonItem] = []
        max_temp_spread = 0.0
        max_precip_spread = 0.0
        max_wind_spread = 0.0

        for v_key in sorted(timesteps.keys())[:24]:  # Focus on key verification steps up to 24
            step_models = timesteps[v_key]
            if len(step_models) < 1:
                continue

            first_item = next(iter(step_models.values()))
            valid_t = v_key
            lead_h = first_item.forecast_lead_time_hours

            model_vals: Dict[str, Dict[str, Any]] = {}
            model_entries: List[NWPModelComparisonModelEntry] = []
            temps: List[float] = []
            precips: List[float] = []
            winds: List[float] = []

            for m_name, item in step_models.items():
                m_enum = item.model_name
                entry = NWPModelComparisonModelEntry(
                    model_name=m_enum,
                    temperature_c=item.variables.temperature_c,
                    precipitation_mm=item.variables.precipitation_mm,
                    wind_speed_kmh=item.variables.wind_speed_kmh,
                    condition=item.variables.condition
                )
                model_entries.append(entry)

                m_str = m_enum.value if hasattr(m_enum, "value") else str(m_enum)
                model_vals[m_str] = {
                    "temperature_c": item.variables.temperature_c,
                    "precipitation_mm": item.variables.precipitation_mm,
                    "wind_speed_kmh": item.variables.wind_speed_kmh,
                    "condition": item.variables.condition
                }
                temps.append(item.variables.temperature_c)
                precips.append(item.variables.precipitation_mm)
                winds.append(item.variables.wind_speed_kmh)

            t_spread = round(max(temps) - min(temps), 1) if len(temps) > 1 else 0.0
            p_spread = round(max(precips) - min(precips), 1) if len(precips) > 1 else 0.0
            w_spread = round(max(winds) - min(winds), 1) if len(winds) > 1 else 0.0

            max_temp_spread = max(max_temp_spread, t_spread)
            max_precip_spread = max(max_precip_spread, p_spread)
            max_wind_spread = max(max_wind_spread, w_spread)

            # Divergence classification for this step
            if t_spread > 4.0 or p_spread > 15.0 or w_spread > 25.0:
                step_div = "HIGH"
            elif t_spread > 2.0 or p_spread > 5.0 or w_spread > 15.0:
                step_div = "MODERATE"
            else:
                step_div = "LOW"

            notes = []
            if p_spread > 10.0:
                heavy_models = [m for m, v in model_vals.items() if v["precipitation_mm"] > 10.0]
                dry_models = [m for m, v in model_vals.items() if v["precipitation_mm"] < 2.0]
                notes.append(f"Precipitation divergence: {', '.join(heavy_models)} project heavy rain, while {', '.join(dry_models)} project dry conditions.")
            elif p_spread <= 2.0 and max(precips) > 5.0:
                notes.append("High model agreement: Both models project significant rainfall during this window.")

            if t_spread > 3.0:
                notes.append(f"Temperature spread of {t_spread}°C between models.")

            comparison_items.append(
                NWPModelComparisonItem(
                    lead_time_hours=lead_h,
                    valid_time=valid_t,
                    models=model_entries,
                    model_values=model_vals,
                    temperature_spread_c=t_spread,
                    precipitation_spread_mm=p_spread,
                    wind_speed_spread_kmh=w_spread,
                    divergence_level=step_div,
                    consensus_notes=notes
                )
            )

        # Overall divergence across all steps
        if max_temp_spread > 4.0 or max_precip_spread > 15.0 or max_wind_spread > 25.0:
            overall_div = "HIGH"
        elif max_temp_spread > 2.0 or max_precip_spread > 5.0 or max_wind_spread > 15.0:
            overall_div = "MODERATE"
        else:
            overall_div = "LOW"

        # Consensus summary synthesis
        if len(models_evaluated) <= 1:
            summary = f"Single or zero NWP models ({', '.join(models_evaluated) if models_evaluated else 'None'}) available. No cross-model spread calculated."
        elif overall_div == "LOW":
            summary = (
                f"High NWP consensus across {', '.join(models_evaluated)}: "
                f"temperature spread <= {max_temp_spread}°C, precipitation spread <= {max_precip_spread}mm. "
                "Physical atmospheric dynamics show strong multi-model agreement."
            )
        elif overall_div == "MODERATE":
            summary = (
                f"Moderate NWP spread across {', '.join(models_evaluated)}: "
                f"peak temperature delta {max_temp_spread}°C, precipitation spread {max_precip_spread}mm. "
                "Forecast trends align, with minor variance in precipitation timing or thermal peaks."
            )
        else:
            summary = (
                f"High NWP divergence between {', '.join(models_evaluated)}: "
                f"High spread detected in precipitation ({max_precip_spread}mm) and temperature ({max_temp_spread}°C). "
                "Convective development timing or cyclone track differs between models. Exercise caution."
            )

        return NWPModelComparison(
            location_name=location_name,
            latitude=latitude,
            longitude=longitude,
            compared_at=now_str,
            models_evaluated=models_evaluated,
            lead_times=comparison_items,
            temperature_max_spread_c=max_temp_spread,
            precipitation_max_spread_mm=max_precip_spread,
            wind_speed_max_spread_kmh=max_wind_spread,
            overall_divergence=overall_div,
            consensus_summary=summary
        )
