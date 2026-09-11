"""Comprehensive Test Suite for SkyZen Automatic Foreground Location Intelligence.

Verifies:
1. Reverse geocoding & anti-fabrication policies:
   - Known reference coordinates resolve to correct official stations (Coimbatore, Chennai).
   - Arbitrary/unmapped coordinates resolve to coordinate string without fabricating phantom cities.
   - Invalid coordinate ranges rejected with 400 Bad Request.
2. User profile and preference last-known location persistence:
   - Saving last-known location, coordinates, source, and timestamp via /users/profile and /users/preferences.
   - Retrieving last-known location metadata survives across sessions.
3. Dynamic foreground location switching:
   - When a user moves from Coimbatore to Chennai, sending live GPS coordinates switches the
     authoritative conversation weather context to Chennai.
4. Conversational AI location intelligence:
   - Differentiates CURRENT_LIVE_LOCATION, LAST_KNOWN_LOCATION, and MANUAL_LOCATION.
   - Handles stale last-known locations gracefully.
   - Explicit in-text query overrides (e.g. "Will it rain in Madurai?") take precedence over GPS for that specific question.
"""

import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.security import hash_password, create_access_token
from backend.db.session import SessionLocal
from backend.db.models import User, UserPreference
from backend.schemas.chat import LocationPayload, ChatRequest
from backend.services.geocoding_service import GeocodingService

geocoding = GeocodingService()

client = TestClient(app)


# =============================================================================
# 1. Reverse Geocoding & Anti-Fabrication Tests
# =============================================================================

