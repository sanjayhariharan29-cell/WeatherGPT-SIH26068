import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.geocoding_service import GeocodingService

client = TestClient(app)
geocoding = GeocodingService()

@pytest.mark.asyncio
async def test_01_valid_coordinates():
    """1. Test valid coordinate validation in GeocodingService."""
    # Valid coordinates should pass without error
    geocoding.validate_coordinates(11.0168, 76.9558)
    geocoding.validate_coordinates(-20.5, 140.2)
    geocoding.validate_coordinates(0.0, 0.0)


@pytest.mark.asyncio
async def test_02_invalid_coordinates():
    """2. Test invalid coordinates raise ValueError or HTTP 400."""
    with pytest.raises(ValueError):
        geocoding.validate_coordinates(999.0, 76.9558)

    with pytest.raises(ValueError):
        geocoding.validate_coordinates(11.0168, -200.0)

    # API test for invalid coordinates
    res = client.post("/api/v1/locations/reverse", json={
        "latitude": 999.0,
        "longitude": 76.9558
    })
    assert res.status_code in [400, 422]


@pytest.mark.asyncio
async def test_03_device_success_reverse_geocoding():
    """3. Test device GPS reverse geocoding converts lat/lon into location metadata."""
    res = await geocoding.reverse_geocode(10.7656, 79.8424, accuracy=15.0)
    assert res["name"] == "Nagapattinam"
    assert res["state"] == "Tamil Nadu"
    assert res["country"] == "India"
    assert res["timezone"] == "Asia/Kolkata"
    assert res["accuracy"] == 15.0
    assert res["source"] == "device_gps"

    # API test for reverse geocoding
    api_res = client.post("/api/v1/locations/reverse", json={
        "latitude": 13.0827,
        "longitude": 80.2707,
        "accuracy": 10.0
    })
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["name"] == "Chennai"
    assert data["timezone"] == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_04_permission_denied_fallback():
    """4. Test permission denied fallback returns default location gracefully."""
    # When query is empty or failed, resolve_location returns default fallback (Coimbatore)
    res = await geocoding.resolve_location("")
    assert res["name"] == "Coimbatore"
    assert res["timezone"] == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_05_timeout_fallback():
    """5. Test timeout handling in GeocodingService falls back cleanly."""
    slow_service = GeocodingService(timeout=0.001)
    res = await slow_service.resolve_location("nonexistent_unknown_place_99999")
    assert res["name"] == "Coimbatore"


@pytest.mark.asyncio
async def test_06_unavailable_location_fallback():
    """6. Test unavailable or unresolvable location falls back to default without crashing."""
    res = await geocoding.resolve_location("xyz123abc_unresolvable")
    assert res["name"] == "Coimbatore"
    assert res["latitude"] == 11.0168


@pytest.mark.asyncio
async def test_07_manual_location_search_and_resolve():
    """7. Test manual location search and resolve endpoints."""
    # Search
    search_res = client.get("/api/v1/locations/search?q=Nagapattinam")
    assert search_res.status_code == 200
    results = search_res.json()["results"]
    assert len(results) >= 1
    assert results[0]["name"] == "Nagapattinam"

    # Resolve
    resolve_res = client.post("/api/v1/locations/resolve", json={"query": "Madurai"})
    assert resolve_res.status_code == 200
    data = resolve_res.json()
    assert data["name"] == "Madurai"
    assert data["latitude"] == 9.9252


@pytest.mark.asyncio
async def test_08_timezone_metadata():
    """8. Test timezone metadata is returned correctly for all location operations."""
    res = await geocoding.resolve_location("Tiruchirappalli")
    assert res["timezone"] == "Asia/Kolkata"
    assert res["country"] == "India"


def test_09_saved_location_creation_and_listing():
    """9. Test creating and listing saved locations for an authenticated user."""
    email = f"loc_user_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Loc User", "email": email, "password": "Password123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]

    # Save Location
    save_res = client.post(
        "/api/v1/locations/saved",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Kanyakumari", "latitude": 8.0883, "longitude": 77.5385}
    )
    assert save_res.status_code == 201
    data = save_res.json()
    assert data["name"] == "Kanyakumari"

    # List Saved Locations
    list_res = client.get("/api/v1/locations/saved", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


def test_10_saved_location_user_ownership():
    """10. Test User A cannot delete or access User B's saved location."""
    # User A
    email_a = f"loc_a_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "User A", "email": email_a, "password": "Password123!"})
    token_a = client.post("/api/v1/auth/login", json={"email": email_a, "password": "Password123!"}).json()["access_token"]

    # User B
    email_b = f"loc_b_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "User B", "email": email_b, "password": "Password123!"})
    token_b = client.post("/api/v1/auth/login", json={"email": email_b, "password": "Password123!"}).json()["access_token"]

    # User B saves a location
    loc_b = client.post(
        "/api/v1/locations/saved",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"name": "Vellore Fort", "latitude": 12.9165, "longitude": 79.1325}
    ).json()

    # User A attempts to delete User B's saved location
    del_res = client.delete(f"/api/v1/locations/saved/{loc_b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert del_res.status_code == 403
    assert "access denied" in del_res.json()["detail"].lower()


def test_11_location_weather_integration():
    """11. Test end-to-end integration: Location resolution feeding Weather API."""
    # Resolve location
    resolve_res = client.post("/api/v1/locations/resolve", json={"query": "Coimbatore"})
    assert resolve_res.status_code == 200
    loc_data = resolve_res.json()

    # Weather request using resolved location name
    weather_res = client.get(f"/api/v1/weather/current?location={loc_data['name']}")
    assert weather_res.status_code == 200
    weather_data = weather_res.json()
    assert weather_data["location"]["name"] == loc_data["name"]
    assert "temperature" in weather_data["weather"]
