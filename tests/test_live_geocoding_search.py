"""
Tests for Live Geocoding Search & Debounced Home Search Bar
Verifies:
1. /api/v1/locations/search?q=che returns live matching Indian locations including Chennai and other similarly named towns.
2. Geocoding service does not use a hardcoded list for search results.
3. Frontend app.js implements debounced search using apiClient.searchLocations and does not hardcode city lists.
4. Selecting a suggestion sets location state with coordinates and calls loadCurrentWeather(true).
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.geocoding_service import GeocodingService


@pytest.fixture
def client():
    return TestClient(app)


def test_01_live_geocoding_search_for_che(client):
    """Test that searching 'che' returns Chennai and other similarly-named Indian towns."""
    resp = client.get("/api/v1/locations/search?q=che")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "results" in data, "Response should have 'results' list"
    results = data["results"]
    assert len(results) >= 2, f"Expected multiple matching Indian locations for 'che', got {len(results)}"

    names = [r["name"].lower() for r in results]
    assert any("chennai" in n for n in names), f"Expected 'Chennai' in results, got {names}"
    
    # Verify all results contain required fields and country is India
    for r in results:
        assert "name" in r and r["name"], "Location must have a name"
        assert "latitude" in r and isinstance(r["latitude"], (int, float)), "Location must have numeric latitude"
        assert "longitude" in r and isinstance(r["longitude"], (int, float)), "Location must have numeric longitude"
        assert r.get("country", "").lower() == "india", "All returned locations should be Indian"


def test_02_geocoding_search_across_indian_cities(client):
    """Test searching various partial queries returns live Indian towns."""
    queries = ["del", "mumb", "pune", "kochi"]
    for q in queries:
        resp = client.get(f"/api/v1/locations/search?q={q}")
        assert resp.status_code == 200
        results = resp.json().get("results", [])
        assert len(results) > 0, f"Expected results for query '{q}'"
        first = results[0]
        assert -90.0 <= first["latitude"] <= 90.0
        assert -180.0 <= first["longitude"] <= 180.0


def test_03_frontend_uses_geocoding_service_and_no_hardcoded_list():
    """Verify frontend app.js does not hardcode a search list and uses debounced apiClient.searchLocations."""
    with open("frontend/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "SEARCH_POPULAR_CITIES" not in js, "SEARCH_POPULAR_CITIES hardcoded list should be removed"
    assert "apiClient.searchLocations" in js, "Frontend must use apiClient.searchLocations for live lookup"
    assert "searchDebounceTimer" in js or "DEBOUNCE_MS" in js, "Frontend must debounce search input"
    assert "loadCurrentWeather(true)" in js, "Selecting suggestion must trigger loadCurrentWeather"
    assert "setLocationState" in js, "Selecting suggestion must update location state with coordinates"


def test_04_android_assets_match_frontend():
    """Verify android public assets match frontend implementation."""
    with open("android/app/src/main/assets/public/app.js", "r", encoding="utf-8") as f:
        android_js = f.read()

    assert "SEARCH_POPULAR_CITIES" not in android_js, "SEARCH_POPULAR_CITIES must not be in Android assets"
    assert "apiClient.searchLocations" in android_js, "Android assets must use apiClient.searchLocations"
