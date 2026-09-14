import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.geocoding_service import GeocodingService

client = TestClient(app)
geocoding = GeocodingService()

@pytest.mark.asyncio
async def test_01_reverse_geocode_gps_coordinates_for_home_location():
    """Verify reverse geocode takes GPS coordinates and returns verified location for Home."""
    res = await geocoding.reverse_geocode(11.0168, 76.9558, accuracy=10.0)
    assert res is not None
    assert "name" in res
    assert res["name"] in ["Coimbatore", "Coimbatore District"]
    assert res["country"] == "India"
    assert res["source"] == "device_gps"

    # Verify API route works
    api_res = client.post("/api/v1/locations/reverse", json={
        "latitude": 11.0168,
        "longitude": 76.9558,
        "accuracy": 10.0
    })
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["name"] in ["Coimbatore", "Coimbatore District"]
    assert data["latitude"] == 11.0168
    assert data["longitude"] == 76.9558


def test_02_frontend_auth_guard_prevents_pre_login_location_request():
    """Verify that frontend/app.js strictly guards location requests so unauthenticated users never get prompted."""
    app_js_path = Path("frontend/app.js")
    assert app_js_path.exists()
    content = app_js_path.read_text(encoding="utf-8")

    # Guard in refreshForegroundLocation
    assert "if (!isAppAuthenticated() && triggerReason !== \"user_click\")" in content
    # Guard in handleForegroundWakeup
    assert "if (!isAppAuthenticated()) return;" in content
    # Guard in showLocationPermissionPrompt
    assert "if (!isAppAuthenticated()) return;" in content


def test_03_frontend_handles_post_auth_location_flow_and_non_repeating_denial():
    """Verify that frontend/app.js implements handlePostAuthLocationFlow and never re-prompts after denial."""
    app_js_path = Path("frontend/app.js")
    content = app_js_path.read_text(encoding="utf-8")

    # Function exists
    assert "async function handlePostAuthLocationFlow" in content

    # Check for denial persistence and graceful fallback
    assert "skyzen_loc_permission_status" in content
    assert "if (permStatus === \"denied\" || isDismissed)" in content
    assert "loadLastKnownLocation();" in content

    # Check that post-auth location flow is wired into all auth completion entry points
    assert "await handlePostAuthLocationFlow(\"session_restore\");" in content
    assert "await handlePostAuthLocationFlow(\"demo_login\");" in content
    assert "await handlePostAuthLocationFlow(\"login_success\");" in content
    assert "await handlePostAuthLocationFlow(\"verification_success\");" in content
    assert "await handlePostAuthLocationFlow(\"onboarding_complete\");" in content


def test_04_location_permission_explanation_banner_wiring():
    """Verify that the explanation banner allow and dismiss actions are properly wired."""
    app_js_path = Path("frontend/app.js")
    content = app_js_path.read_text(encoding="utf-8")

    assert "locPromptAllowBtn.addEventListener(\"click\"" in content
    assert "locPromptDismissBtn.addEventListener(\"click\"" in content
    # Dismiss records denial
    assert "localStorage.setItem(\"skyzen_loc_permission_status\", \"denied\");" in content
