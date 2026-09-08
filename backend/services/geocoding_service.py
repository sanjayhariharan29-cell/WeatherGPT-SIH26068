import math
import httpx
from typing import Dict, Any, Optional, List

# Known Tamil Nadu & India location coordinates map with timezone and country metadata
KNOWN_LOCATIONS: Dict[str, Dict[str, Any]] = {
    "coimbatore": {
        "name": "Coimbatore",
        "district": "Coimbatore",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "கோயம்புத்தூர்": {
        "name": "Coimbatore",
        "district": "Coimbatore",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "nagapattinam": {
        "name": "Nagapattinam",
        "district": "Nagapattinam",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 10.7656,
        "longitude": 79.8424,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "நாகப்பட்டினம்": {
        "name": "Nagapattinam",
        "district": "Nagapattinam",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 10.7656,
        "longitude": 79.8424,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "chennai": {
        "name": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "சென்னை": {
        "name": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "madurai": {
        "name": "Madurai",
        "district": "Madurai",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 9.9252,
        "longitude": 78.1198,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "மதுரை": {
        "name": "Madurai",
        "district": "Madurai",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 9.9252,
        "longitude": 78.1198,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "tiruchirappalli": {
        "name": "Tiruchirappalli",
        "district": "Tiruchirappalli",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 10.7905,
        "longitude": 78.7047,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "trichy": {
        "name": "Tiruchirappalli",
        "district": "Tiruchirappalli",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 10.7905,
        "longitude": 78.7047,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "tirunelveli": {
        "name": "Tirunelveli",
        "district": "Tirunelveli",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 8.7139,
        "longitude": 77.7567,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
    "salem": {
        "name": "Salem",
        "district": "Salem",
        "state": "Tamil Nadu",
        "country": "India",
        "latitude": 11.6643,
        "longitude": 78.1460,
        "timezone": "Asia/Kolkata",
        "source": "preset"
    },
}

class GeocodingService:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def validate_coordinates(self, lat: float, lon: float) -> None:
        """Validates latitude and longitude bounds strictly."""
        if lat is None or lon is None:
            raise ValueError("Latitude and longitude cannot be null.")
        if not isinstance(lat, (int, float)) or not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Invalid latitude {lat}. Latitude must be between -90 and +90 degrees.")
        if not isinstance(lon, (int, float)) or not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Invalid longitude {lon}. Longitude must be between -180 and +180 degrees.")

    async def resolve_location(self, query: str) -> Dict[str, Any]:
        """Resolves location query string (English/Tamil) into full location metadata."""
        if not query or not query.strip():
            return KNOWN_LOCATIONS["coimbatore"]

        cleaned = query.strip().lower()
        if cleaned in KNOWN_LOCATIONS:
            return KNOWN_LOCATIONS[cleaned]

        for key, loc in KNOWN_LOCATIONS.items():
            if cleaned in key or cleaned in loc["name"].lower():
                return loc

        # External Geocoding Fallback via Nominatim OSM
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
            headers = {"User-Agent": "WeatherGPT-SIH26068/1.0"}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and resp.json():
                    data = resp.json()[0]
                    lat = float(data["lat"])
                    lon = float(data["lon"])
                    self.validate_coordinates(lat, lon)
                    display = data.get("display_name", query).split(",")
                    name = display[0].strip()
                    district = display[1].strip() if len(display) > 1 else name
                    state = display[2].strip() if len(display) > 2 else "Tamil Nadu"

                    return {
                        "name": name,
                        "district": district,
                        "state": state,
                        "country": "India",
                        "latitude": lat,
                        "longitude": lon,
                        "timezone": "Asia/Kolkata",
                        "source": "nominatim_geocoding"
                    }
        except Exception:
            pass

        return KNOWN_LOCATIONS["coimbatore"]

    async def reverse_geocode(self, latitude: float, longitude: float, accuracy: Optional[float] = None) -> Dict[str, Any]:
        """Converts device GPS coordinates into nearest location and timezone."""
        self.validate_coordinates(latitude, longitude)

        # Find nearest known location by Euclidean distance
        closest_loc = None
        min_dist = float("inf")

        for loc in KNOWN_LOCATIONS.values():
            dist = math.hypot(latitude - loc["latitude"], longitude - loc["longitude"])
            if dist < min_dist:
                min_dist = dist
                closest_loc = loc

        if closest_loc and min_dist <= 1.0:  # Within ~100km radius
            return {
                "name": closest_loc["name"],
                "district": closest_loc["district"],
                "state": closest_loc["state"],
                "country": closest_loc["country"],
                "latitude": latitude,
                "longitude": longitude,
                "timezone": closest_loc["timezone"],
                "accuracy": accuracy,
                "source": "device_gps" if accuracy is not None else "reverse_geocoding"
            }

        # Fallback for arbitrary valid coordinates
        return {
            "name": f"Location ({latitude:.2f}, {longitude:.2f})",
            "district": "Custom District",
            "state": "Tamil Nadu",
            "country": "India",
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "Asia/Kolkata",
            "accuracy": accuracy,
            "source": "device_gps"
        }

    async def search_locations(self, query: str) -> List[Dict[str, Any]]:
        """Search locations matching query string."""
        if not query or not query.strip():
            return [KNOWN_LOCATIONS["coimbatore"]]

        cleaned = query.strip().lower()
        results = []
        for key, loc in KNOWN_LOCATIONS.items():
            if cleaned in key or cleaned in loc["name"].lower():
                if loc not in results:
                    results.append(loc)
        if not results:
            resolved = await self.resolve_location(query)
            results.append(resolved)
        return results
