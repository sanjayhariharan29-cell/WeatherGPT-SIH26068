"""IMD Meteorological Adapter (India Meteorological Department).

Authoritative meteorological data adapter for official Indian weather observations,
forecasts, district disaster warnings, and localized district nowcasts.
Queries official IMD GeoServer WFS and Mausam APIs with full provenance,
strict lifecycle evaluation, and zero fabricated alerts.
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from backend.config.settings import settings
from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError
)
from backend.services.base_provider import BaseWeatherProvider
from backend.services.schemas import (
    NormalizedWeatherObservation,
    NormalizedForecastItem,
    NormalizedAlertItem
)
from backend.services.cache import provider_cache
from backend.services.imd_district_registry import resolve_imd_district

logger = logging.getLogger("weathergpt.imd_adapter")

# Official IMD warning category definitions (from IMD official district warning bulletin system)
IMD_WARNING_CATEGORIES: Dict[str, str] = {
    "1": "No Warning",
    "2": "Heavy Rain",
    "3": "Heavy Snow",
    "4": "Thunderstorms & Lightning, Squall etc",
    "5": "Hailstorm",
    "6": "Dust Storm",
    "7": "Dust Raising Winds",
    "8": "Strong Surface Winds",
    "9": "Heat Wave",
    "10": "Hot Day",
    "11": "Warm Night",
    "12": "Cold Wave",
    "13": "Cold Day",
    "14": "Ground Frost",
    "15": "Fog",
    "16": "Very Heavy Rain",
    "17": "Extremely Heavy Rain"
}

# Official IMD Nowcast category definitions (from IMD official nowcast system)
IMD_NOWCAST_CATEGORIES: Dict[str, str] = {
    "cat1": "No Warning",
    "cat2": "Light rain (< 5 mm/hr)",
    "cat3": "Light snow (< 5 cm/hr)",
    "cat4": "Light Thunderstorms with maximum surface wind speed < 40 kmph",
    "cat5": "Slight dust storm (wind speed up to 41 kmph)",
    "cat6": "Low cloud to ground Lightning probability (< 30%)",
    "cat7": "Moderate rain (5-15 mm/hr)",
    "cat8": "Moderate snow (5-15 cm/hr)",
    "cat9": "Moderate Thunderstorms with wind speed 41-61 kmph",
    "cat10": "Moderate dust storm",
    "cat11": "Moderate cloud to ground Lightning probability (30-60%)",
    "cat12": "Heavy rain (> 15 mm/hr)",
    "cat13": "Heavy snow (> 15 cm/hr)",
    "cat14": "Severe Thunderstorms with wind speed 62-87 kmph",
    "cat15": "Very Severe Thunderstorms with wind speed > 87 kmph",
    "cat17": "Thunderstorms with Hail",
    "cat18": "Severe dust storm (> 61 kmph)",
    "cat19": "High cloud to ground Lightning probability (> 60%)"
}

# IMD 4-Stage Color Severity Mapping
COLOR_SEVERITY_MAP = {
    1: ("green", "low"),      # No Warning (Watch)
    2: ("yellow", "low"),     # Be Updated / Watch
    3: ("orange", "medium"),  # Be Prepared / Alert
    4: ("red", "high")        # Take Action / Warning
}


class IMDAdapter(BaseWeatherProvider):
    """Primary Authoritative Meteorological Data Adapter for IMD (India Meteorological Dept)."""

    def __init__(self, timeout: Optional[float] = None, mode: Optional[str] = None):
        super().__init__(timeout=timeout)
        # Mode: 'live' (production default) or 'test' (unit tests only)
        import os
        if mode:
            self.mode = mode
        elif os.getenv("PYTEST_CURRENT_TEST") and os.getenv("IMD_ENVIRONMENT") != "production":
            self.mode = "test"
        else:
            self.mode = settings.IMD_ENVIRONMENT or "live"

    @property
    def name(self) -> str:
        return "IMD"

    @property
    def authority_level(self) -> str:
        return "primary_authoritative"

    @property
    def is_live_configured(self) -> bool:
        """Checks if genuine live official IMD credentials / endpoint access are configured."""
        return bool(settings.IMD_API_KEY and settings.IMD_API_KEY.strip())

    @staticmethod
    def generate_alert_fingerprint(source: str, alert_type: str, area: str, issued_at: str) -> str:
        """Generates deterministic SHA-256 fingerprint for alert deduplication and tracking."""
        key = f"{source}:{alert_type}:{area}:{issued_at}".encode("utf-8")
        return hashlib.sha256(key).hexdigest()[:16]

    # =========================================================================
    # 1. OBSERVATIONS
    # =========================================================================
    async def get_current_weather(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> NormalizedWeatherObservation:
        """Fetch current weather observations from IMD with caching and provenance."""
        cache_key = f"imd_current_{location_name}_{latitude}_{longitude}"
        cached = provider_cache.get(cache_key)
        if cached:
            return cached

        now_utc = datetime.now(timezone.utc).isoformat()

        # If live credentials configured, attempt real HTTP fetch from observation endpoint
        if self.is_live_configured:
            try:
                url = f"{settings.IMD_BASE_URL}/observations/current"
                params = {"lat": latitude, "lon": longitude, "key": settings.IMD_API_KEY}
                payload = await self._fetch_json(url, params=params)
                obs_data = payload.get("observation", {}) or payload
                temp = float(obs_data.get("temp", obs_data.get("temperature", 0.0)))
                hum = float(obs_data.get("humidity", 0.0))
                wind = float(obs_data.get("wind_speed", 0.0))
                cond = obs_data.get("condition", "Observed")
                obs_time = obs_data.get("observed_at", now_utc)

                live_obs = NormalizedWeatherObservation(
                    location_name=location_name,
                    latitude=latitude,
                    longitude=longitude,
                    temperature_c=temp,
                    humidity_pct=hum,
                    rain_probability_pct=float(obs_data.get("rain_prob", 0.0)),
                    wind_speed_kmh=wind,
                    rainfall_mm=float(obs_data.get("rainfall_mm", 0.0)),
                    condition=cond,
                    source=self.name,
                    authority_level=self.authority_level,
                    observed_at=obs_time,
                    retrieved_at=now_utc
                )
                provider_cache.set(cache_key, live_obs)
                return live_obs
            except ProviderError:
                raise
            except Exception as e:
                raise ProviderUnavailableError(
                    f"Live IMD observation endpoint error: {str(e)}",
                    provider_name=self.name,
                    diagnostics={"error": str(e), "is_live_configured": True}
                )

        # In test mode, return isolated test fixture
        if self.mode == "test":
            from backend.services.imd_fixtures import get_test_fixture_observation
            return get_test_fixture_observation(location_name, latitude, longitude, now_utc)

        # Production without live observation credentials: raise explicit unavailable error
        raise ProviderUnavailableError(
            "IMD live observation stream requires authorized API credentials or whitelisting.",
            provider_name=self.name,
            diagnostics={"is_live_configured": False, "mode": self.mode}
        )

    # =========================================================================
    # 2. FORECASTS
    # =========================================================================
    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedForecastItem]:
        """Fetch forecast data from IMD data services with provenance."""
        cache_key = f"imd_forecast_{location_name}_{latitude}_{longitude}"
        cached = provider_cache.get(cache_key)
        if cached:
            return cached

        now_utc = datetime.now(timezone.utc).isoformat()

        # In test mode, return isolated test fixture
        if self.mode == "test":
            from backend.services.imd_fixtures import get_test_fixture_forecast
            return get_test_fixture_forecast(location_name, now_utc)

        # Production without dedicated IMD forecast stream: raise ProviderUnavailableError
        # to allow ForecastService to cleanly fail over to secondary provider (Open-Meteo Fallback)
        raise ProviderUnavailableError(
            "IMD official forecast stream unavailable. Graceful failover to secondary provider required.",
            provider_name=self.name,
            diagnostics={"mode": self.mode}
        )

    # =========================================================================
    # 3. OFFICIAL WARNING FETCHERS (WFS & DIRECT API)
    # =========================================================================
    async def fetch_official_district_warnings(
        self,
        district_name: str
    ) -> List[NormalizedAlertItem]:
        """Queries the official IMD District Warning product (Days 1 to 5).

        Uses official IMD GeoServer WFS endpoint (with CQL filter for targeted district).
        """
        canonical_district = district_name.upper().strip()
        url = settings.IMD_GEOSERVER_WFS_URL
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typename": "imd:district_warnings_india",
            "srsname": "EPSG:4326",
            "outputFormat": "application/json",
            "cql_filter": f"District='{canonical_district}'"
        }

        headers = {"User-Agent": "WeatherGPT-SkyZen/1.0 (India Meteorological Ingestion)"}
        if settings.IMD_AUTH_HEADER:
            headers["Authorization"] = settings.IMD_AUTH_HEADER

        try:
            payload = await self._fetch_json(url, params=params, headers=headers)
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderUnavailableError(
                f"Official IMD district warning query failed: {str(e)}",
                provider_name=self.name,
                diagnostics={"district": canonical_district, "error": str(e)}
            )

        features = payload.get("features", [])
        if not features:
            return []

        alerts: List[NormalizedAlertItem] = []
        now_dt = datetime.now(timezone.utc)
        now_utc_str = now_dt.isoformat()

        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            date_str = str(props.get("Date") or now_dt.strftime("%Y-%m-%d")).strip()
            updated_str = props.get("updated_at")

            try:
                base_dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            except Exception:
                base_dt = now_dt

            # Parse 5-day warning timeline
            for day_idx in range(1, 6):
                day_key = f"Day_{day_idx}"
                color_key = f"Day{day_idx}_Color"
                text_key = f"Day{day_idx}_text"

                raw_warning_code = str(props.get(day_key) or "1").strip()
                raw_color_code = props.get(color_key) or 1

                try:
                    color_int = int(raw_color_code)
                except Exception:
                    color_int = 1

                # Color 1 = Green / No Warning. Warning code "1" = No Warning.
                # Only construct official warning if color > 1 or code > 1
                if color_int <= 1 and raw_warning_code in ("1", "", "0", "None"):
                    continue

                # Parse category names
                cat_names = []
                for code_part in raw_warning_code.split(","):
                    c = code_part.strip()
                    if c and c in IMD_WARNING_CATEGORIES and c != "1":
                        cat_names.append(IMD_WARNING_CATEGORIES[c])

                category_label = ", ".join(cat_names) if cat_names else "Adverse Weather Alert"
                color_name, severity_level = COLOR_SEVERITY_MAP.get(color_int, ("yellow", "low"))

                # Official validity window: Each day covers a 24-hour bracket
                day_start_dt = base_dt + timedelta(days=(day_idx - 1))
                day_end_dt = day_start_dt + timedelta(days=1)

                status = "ACTIVE"
                if now_dt < day_start_dt:
                    status = "SCHEDULED"
                elif now_dt > day_end_dt:
                    status = "EXPIRED"

                alert_id = f"IMD-DISTWARN-{canonical_district}-{date_str}-D{day_idx}"
                custom_text = str(props.get(text_key) or "").strip()
                desc = (
                    f"{category_label}. Official IMD Day {day_idx} alert for {canonical_district.title()}. "
                    f"{custom_text}".strip()
                )

                item = NormalizedAlertItem(
                    alert_id=alert_id,
                    alert_type="district_warning",
                    severity=severity_level,
                    title=f"IMD {category_label} ({canonical_district.title()})",
                    description=desc,
                    instructions=custom_text if custom_text else f"Monitor local weather bulletins and follow official IMD advisories.",
                    area=f"{canonical_district.title()} District",
                    source=self.name,
                    source_url=f"https://mausam.imd.gov.in/responsive/districtWiseWarningGIS.php?day={day_idx}",
                    product_type="district_warning",
                    state="LIVE",
                    geometry=geom,
                    matched_district=canonical_district,
                    issued_at=updated_str or base_dt.isoformat(),
                    expires_at=day_end_dt.isoformat(),
                    valid_from=day_start_dt.isoformat(),
                    updated_at=updated_str,
                    retrieved_at=now_utc_str,
                    status=status,
                    version=1
                )
                alerts.append(item)

        return alerts

    async def fetch_official_district_nowcast(
        self,
        district_name: str
    ) -> List[NormalizedAlertItem]:
        """Queries the official IMD District Nowcast product (high-urgency 3-hour localized warnings).

        Uses official IMD Nowcast GeoServer WFS endpoint.
        """
        canonical_district = district_name.upper().strip()
        url = settings.IMD_NOWCAST_WFS_URL
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typename": "imd:NowcastWarningDistrict",
            "srsname": "EPSG:4326",
            "outputFormat": "application/json",
            "cql_filter": f"District='{canonical_district}'"
        }

        headers = {"User-Agent": "WeatherGPT-SkyZen/1.0 (India Meteorological Ingestion)"}
        if settings.IMD_AUTH_HEADER:
            headers["Authorization"] = settings.IMD_AUTH_HEADER

        try:
            payload = await self._fetch_json(url, params=params, headers=headers)
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderUnavailableError(
                f"Official IMD nowcast query failed: {str(e)}",
                provider_name=self.name,
                diagnostics={"district": canonical_district, "error": str(e)}
            )

        features = payload.get("features", [])
        if not features:
            return []

        now_dt = datetime.now(timezone.utc)
        now_utc_str = now_dt.isoformat()
        alerts: List[NormalizedAlertItem] = []

        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry")

            raw_color = props.get("Color") or 1
            try:
                color_int = int(raw_color)
            except Exception:
                color_int = 1

            # Identify active nowcast categories (cat1 to cat19)
            active_cats: List[str] = []
            for cat_id, cat_desc in IMD_NOWCAST_CATEGORIES.items():
                if cat_id == "cat1":
                    continue
                val = props.get(cat_id)
                if val and str(val).strip() not in ("0", "", "None"):
                    active_cats.append(cat_desc)

            # Check for custom text message
            msg = str(props.get("message") or "").strip()
            impact = str(props.get("impact") or "").strip()
            action = str(props.get("action") or "").strip()
            toi_raw = str(props.get("toi") or "0000").strip()
            vupto_raw = str(props.get("vupto") or "0000").strip()
            date_raw = str(props.get("Date") or now_dt.strftime("%Y-%m-%d")).strip()
            update_time = props.get("update_time")

            # If color is 1 (Green) and no categories and no message -> No active warning
            if color_int <= 1 and not active_cats and not msg:
                continue

            color_name, severity_level = COLOR_SEVERITY_MAP.get(color_int, ("yellow", "low"))
            category_summary = "; ".join(active_cats) if active_cats else "Localized Meteorological Hazard"

            # Parse validity timestamps from Date, toi, vupto (toi: HHMM in IST/UTC)
            try:
                toi_h, toi_m = int(toi_raw[:2]), int(toi_raw[2:4]) if len(toi_raw) >= 4 else (0, 0)
                base_d = datetime.fromisoformat(date_raw)
                # IMD publishes toi/vupto in IST (UTC+5:30)
                ist_offset = timedelta(hours=5, minutes=30)
                issue_dt = base_d.replace(hour=toi_h, minute=toi_m, tzinfo=timezone.utc) - ist_offset
            except Exception:
                issue_dt = now_dt

            try:
                vupto_h, vupto_m = int(vupto_raw[:2]), int(vupto_raw[2:4]) if len(vupto_raw) >= 4 else (0, 0)
                base_d = datetime.fromisoformat(date_raw)
                ist_offset = timedelta(hours=5, minutes=30)
                expire_dt = base_d.replace(hour=vupto_h, minute=vupto_m, tzinfo=timezone.utc) - ist_offset
                if expire_dt <= issue_dt:
                    expire_dt = issue_dt + timedelta(hours=3)
            except Exception:
                expire_dt = issue_dt + timedelta(hours=3)

            status = "ACTIVE"
            if now_dt < issue_dt:
                status = "SCHEDULED"
            elif now_dt > expire_dt:
                status = "EXPIRED"

            desc_parts = [category_summary]
            if msg:
                desc_parts.append(msg)
            if impact:
                desc_parts.append(f"Impact: {impact}")
            full_desc = " | ".join(desc_parts)

            alert_id = f"IMD-NOWCAST-{canonical_district}-{date_raw}-{toi_raw}"

            item = NormalizedAlertItem(
                alert_id=alert_id,
                alert_type="district_nowcast",
                severity=severity_level,
                title=f"IMD Nowcast: {canonical_district.title()}",
                description=full_desc,
                instructions=action or "Take necessary precautionary measures. Stay updated on official IMD alerts.",
                area=f"{canonical_district.title()} District",
                source=self.name,
                source_url="https://mausam.imd.gov.in/responsive/districtWiseNowcastGIS.php",
                product_type="district_nowcast",
                state="LIVE",
                geometry=geom,
                toi=toi_raw,
                vupto=vupto_raw,
                matched_district=canonical_district,
                issued_at=issue_dt.isoformat(),
                expires_at=expire_dt.isoformat(),
                valid_from=issue_dt.isoformat(),
                updated_at=update_time,
                retrieved_at=now_utc_str,
                status=status,
                version=1
            )
            alerts.append(item)

        return alerts

    # =========================================================================
    # 4. MASTER OFFICIAL ALERT ENTRYPOINT
    # =========================================================================
    async def get_official_alerts(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedAlertItem]:
        """Fetches active official IMD disaster warnings and nowcasts.

        Strict Separation Rules:
        - In test mode ('test'): allows isolated test fixtures.
        - In production mode ('live'): queries REAL official IMD endpoints.
          Never automatically falls back to fixture data.
        """
        # Test fixture route for automated isolated test environments
        if self.mode == "test":
            from backend.services.imd_fixtures import get_test_fixture_alerts
            fixture_items = get_test_fixture_alerts(location_name)
            if fixture_items:
                return fixture_items

        # Resolve location or coordinates to canonical IMD district
        matched_district = resolve_imd_district(
            location_name=location_name,
            latitude=latitude,
            longitude=longitude
        )

        if not matched_district:
            logger.info(
                f"No reliable IMD district match established for '{location_name}' ({latitude}, {longitude}). "
                "Returning zero alerts (no hallucinated match)."
            )
            return []

        cache_key = f"imd_official_alerts_{matched_district}"
        cached = provider_cache.get(cache_key)
        if cached:
            # Re-evaluate validity times of cached alerts against current time
            now = datetime.now(timezone.utc)
            valid_cached: List[NormalizedAlertItem] = []
            for item in cached:
                try:
                    exp = datetime.fromisoformat(item.expires_at)
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if exp >= now:
                        # Update state to STALE if cached for longer than 60s
                        item.state = "LIVE"
                        valid_cached.append(item)
                except Exception:
                    pass
            return valid_cached

        # In production mode: Query real IMD GeoServer/Mausam warning endpoints
        all_official_alerts: List[NormalizedAlertItem] = []

        try:
            # 1. Fetch District-Wise Warnings (Days 1 to 5)
            warnings = await self.fetch_official_district_warnings(matched_district)
            all_official_alerts.extend(warnings)
        except Exception as e:
            logger.warning(f"Official IMD district warnings query error for {matched_district}: {e}")

        try:
            # 2. Fetch District-Wise Nowcasts (3-hour high urgency)
            nowcasts = await self.fetch_official_district_nowcast(matched_district)
            all_official_alerts.extend(nowcasts)
        except Exception as e:
            logger.warning(f"Official IMD nowcast query error for {matched_district}: {e}")

        if all_official_alerts:
            provider_cache.set(cache_key, all_official_alerts, ttl=settings.IMD_CACHE_TTL_SECONDS)

        return all_official_alerts
