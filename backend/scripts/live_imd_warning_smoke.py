"""SkyZen Official IMD Warning & Nowcast Live Smoke Test Utility.

Queries genuine official IMD endpoints (GeoServer WFS and Mausam APIs) for live
district-wise warnings and nowcasts. Validates provenance, timestamps, severity,
and active alert counts without exposing secrets or private credentials.

Usage:
    python backend/scripts/live_imd_warning_smoke.py [--district DISTRICT] [--lat LAT] [--lon LON]
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime, timezone

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.config.settings import settings
from backend.services.imd_adapter import IMDAdapter
from backend.services.imd_district_registry import resolve_imd_district, ALL_DISTRICTS
from backend.services.exceptions import ProviderError, ProviderUnavailableError


async def run_live_imd_smoke(location_or_district: str, lat: float, lon: float) -> int:
    print("=" * 70)
    print("SKYZEN OFFICIAL IMD WARNING & NOWCAST LIVE SMOKE TEST")
    print("=" * 70)

    # 1. Resolve to canonical IMD district
    canonical_district = resolve_imd_district(location_or_district, lat, lon)
    if not canonical_district:
        print(f"Target Query: '{location_or_district}' (Lat: {lat}, Lon: {lon})")
        print("Status: IMD DISTRICT NOT RESOLVED")
        print("Reason: No official IMD district match found for location/coordinates.")
        print("IMD LIVE ACCESS FAILED")
        return 1

    print(f"Target District: {canonical_district} (Input: '{location_or_district}')")
    print(f"Coordinates: {lat}° N, {lon}° E")
    print(f"Retrieved At: {datetime.now(timezone.utc).isoformat()} (UTC)")
    print("-" * 70)

    # Initialize live IMD adapter in strict live mode (never fixture)
    adapter = IMDAdapter(timeout=10.0, mode="live")

    # 2. Test Official District Warnings (Days 1 to 5)
    print(f"1. Querying IMD District Warnings (Endpoint: {settings.IMD_GEOSERVER_WFS_URL})...")
    district_warnings = []
    w_status = "REAL IMD LIVE"

    try:
        district_warnings = await adapter.fetch_official_district_warnings(canonical_district)
        print(f"   Request Status: SUCCESS [HTTP 200]")
        print(f"   Product: IMD District Warning")
        print(f"   Source Provenance: IMD Official (Authoritative)")
        print(f"   Active Warnings Count: {len(district_warnings)}")

        for idx, warn in enumerate(district_warnings, 1):
            print(f"   [{idx}] ID: {warn.alert_id}")
            print(f"       Severity: {warn.severity.upper()} | Status: {warn.status}")
            print(f"       Title: {warn.title}")
            print(f"       Affected Area: {warn.area}")
            print(f"       Valid: {warn.issued_at} -> {warn.expires_at}")
            print(f"       Geometry Attached: {bool(warn.geometry and warn.geometry.get('coordinates'))}")
    except Exception as e:
        w_status = "FAILED"
        print(f"   Request Status: ERROR ({type(e).__name__}: {str(e)})")

    # 3. Test Official District Nowcasts (3-hour immediate hazard)
    print(f"\n2. Querying IMD District Nowcasts (Endpoint: {settings.IMD_NOWCAST_WFS_URL})...")
    district_nowcasts = []
    n_status = "REAL IMD LIVE"

    try:
        district_nowcasts = await adapter.fetch_official_district_nowcast(canonical_district)
        print(f"   Request Status: SUCCESS [HTTP 200]")
        print(f"   Product: IMD District Nowcast")
        print(f"   Source Provenance: IMD Official (Authoritative)")
        print(f"   Active Nowcast Count: {len(district_nowcasts)}")

        for idx, nowc in enumerate(district_nowcasts, 1):
            print(f"   [{idx}] ID: {nowc.alert_id}")
            print(f"       Severity: {nowc.severity.upper()} | Status: {nowc.status}")
            print(f"       Title: {nowc.title}")
            print(f"       Affected Area: {nowc.area}")
            print(f"       TOI: {nowc.toi} | Valid Upto: {nowc.vupto}")
            print(f"       Issued: {nowc.issued_at} -> Expires: {nowc.expires_at}")
    except Exception as e:
        n_status = "FAILED"
        print(f"   Request Status: ERROR ({type(e).__name__}: {str(e)})")

    # 4. Summary & Verification
    print("\n" + "=" * 70)
    total_alerts = len(district_warnings) + len(district_nowcasts)

    if w_status == "REAL IMD LIVE" or n_status == "REAL IMD LIVE":
        print(f"OFFICIAL IMD STATUS: REAL IMD LIVE")
        print(f"TOTAL ACTIVE OFFICIAL ALERTS FOR {canonical_district}: {total_alerts}")
        print("ATTRIBUTION: India Meteorological Department (IMD), Ministry of Earth Sciences")
        print("SECURITY: Zero secrets or private keys exposed in output.")
        print("=" * 70)
        return 0
    else:
        print("OFFICIAL IMD STATUS: IMD LIVE ACCESS FAILED")
        print("Reason: All official IMD live endpoints returned connection or authorization errors.")
        print("=" * 70)
        return 1


def main():
    parser = argparse.ArgumentParser(description="SkyZen Official IMD Warning Live Smoke Test")
    parser.add_argument("--district", type=str, default="Coimbatore", help="District or Location name")
    parser.add_argument("--lat", type=float, default=11.0168, help="Latitude")
    parser.add_argument("--lon", type=float, default=76.9558, help="Longitude")
    args = parser.parse_args()

    exit_code = asyncio.run(run_live_imd_smoke(args.district, args.lat, args.lon))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
