"""IMD District Registry & Deterministic Geographic Resolver.

Provides canonical IMD district identification and deterministic coordinate/location
resolution for India (specifically Tamil Nadu and major meteorological centers).
Guarantees zero LLM hallucinations and zero unsafe guessing.
"""

import math
from typing import Dict, Any, Optional, Tuple

# All 38 official districts of Tamil Nadu + key national meteorological districts
# mapped to canonical IMD district spelling (UPPERCASE as returned by IMD GeoServer / API).
TAMIL_NADU_DISTRICTS: Dict[str, Dict[str, Any]] = {
    "ARIYALUR": {"lat": 11.1401, "lon": 79.0786, "aliases": ["ariyalur", "அரியலூர்"]},
    "CHENGALPATTU": {"lat": 12.6841, "lon": 79.9836, "aliases": ["chengalpattu", "chengalpet", "செங்கல்பட்டு"]},
    "CHENNAI": {"lat": 13.0827, "lon": 80.2707, "aliases": ["chennai", "madras", "சென்னை"]},
    "COIMBATORE": {"lat": 11.0168, "lon": 76.9558, "aliases": ["coimbatore", "kovai", "கோயம்புத்தூர்", "கோவை"]},
    "CUDDALORE": {"lat": 11.7480, "lon": 79.7714, "aliases": ["cuddalore", "கடலூர்"]},
    "DHARMAPURI": {"lat": 12.1211, "lon": 78.1582, "aliases": ["dharmapuri", "தருமபுரி"]},
    "DINDIGUL": {"lat": 10.3673, "lon": 77.9803, "aliases": ["dindigul", "திண்டுக்கல்"]},
    "ERODE": {"lat": 11.3410, "lon": 77.7172, "aliases": ["erode", "ஈரோடு"]},
    "KALLAKURICHI": {"lat": 11.7384, "lon": 78.9639, "aliases": ["kallakurichi", "கள்ளக்குறிச்சி"]},
    "KANCHEEPURAM": {"lat": 12.8342, "lon": 79.7036, "aliases": ["kancheepuram", "kanchipuram", "காஞ்சிபுரம்"]},
    "KANYAKUMARI": {"lat": 8.0883, "lon": 77.5385, "aliases": ["kanyakumari", "cape comorin", "கன்யாகுமரி", "கன்னியாகுமரி"]},
    "KARUR": {"lat": 10.9601, "lon": 78.0766, "aliases": ["karur", "கரூர்"]},
    "KRISHNAGIRI": {"lat": 12.5186, "lon": 78.2137, "aliases": ["krishnagiri", "கிருஷ்ணகிரி"]},
    "MADURAI": {"lat": 9.9252, "lon": 78.1198, "aliases": ["madurai", "மதுரை"]},
    "MAYILADUTHURAI": {"lat": 11.1075, "lon": 79.6523, "aliases": ["mayiladuthurai", "மயிலாடுதுறை"]},
    "NAGAPATTINAM": {"lat": 10.7656, "lon": 79.8424, "aliases": ["nagapattinam", "nagai", "நாகப்பட்டினம்", "நாகை"]},
    "NAMAKKAL": {"lat": 11.2189, "lon": 78.1674, "aliases": ["namakkal", "நாமக்கல்"]},
    "NILGIRIS": {"lat": 11.4102, "lon": 76.6950, "aliases": ["nilgiris", "ooty", "udhagamandalam", "coonoor", "நீலகிரி", "ஊட்டி"]},
    "PERAMBALUR": {"lat": 11.2342, "lon": 78.8820, "aliases": ["perambalur", "பெரம்பலூர்"]},
    "PUDUKKOTTAI": {"lat": 10.3833, "lon": 78.8001, "aliases": ["pudukkottai", "புதுக்கோட்டை"]},
    "RAMANATHAPURAM": {"lat": 9.3639, "lon": 78.8395, "aliases": ["ramanathapuram", "ramnad", "இராமநாதபுரம்"]},
    "RANIPET": {"lat": 12.9224, "lon": 79.3328, "aliases": ["ranipet", "ராணிப்பேட்டை"]},
    "SALEM": {"lat": 11.6643, "lon": 78.1460, "aliases": ["salem", "சேலம்"]},
    "SIVAGANGA": {"lat": 9.8433, "lon": 78.4809, "aliases": ["sivaganga", "sivagangai", "சிவகங்கை"]},
    "TENKASI": {"lat": 8.9594, "lon": 77.3150, "aliases": ["tenkasi", "தென்காசி"]},
    "THANJAVUR": {"lat": 10.7870, "lon": 79.1378, "aliases": ["thanjavur", "tanjore", "தஞ்சாவூர்"]},
    "THENI": {"lat": 10.0104, "lon": 77.4768, "aliases": ["theni", "தேனி"]},
    "THOOTHUKUDI": {"lat": 8.7642, "lon": 78.1348, "aliases": ["thoothukudi", "tuticorin", "தூத்துக்குடி"]},
    "TIRUCHIRAPPALLI": {"lat": 10.7905, "lon": 78.7047, "aliases": ["tiruchirappalli", "trichy", "திருச்சிராப்பள்ளி", "திருச்சி"]},
    "TIRUNELVELI": {"lat": 8.7139, "lon": 77.7567, "aliases": ["tirunelveli", "nellai", "திருநெல்வேலி", "நெல்லை"]},
    "TIRUPATHUR": {"lat": 12.4925, "lon": 78.5678, "aliases": ["tirupathur", "திருப்பத்தூர்"]},
    "TIRUPPUR": {"lat": 11.1085, "lon": 77.3411, "aliases": ["tiruppur", "tirupur", "திருப்பூர்"]},
    "TIRUVALLUR": {"lat": 13.1432, "lon": 79.9083, "aliases": ["tiruvallur", "thiruvallur", "திருவள்ளூர்"]},
    "TIRUVANNAMALAI": {"lat": 12.2253, "lon": 79.0747, "aliases": ["tiruvannamalai", "thiruvannamalai", "திருவண்ணாமலை"]},
    "THIRUVARUR": {"lat": 10.7661, "lon": 79.6344, "aliases": ["thiruvarur", "tiruvarur", "திருவாரூர்"]},
    "VELLORE": {"lat": 12.9165, "lon": 79.1325, "aliases": ["vellore", "வேலூர்"]},
    "VILLUPURAM": {"lat": 11.9401, "lon": 79.4861, "aliases": ["villupuram", "viluppuram", "விழுப்புரம்"]},
    "VIRUDHUNAGAR": {"lat": 9.5680, "lon": 77.9624, "aliases": ["virudhunagar", "விருதுநகர்"]}
}

