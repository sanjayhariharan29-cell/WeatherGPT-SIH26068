import httpx
from typing import Dict, Any, Optional, List

# Known Tamil Nadu location coordinates map for high-speed offline/hackathon fallback
KNOWN_LOCATIONS: Dict[str, Dict[str, Any]] = {
    "coimbatore": {"name": "Coimbatore", "district": "Coimbatore", "state": "Tamil Nadu", "latitude": 11.0168, "longitude": 76.9558},
    "கோயம்புத்தூர்": {"name": "Coimbatore", "district": "Coimbatore", "state": "Tamil Nadu", "latitude": 11.0168, "longitude": 76.9558},
    "nagapattinam": {"name": "Nagapattinam", "district": "Nagapattinam", "state": "Tamil Nadu", "latitude": 10.7656, "longitude": 79.8424},
    "நாகப்பட்டினம்": {"name": "Nagapattinam", "district": "Nagapattinam", "state": "Tamil Nadu", "latitude": 10.7656, "longitude": 79.8424},
    "chennai": {"name": "Chennai", "district": "Chennai", "state": "Tamil Nadu", "latitude": 13.0827, "longitude": 80.2707},
    "சென்னை": {"name": "Chennai", "district": "Chennai", "state": "Tamil Nadu", "latitude": 13.0827, "longitude": 80.2707},
    "madurai": {"name": "Madurai", "district": "Madurai", "state": "Tamil Nadu", "latitude": 9.9252, "longitude": 78.1198},
    "மதுரை": {"name": "Madurai", "district": "Madurai", "state": "Tamil Nadu", "latitude": 9.9252, "longitude": 78.1198},
    "tiruchirappalli": {"name": "Tiruchirappalli", "district": "Tiruchirappalli", "state": "Tamil Nadu", "latitude": 10.7905, "longitude": 78.7047},
    "trichy": {"name": "Tiruchirappalli", "district": "Tiruchirappalli", "state": "Tamil Nadu", "latitude": 10.7905, "longitude": 78.7047},
    "tirunelveli": {"name": "Tirunelveli", "district": "Tirunelveli", "state": "Tamil Nadu", "latitude": 8.7139, "longitude": 77.7567},
    "salem": {"name": "Salem", "district": "Salem", "state": "Tamil Nadu", "latitude": 11.6643, "longitude": 78.1460},
}

class GeocodingService:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    async def resolve_location(self, query: str) -> Dict[str, Any]:
        """Resolves location query string (English/Tamil) into coordinates."""
        cleaned = query.strip().lower()
        if cleaned in KNOWN_LOCATIONS:
            return KNOWN_LOCATIONS[cleaned]

        # Try Nominatim OpenStreetMap Geocoding with fallback
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
            headers = {"User-Agent": "WeatherGPT-SIH26068/1.0"}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and resp.json():
                    data = resp.json()[0]
                    return {
                        "name": data.get("display_name", query).split(",")[0],
                        "district": data.get("display_name", query).split(",")[1].strip() if "," in data.get("display_name", "") else query,
                        "state": "Tamil Nadu",
                        "latitude": float(data["lat"]),
                        "longitude": float(data["lon"])
                    }
        except Exception:
            pass

        # Default fallback to Coimbatore if unknown
        return KNOWN_LOCATIONS["coimbatore"]

    async def search_locations(self, query: str) -> List[Dict[str, Any]]:
        """Search locations matching query string."""
        cleaned = query.strip().lower()
        results = []
        for key, loc in KNOWN_LOCATIONS.items():
            if cleaned in key or cleaned in loc["name"].lower():
                if loc not in results:
                    results.append(loc)
        if not results:
            results.append(KNOWN_LOCATIONS["coimbatore"])
        return results
