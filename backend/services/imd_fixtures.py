"""IMD Test Fixtures (Test Environments Only).

Contains reference fixtures strictly isolated for unit and integration testing.
NEVER imported or executed in the production live alert path.
"""

import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from backend.config.settings import settings
from backend.services.schemas import (
    NormalizedWeatherObservation,
    NormalizedForecastItem,
    NormalizedAlertItem
)


def assert_test_environment_allowed():
    """Safety guard ensuring test fixtures are never invoked in live production."""
    env = (settings.IMD_ENVIRONMENT or os.getenv("IMD_ENVIRONMENT", "production")).lower()
    app_env = (settings.ENVIRONMENT or os.getenv("ENVIRONMENT", "development")).lower()
    if env == "production" and app_env == "production":
        raise RuntimeError(
            "FATAL: Test fixtures cannot be accessed in production environment. "
            "SkyZen requires live official IMD warning data."
        )


def get_test_fixture_observation(
    location_name: str,
    latitude: float,
    longitude: float,
    now_utc: Optional[str] = None
) -> NormalizedWeatherObservation:
    """Provides deterministic IMD observation fixture for test suites."""
    assert_test_environment_allowed()
    now = now_utc or datetime.now(timezone.utc).isoformat()
    loc_lower = location_name.lower()

    if "nagapattinam" in loc_lower or "நாகப்பட்டினம்" in loc_lower:
        return NormalizedWeatherObservation(
            location_name="Nagapattinam",
            latitude=latitude,
            longitude=longitude,
            temperature_c=27.5,
            humidity_pct=88.0,
            rain_probability_pct=85.0,
            wind_speed_kmh=34.0,
            rainfall_mm=45.0,
            condition="Heavy Rain & Wind",
            source="IMD",
            authority_level="primary_authoritative",
            observed_at=now,
            retrieved_at=now
        )
    return NormalizedWeatherObservation(
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        temperature_c=29.0,
        humidity_pct=72.0,
        rain_probability_pct=65.0,
        wind_speed_kmh=18.0,
        rainfall_mm=12.5,
        condition="Moderate Rain",
        source="IMD",
        authority_level="primary_authoritative",
        observed_at=now,
        retrieved_at=now
    )


def get_test_fixture_forecast(
    location_name: str,
    now_utc: Optional[str] = None
) -> List[NormalizedForecastItem]:
    """Provides deterministic IMD forecast fixture for test suites."""
    assert_test_environment_allowed()
    now = now_utc or datetime.now(timezone.utc).isoformat()
    loc_lower = location_name.lower()

    if "nagapattinam" in loc_lower or "நாகப்பட்டினம்" in loc_lower:
        return [
            NormalizedForecastItem(
                forecast_time="07:00 AM",
                forecast_for=now,
                temperature_c=26.5,
                temp_min_c=24.0,
                temp_max_c=28.0,
                rain_probability_pct=90.0,
                rainfall_mm=35.0,
                wind_speed_kmh=38.0,
                condition="Torrential Rain",
                source="IMD",
                issued_at=now,
                retrieved_at=now
            ),
            NormalizedForecastItem(
                forecast_time="12:00 PM",
                forecast_for=now,
                temperature_c=28.0,
                temp_min_c=25.0,
                temp_max_c=30.0,
                rain_probability_pct=85.0,
                rainfall_mm=25.0,
                wind_speed_kmh=35.0,
                condition="Heavy Rain",
                source="IMD",
                issued_at=now,
                retrieved_at=now
            )
        ]
    return [
        NormalizedForecastItem(
            forecast_time="07:00 AM",
            forecast_for=now,
            temperature_c=27.0,
            temp_min_c=23.0,
            temp_max_c=31.0,
            rain_probability_pct=70.0,
            rainfall_mm=10.0,
            wind_speed_kmh=14.0,
            condition="Moderate Rain",
            source="IMD",
            issued_at=now,
            retrieved_at=now
        ),
        NormalizedForecastItem(
            forecast_time="12:00 PM",
            forecast_for=now,
            temperature_c=30.5,
            temp_min_c=25.0,
            temp_max_c=33.0,
            rain_probability_pct=45.0,
            rainfall_mm=2.0,
            wind_speed_kmh=16.0,
            condition="Partly Cloudy",
            source="IMD",
            issued_at=now,
            retrieved_at=now
        )
    ]


def get_test_fixture_alerts(
    location_name: str,
    now_dt: Optional[datetime] = None
) -> List[NormalizedAlertItem]:
    """Provides deterministic IMD alert fixtures for isolated unit tests."""
    assert_test_environment_allowed()
    dt = (now_dt or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    now_utc = dt.isoformat()
    expires_24h = (dt + timedelta(hours=24)).isoformat()
    expires_12h = (dt + timedelta(hours=12)).isoformat()
    expired_yesterday = (dt - timedelta(hours=12)).isoformat()
    loc_lower = location_name.lower()

    if "expired" in loc_lower:
        return [
            NormalizedAlertItem(
                alert_id="IMD-FIXTURE-EXPIRED",
                alert_type="heatwave_warning",
                severity="medium",
                title="IMD Expired Heatwave Notice",
                description="Historic heatwave advisory now expired.",
                instructions="Stay hydrated.",
                area="Expired Zone",
                source="IMD",
                product_type="district_warning",
                state="FIXTURE",
                issued_at=(dt - timedelta(days=2)).isoformat(),
                expires_at=expired_yesterday,
                retrieved_at=now_utc,
                status="EXPIRED"
            )
        ]
    elif "nagapattinam" in loc_lower or "நாகப்பட்டினம்" in loc_lower:
        return [
            NormalizedAlertItem(
                alert_id="IMD-FIXTURE-NAGAPATTINAM",
                alert_type="heavy_rain_cyclone",
                severity="high",
                title="IMD Heavy Rain & Marine Warning",
                description="Severe weather warning issued by IMD for coastal Tamil Nadu. Fishermen advised not to venture into deep sea due to high squally winds.",
                instructions="Avoid sea ventures. Move to cyclone relief centers if in low-lying areas.",
                area="Nagapattinam Coastal Zone",
                source="IMD",
                product_type="district_warning",
                state="FIXTURE",
                issued_at=(dt - timedelta(hours=1)).isoformat(),
                expires_at=expires_24h,
                retrieved_at=now_utc,
                status="ACTIVE"
            )
        ]
    elif "coimbatore" in loc_lower or "கோயம்புத்தூர்" in loc_lower:
        return [
            NormalizedAlertItem(
                alert_id="IMD-FIXTURE-COIMBATORE",
                alert_type="thunderstorm_warning",
                severity="medium",
                title="IMD Rain & Thunderstorm Advisory",
                description="Moderate to heavy rain with thunderstorm expected in Coimbatore district during morning hours.",
                instructions="Avoid open ground and under isolated trees during thunderstorm activity.",
                area="Coimbatore District",
                source="IMD",
                product_type="district_warning",
                state="FIXTURE",
                issued_at=(dt - timedelta(hours=1)).isoformat(),
                expires_at=expires_12h,
                retrieved_at=now_utc,
                status="ACTIVE"
            )
        ]
    return []