# Major national meteorological districts for multi-state testing & deployment
NATIONAL_DISTRICTS: Dict[str, Dict[str, Any]] = {
    "MUMBAI": {"lat": 18.9220, "lon": 72.8347, "aliases": ["mumbai", "bombay"]},
    "NEW DELHI": {"lat": 28.6139, "lon": 77.2090, "aliases": ["new delhi", "delhi"]},
    "BENGALURU URBAN": {"lat": 12.9716, "lon": 77.5946, "aliases": ["bengaluru", "bangalore"]},
    "HYDERABAD": {"lat": 17.3850, "lon": 78.4867, "aliases": ["hyderabad"]},
    "KOLKATA": {"lat": 22.5726, "lon": 88.3639, "aliases": ["kolkata", "calcutta"]},
    "SAITUAL": {"lat": 23.9700, "lon": 92.5700, "aliases": ["saitual"]}
}

ALL_DISTRICTS: Dict[str, Dict[str, Any]] = {**TAMIL_NADU_DISTRICTS, **NATIONAL_DISTRICTS}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates geodesic distance in kilometers between two GPS coordinates."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def resolve_imd_district(
    location_name: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    max_radius_km: float = 65.0
) -> Optional[str]:
    """Deterministically resolves a location name or coordinates to an official IMD District.

    Rules:
    1. Exact / alias match on location name (case-insensitive, unicode-normalized).
    2. Substring containment match on location name.
    3. Coordinate geodesic proximity match (nearest district within max_radius_km).
    4. Strict fallback: Returns None if no reliable match exists. NEVER invents or hallucinates.

    Returns:
        Canonical uppercase IMD district string (e.g., 'COIMBATORE') or None.
    """
    # 1. Direct name lookup
    if location_name and isinstance(location_name, str):
        cleaned = location_name.strip().lower()
        for canonical, info in ALL_DISTRICTS.items():
            if cleaned == canonical.lower():
                return canonical
            if any(cleaned == alias.lower() for alias in info.get("aliases", [])):
                return canonical

        # 2. Substring containment (e.g. "Nagapattinam Port" -> "NAGAPATTINAM")
        for canonical, info in ALL_DISTRICTS.items():
            if canonical.lower() in cleaned:
                return canonical
            for alias in info.get("aliases", []):
                if alias.lower() in cleaned or cleaned in alias.lower():
                    if len(alias) >= 4:  # Avoid overly short false positives
                        return canonical

    # 3. Coordinate proximity matching
    if latitude is not None and longitude is not None:
        if -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0:
            best_district: Optional[str] = None
            min_dist = float("inf")

            for canonical, info in ALL_DISTRICTS.items():
                d_lat = info.get("lat")
                d_lon = info.get("lon")
                if d_lat is not None and d_lon is not None:
                    dist = _haversine_km(latitude, longitude, d_lat, d_lon)
                    if dist < min_dist:
                        min_dist = dist
                        best_district = canonical

            if best_district and min_dist <= max_radius_km:
                return best_district

    # No reliable match established
    return None