class TestReverseGeocodingAndAntiFabrication:
    """Test GPS coordinate resolution and strict anti-fabrication rules."""

    def test_reverse_geocode_coimbatore_station(self):
        """Coimbatore GPS coordinates resolve to Coimbatore."""
        res = client.post(
            "/api/v1/locations/reverse",
            json={"latitude": 11.0168, "longitude": 76.9558, "accuracy": 15.0}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"].lower() == "coimbatore"
        assert data["state"] == "Tamil Nadu"
        assert data["source"] == "device_gps"

    def test_reverse_geocode_chennai_station(self):
        """Chennai GPS coordinates resolve to Chennai."""
        res = client.post(
            "/api/v1/locations/reverse",
            json={"latitude": 13.0827, "longitude": 80.2707, "accuracy": 10.0}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"].lower() == "chennai"
        assert data["state"] == "Tamil Nadu"

    def test_anti_fabrication_arbitrary_coordinates(self):
        """Remote/unmapped coordinates must never fabricate a false city name."""
        res = client.post(
            "/api/v1/locations/reverse",
            json={"latitude": 28.6139, "longitude": 77.2090, "accuracy": 50.0}
        )
        assert res.status_code == 200
        data = res.json()
        # Must format as coordinates or valid station, NEVER invent a non-existent Tamil Nadu city
        assert "Location (" in data["name"] or data["name"] in ("Delhi", "New Delhi")
        assert data["latitude"] == pytest.approx(28.6139, abs=0.01)

    def test_invalid_coordinates_rejected(self):
        """Out of range coordinates must be rejected with 422 or 400."""
        res = client.post(
            "/api/v1/locations/reverse",
            json={"latitude": 95.0, "longitude": 80.0}
        )
        assert res.status_code in (400, 422)


# =============================================================================
# 2. User Profile & Preference Last-Known Location Persistence
# =============================================================================

class TestUserProfileLocationPersistence:
    """Test persisting and restoring last known location metadata across sessions."""

    @pytest.fixture
    def test_user(self):
        """Create a temporary verified user and auth token."""
        db = SessionLocal()
        user_id = str(uuid.uuid4())
        email = f"location_test_{uuid.uuid4().hex[:6]}@test.com"
        user = User(
            id=user_id,
            email=email,
            name="Location Test User",
            password_hash=hash_password("Pass123!"),
            role="user",
            is_verified=True,
            onboarding_completed=True
        )
        pref = UserPreference(user_id=user_id, last_known_location="Coimbatore", last_latitude=11.0168, last_longitude=76.9558)
        db.add(user)
        db.add(pref)
        db.commit()
        db.refresh(user)

        token = create_access_token(data={"sub": user.id})
        headers = {"Authorization": f"Bearer {token}"}

        yield {"user": user, "headers": headers}

        # Cleanup
        try:
            db.query(UserPreference).filter(UserPreference.user_id == user_id).delete()
            db.query(User).filter(User.id == user_id).delete()
            db.commit()
        finally:
            db.close()

    def test_update_and_get_last_known_location_via_profile(self, test_user):
        """Verify profile update persists last-known location and GPS coordinates."""
        headers = test_user["headers"]

        # 1. Update last known location to Chennai
        update_payload = {
            "last_known_location": "Chennai",
            "last_latitude": 13.0827,
            "last_longitude": 80.2707,
            "last_location_source": "CURRENT_LIVE_LOCATION"
        }
        res = client.put("/api/v1/users/profile", json=update_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["last_known_location"] == "Chennai"
        assert data["last_latitude"] == pytest.approx(13.0827, abs=0.001)
        assert data["last_longitude"] == pytest.approx(80.2707, abs=0.001)
        assert data["last_location_source"] == "CURRENT_LIVE_LOCATION"
        assert data["last_location_updated_at"] is not None

        # 2. Get profile and verify persistent state survives
        get_res = client.get("/api/v1/users/profile", headers=headers)
        assert get_res.status_code == 200
        profile = get_res.json()
        assert profile["last_known_location"] == "Chennai"
        assert profile["last_latitude"] == pytest.approx(13.0827, abs=0.001)
        assert profile["last_longitude"] == pytest.approx(80.2707, abs=0.001)
        assert profile["last_location_source"] == "CURRENT_LIVE_LOCATION"

    def test_preferences_endpoint_location_sync(self, test_user):
        """Verify /users/preferences endpoint synchronizes last-known location."""
        headers = test_user["headers"]

        pref_payload = {
            "last_known_location": "Madurai",
            "last_latitude": 9.9252,
            "last_longitude": 78.1198,
            "last_location_source": "LAST_KNOWN_LOCATION"
        }
        res = client.put("/api/v1/users/preferences", json=pref_payload, headers=headers)
        assert res.status_code == 200
        pref_data = res.json()
        assert pref_data["last_known_location"] == "Madurai"
        assert pref_data["last_latitude"] == pytest.approx(9.9252, abs=0.001)
        assert pref_data["last_longitude"] == pytest.approx(78.1198, abs=0.001)
        assert pref_data["last_location_source"] == "LAST_KNOWN_LOCATION"


# =============================================================================
# 3. Dynamic Location Switching & Conversational AI Integration
# =============================================================================

class TestConversationalLocationIntelligence:
    """Test dynamic location switching and GPS-grounded conversational AI turns."""

    def test_schema_location_payload_fields(self):
        """Validate LocationPayload model accepts source_type, accuracy, and is_stale."""
        loc = LocationPayload(
            name="Coimbatore",
            latitude=11.0168,
            longitude=76.9558,
            source_type="CURRENT_LIVE_LOCATION",
            accuracy=12.5,
            is_stale=False
        )
        assert loc.source_type == "CURRENT_LIVE_LOCATION"
        assert loc.accuracy == 12.5
        assert loc.is_stale is False

    def test_live_gps_switches_location_from_coimbatore_to_chennai(self):
        """When user travels to Chennai, live GPS switches the active weather context."""
        # Turn 1: User in Coimbatore
        t1_res = client.post(
            "/api/v1/chat",
            json={
                "message": "What is the weather today?",
                "persona": "student",
                "location": {
                    "name": "Coimbatore",
                    "latitude": 11.0168,
                    "longitude": 76.9558,
                    "source_type": "CURRENT_LIVE_LOCATION",
                    "accuracy": 15.0
                },
                "language": "en"
            }
        )
        assert t1_res.status_code == 200
        t1_data = t1_res.json()
        conv_id = t1_data.get("conversation_id")
        assert "Coimbatore" in t1_data.get("location", "") or "coimbatore" in t1_data.get("answer", "").lower()

        # Turn 2: User moves from Coimbatore to Chennai
        # GPS coordinates switch to Chennai (13.0827, 80.2707)
        t2_res = client.post(
            "/api/v1/chat",
            json={
                "message": "What is the temperature here now?",
                "persona": "student",
                "conversation_id": conv_id,
                "location": {
                    "name": "Coimbatore",  # Old dropdown value before geocoding
                    "latitude": 13.0827,    # LIVE GPS IS CHENNAI (SOURCE OF TRUTH)
                    "longitude": 80.2707,
                    "source_type": "CURRENT_LIVE_LOCATION",
                    "accuracy": 10.0
                },
                "language": "en"
            }
        )
        assert t2_res.status_code == 200
        t2_data = t2_res.json()
        # GPS source of truth should have switched resolved location to Chennai
        assert "Chennai" in t2_data.get("location", "") or "chennai" in t2_data.get("answer", "").lower()

    def test_explicit_query_city_override_preserves_gps_fallback(self):
        """An explicit query for a different city ('in Madurai') overrides GPS for that query."""
        res = client.post(
            "/api/v1/chat",
            json={
                "message": "Will it rain in Madurai tomorrow?",
                "persona": "student",
                "location": {
                    "name": "Coimbatore",
                    "latitude": 11.0168,
                    "longitude": 76.9558,
                    "source_type": "CURRENT_LIVE_LOCATION"
                },
                "language": "en"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert "Madurai" in data.get("location", "") or "madurai" in data.get("answer", "").lower()

    def test_stale_last_known_location_handled_gracefully(self):
        """Stale last-known location is accepted without breaking chat reasoning."""
        res = client.post(
            "/api/v1/chat",
            json={
                "message": "Should I carry an umbrella today?",
                "persona": "general",
                "location": {
                    "name": "Coimbatore",
                    "latitude": 11.0168,
                    "longitude": 76.9558,
                    "source_type": "LAST_KNOWN_LOCATION",
                    "is_stale": True
                },
                "language": "en"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_manual_location_type_handled(self):
        """Manual location selection works seamlessly."""
        res = client.post(
            "/api/v1/chat",
            json={
                "message": "Can I go cycling this evening?",
                "persona": "commuter",
                "location": {
                    "name": "Salem",
                    "source_type": "MANUAL_LOCATION"
                },
                "language": "en"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
