# Phase 14 — Location Services (Person 2)

## Overview

Phase 14 makes WeatherGPT location-aware. It adds device GPS geolocation integration, reverse geocoding from latitude/longitude coordinates, location query resolution for Tamil and English location names, location timezone metadata (`Asia/Kolkata`), strict coordinate bounds validation, and user location persistence with resource ownership checks.

---

## Key Components Implemented

### 1. Reverse Geocoding & Location Resolution (`backend/services/geocoding_service.py`)
- **Strict Bounds Validation**: `validate_coordinates(lat, lon)` enforces `-90.0 <= latitude <= 90.0` and `-180.0 <= longitude <= 180.0`. Invalid inputs raise `ValueError` / HTTP 420/422 errors.
- **Reverse Geocoding**: `reverse_geocode(lat, lon, accuracy)` resolves GPS coordinates into nearest location, district, state, country (`India`), timezone (`Asia/Kolkata`), and source (`device_gps`).
- **Location Resolution**: Resolves search queries in Tamil or English (e.g. `Nagapattinam`, `கோயம்புத்தூர்`, `Chennai`) with fallback to Nominatim OSM geocoding and default presets.

### 2. Location API Endpoints (`backend/api/locations.py`)
- `GET /api/v1/locations/search?q=...`: Searches for matching location names.
- `POST /api/v1/locations/resolve`: Resolves query string or coordinates into location metadata and timezone.
- `POST /api/v1/locations/reverse`: Converts device GPS coordinates into location details and timezone.
- `POST /api/v1/locations/saved`: Saves a location for the authenticated user.
- `GET /api/v1/locations/saved`: Lists saved locations owned by the authenticated user (User Ownership enforced).
- `DELETE /api/v1/locations/saved/{id}`: Deletes saved location owned by the authenticated user (User Ownership enforced).

### 3. Device Geolocation Integration (`frontend/app.js` & `frontend/index.html`)
- **GPS Button (`#geoBtn`)**: Triggers `navigator.geolocation.getCurrentPosition()` with a 8.0-second timeout and high accuracy.
- **Graceful Error Fallbacks**:
  - `PERMISSION_DENIED`: Displays notification ("Location permission denied. Please select location manually.") without crashing.
  - `TIMEOUT`: Displays notification ("GPS request timed out. Please select location manually.").
  - `POSITION_UNAVAILABLE`: Displays notification ("Location information unavailable. Please select location manually.").
  - Never forces location access or crashes application shell.

---

## Test Verification Summary

The test suite in `tests/test_location_services.py` verifies all 11 required location test cases:

1. **Valid Coordinates**: Verifies `-90 <= lat <= 90` and `-180 <= lon <= 180` pass validation.
2. **Invalid Coordinates**: Verifies invalid inputs (e.g. `lat=999`) raise validation errors / HTTP 422/400.
3. **Device Success**: Verifies GPS reverse geocoding returns location name, district, state, country, timezone (`Asia/Kolkata`), and accuracy.
4. **Permission Denied Fallback**: Verifies fallback to default manual location selection works gracefully.
5. **Timeout Fallback**: Verifies timeout handling falls back cleanly without breaking app shell.
6. **Unavailable Location Fallback**: Verifies unresolvable locations fall back gracefully.
7. **Manual Location Search & Resolve**: Verifies location search and resolve APIs for Tamil/English names.
8. **Timezone Metadata**: Verifies `Asia/Kolkata` timezone string is attached to location metadata.
9. **Saved Location Management**: Verifies location creation and listing for authenticated users.
10. **Saved Location User Ownership**: Verifies User A cannot access or delete User B's saved locations (403 Forbidden).
11. **Location & Weather Integration**: Verifies resolved location feeds into backend current weather & forecast telemetry seamlessly.

### Full Regression Results

Full test suite execution (`python -m pytest -v`):
- **Total Passed**: **426 / 426**
- **Failed**: **0**
- **Execution Time**: 21.19s
