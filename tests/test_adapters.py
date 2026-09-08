import pytest
from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.nasa_power_adapter import NasaPowerAdapter
from backend.services.geocoding_service import GeocodingService
from backend.services.weather_manager import WeatherManager

@pytest.mark.asyncio
async def test_imd_adapter_coimbatore():
    adapter = IMDAdapter()
    obs = await adapter.get_current_weather(11.0168, 76.9558, "Coimbatore")
    assert obs["location_name"] == "Coimbatore"
    assert obs["source"] == "IMD"
    assert "temperature" in obs

    alerts = await adapter.get_official_alerts(11.0168, 76.9558, "Coimbatore")
    assert isinstance(alerts, list)

@pytest.mark.asyncio
async def test_imd_adapter_nagapattinam_hero():
    adapter = IMDAdapter()
    obs = await adapter.get_current_weather(10.7656, 79.8424, "Nagapattinam")
    assert obs["location_name"] == "Nagapattinam"
    assert obs["rain_probability"] == 85.0

    alerts = await adapter.get_official_alerts(10.7656, 79.8424, "Nagapattinam")
    assert len(alerts) >= 1
    assert "Heavy Rain" in alerts[0]["title"]

@pytest.mark.asyncio
async def test_geocoding_service():
    geo = GeocodingService()
    res = await geo.resolve_location("Coimbatore")
    assert res["name"] == "Coimbatore"
    assert res["latitude"] == 11.0168

    res_tamil = await geo.resolve_location("கோயம்புத்தூர்")
    assert res_tamil["name"] == "Coimbatore"

@pytest.mark.asyncio
async def test_weather_manager():
    manager = WeatherManager()
    data = await manager.get_current_weather(location_name="Coimbatore")
    assert "weather" in data
    assert "alerts" in data
    assert "comparison" in data
    assert data["weather"]["temperature"] > 0
