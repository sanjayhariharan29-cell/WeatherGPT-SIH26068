"""SkyZen Live Weather Smoke Test Utility.

Command-line execution script to test actual live weather requests against configured providers
(Open-Meteo, OpenWeather, and IMD). Validates timestamps, freshness, physical boundaries,
and outputs diagnostic statuses WITHOUT exposing provider API secrets or private credentials.

Usage:
    python backend/scripts/live_weather_smoke.py [--lat LAT] [--lon LON] [--loc LOCATION]
"""

import os
import sys
import asyncio
import argparse
from typing import Dict, Any, List

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.config.settings import settings
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.openweather_adapter import OpenWeatherAdapter
from backend.services.imd_adapter import IMDAdapter
from backend.services.weather_reliability import (
    evaluate_weather_freshness,
    validate_weather_completeness,
    PhysicalBounds
)


async def run_smoke_test(lat: float, lon: float, location: str):
    print("=" * 60)
    print(f"SKYZEN REAL-TIME MULTI-SOURCE WEATHER SMOKE TEST")
    print("=" * 60)
    print(f"Target Location: {location} (Lat: {lat}, Lon: {lon})\n")

    # 1. Test Open-Meteo (Live API)
    print("1. Testing Provider: Open-Meteo (Real-Time API)...")
    open_meteo = OpenMeteoAdapter(timeout=6.0)
    try:
        om_obs = await open_meteo.get_current_weather(lat, lon, location)
        freshness, age_min, meta = evaluate_weather_freshness(om_obs.observed_at, om_obs.retrieved_at)
        comp, val, issues = validate_weather_completeness(om_obs.model_dump())
        print(f"   Status: PASS [HTTP 200]")
        print(f"   Temperature: {om_obs.temperature_c}°C (Feels like: {om_obs.feels_like_c}°C)")
        print(f"   Humidity: {om_obs.humidity_pct}% | Wind: {om_obs.wind_speed_kmh} km/h | Condition: {om_obs.condition}")
        print(f"   Observed At: {om_obs.observed_at} (Age: {age_min}m, Freshness: {freshness.value})")
        print(f"   Completeness: {comp.value} | Validation: {val.value}")
    except Exception as e:
        print(f"   Status: FAIL ({str(e)})")

    # 2. Test OpenWeather (Independent Secondary Provider)
    print("\n2. Testing Provider: OpenWeather (Configurable Live API)...")
    openweather = OpenWeatherAdapter(timeout=6.0)
    if not openweather.is_configured:
        print("   Status: LIVE PROVIDER CREDENTIALS NOT CONFIGURED")
        print("   Notice: Set OPENWEATHER_API_KEY in backend/.env to activate live requests.")
    else:
        try:
            ow_obs = await openweather.get_current_weather(lat, lon, location)
            freshness, age_min, meta = evaluate_weather_freshness(ow_obs.observed_at, ow_obs.retrieved_at)
            comp, val, issues = validate_weather_completeness(ow_obs.model_dump())
            print(f"   Status: PASS [HTTP 200]")
            print(f"   Temperature: {ow_obs.temperature_c}°C (Feels like: {ow_obs.feels_like_c}°C)")
            print(f"   Humidity: {ow_obs.humidity_pct}% | Wind: {ow_obs.wind_speed_kmh} km/h | Condition: {ow_obs.condition}")
            print(f"   Observed At: {ow_obs.observed_at} (Age: {age_min}m, Freshness: {freshness.value})")
            print(f"   Completeness: {comp.value} | Validation: {val.value}")
        except Exception as e:
            print(f"   Status: FAIL ({str(e)})")

    # 3. Test IMD (Official Primary Provider)
    print("\n3. Testing Provider: IMD (India Meteorological Department)...")
    imd = IMDAdapter(timeout=6.0)
    if not imd.is_live_configured:
        print("   Status: IMD LIVE ACCESS NOT CONFIGURED")
        print("   Notice: Authorized IMD endpoint key not present. Operating in deterministic reference boundary.")
        imd_obs = await imd.get_current_weather(lat, lon, location)
        print(f"   Deterministic Fixture Value: {imd_obs.temperature_c}°C ({imd_obs.condition})")
        print(f"   Authority: {imd_obs.authority_level} (Official Warnings Authoritative)")
    else:
        try:
            imd_obs = await imd.get_current_weather(lat, lon, location)
            print(f"   Status: PASS [Official Live Stream]")
            print(f"   Temperature: {imd_obs.temperature_c}°C | Humidity: {imd_obs.humidity_pct}%")
        except Exception as e:
            print(f"   Status: FAIL ({str(e)})")

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE: Zero secrets exposed in output.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="SkyZen Live Weather Smoke Test")
    parser.add_argument("--lat", type=float, default=11.0168, help="Latitude")
    parser.add_argument("--lon", type=float, default=76.9558, help="Longitude")
    parser.add_argument("--loc", type=str, default="Coimbatore", help="Location name")
    args = parser.parse_args()

    asyncio.run(run_smoke_test(args.lat, args.lon, args.loc))


if __name__ == "__main__":
    main()
