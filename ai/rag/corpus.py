"""Authoritative Meteorological Knowledge Corpus for WeatherGPT RAG.

Curated from official Indian Meteorological Department (IMD) Standard Operating Procedures,
National Disaster Management Authority (NDMA) guidelines, and State Disaster Management Authorities.
"""

from typing import List
from ai.rag.schema import KnowledgeDocument

AUTHORITATIVE_DOCUMENTS: List[KnowledgeDocument] = [
    KnowledgeDocument(
        id="doc_imd_rainfall_standards",
        title="IMD Standard Operating Procedure: Rainfall Classification and Thresholds",
        source="India Meteorological Department (IMD)",
        source_type="METEOROLOGICAL_STANDARD",
        topic="heavy_rain",
        language="en",
        authority_level="AUTHORITATIVE_GOVERNMENT",
        version="2024.1",
        updated_at="2024-06-01",
        content="""## IMD Rainfall Intensity Classifications
Official definitions used by the India Meteorological Department for 24-hour cumulative rainfall:
- Light Rain: 2.5 mm to 15.5 mm in 24 hours.
- Moderate Rain: 15.6 mm to 64.4 mm in 24 hours.
- Heavy Rain: 64.5 mm to 115.5 mm in 24 hours. Localized waterlogging in low-lying urban areas.
- Very Heavy Rain: 115.6 mm to 204.4 mm in 24 hours. Substantial inundation, stormwater drainage overflow, and agricultural flooding.
- Extremely Heavy Rain: 204.5 mm or more in 24 hours. Severe flash flood danger, widespread urban inundation, and life-threatening transport disruptions.

## Hydrological Impact and Flash Flood Criteria
Rainfall rates exceeding 100 mm in 1 hour or 200 mm in 24 hours represent flash flood risk. Commuters must avoid submerged subways and underpasses.
""",
        metadata={"domain": "precipitation", "jurisdiction": "India", "sop_ref": "IMD-MET-PRECIP-2024"}
    ),
    KnowledgeDocument(
        id="doc_imd_color_codes",
        title="IMD Weather Warning Color Codes and Action Protocol",
        source="India Meteorological Department (IMD)",
        source_type="OFFICIAL_GUIDELINE",
        topic="terminology",
        language="en",
        authority_level="AUTHORITATIVE_GOVERNMENT",
        version="2024.1",
        updated_at="2024-01-15",
        content="""## Color-Coded Warning System
The IMD issues daily 4-stage color-coded warnings to signal meteorological hazard severity:
- Green (No Warning): No action required. Weather conditions are normal with no severe events expected.
- Yellow (Watch / Be Updated): Weather conditions have potential to deteriorate over the next 48 to 72 hours. Stay informed about localized updates.
- Orange (Alert / Be Prepared): High likelihood of severe weather causing disruptions in transit, power, and agriculture. Prepare emergency supplies.
- Red (Warning / Take Action): Extreme and dangerous weather conditions imminent. High risk to life and infrastructure. Follow official evacuation or stay-at-home directives immediately.
""",
        metadata={"domain": "disaster_management", "jurisdiction": "India"}
    ),
    KnowledgeDocument(
        id="doc_imd_cyclone_stages",
        title="IMD Tropical Cyclone Classification and 4-Stage Warning System",
        source="India Meteorological Department (IMD)",
        source_type="METEOROLOGICAL_STANDARD",
        topic="cyclone",
        language="en",
        authority_level="AUTHORITATIVE_GOVERNMENT",
        version="2024.2",
        updated_at="2024-04-10",
        content="""## Tropical Cyclone Intensity Stages by Wind Speed
Wind speed classification over the Bay of Bengal and Arabian Sea:
- Depression: 31 to 49 km/h (17 to 27 knots).
- Deep Depression: 50 to 61 km/h (28 to 33 knots).
- Cyclonic Storm: 62 to 87 km/h (34 to 47 knots). Gale wind threshold; marine operations halted.
- Severe Cyclonic Storm: 88 to 117 km/h (48 to 63 knots).
- Very Severe Cyclonic Storm: 118 to 165 km/h (64 to 89 knots).
- Extremely Severe Cyclonic Storm: 166 to 221 km/h (90 to 119 knots).
- Super Cyclonic Storm: 222 km/h and above (120 knots and above).

## 4-Stage Cyclone Warning Protocol
1. Pre-Cyclone Watch: Issued 72 hours before cyclonic disturbance onset.
2. Cyclone Alert (Yellow): Issued 48 hours in advance for coastal districts.
3. Cyclone Warning (Orange): Issued 24 hours in advance specifying landfall location.
4. Post-Landfall Outlook (Red): Issued 12 hours prior to landfall detailing inland gale and heavy rain impacts.
""",
        metadata={"domain": "cyclone", "jurisdiction": "North Indian Ocean"}
    ),
    KnowledgeDocument(
        id="doc_ndma_cyclone_safety",
        title="NDMA Cyclone Disaster Preparedness and Safety Protocol",
        source="National Disaster Management Authority (NDMA)",
        source_type="SAFETY_PROTOCOL",
        topic="cyclone",
        language="en",
        authority_level="AUTHORITATIVE_GOVERNMENT",
        version="2023.2",
        updated_at="2023-11-20",
        content="""## Coastal and General Public Cyclone Safety Rules
- Fishermen must completely avoid venturing into open sea or coastal waters during gale warnings.
- Keep emergency battery lights, portable radio, non-perishable food, potable water, and first-aid kits ready.
- Secure roofs, loose tin sheets, and outdoor fixtures. Trim hanging tree branches near power lines.
- Do not venture outside during the 'eye of the storm' when calm temporarily prevails; gale winds resume suddenly from the opposite direction.
- Relocate to designated cyclone relief shelters immediately when directed by local disaster authorities.
""",
        metadata={"domain": "cyclone_safety", "authority": "NDMA"}
    ),
    KnowledgeDocument(
        id="doc_ndma_heavy_rain_flood",
        title="NDMA Heavy Rain, Urban Waterlogging and Flood Safety Protocol",
        source="National Disaster Management Authority (NDMA)",
        source_type="SAFETY_PROTOCOL",
        topic="heavy_rain",
        language="en",
        authority_level="AUTHORITATIVE_GOVERNMENT",
        version="2023.1",
        updated_at="2023-08-15",
        content="""## Urban Waterlogging & Flood Precautions
- Stay clear of waterlogged streets, flooded subways, and storm drains.
- Do not drive or walk through flood waters; 15 cm of moving water can knock down an adult.
- Keep away from fallen electrical wires, transformers, and submerged utility poles to prevent electrocution.
- Farmers should maintain drainage outlets in agricultural fields to minimize root inundation.
""",
        metadata={"domain": "flood_safety", "authority": "NDMA"}
    ),
    KnowledgeDocument(
        id="doc_ndma_lightning_safety",
        title="NDMA Lightning Safety Guidelines and the 30-30 Rule",
        source="National Disaster Management Authority (NDMA)",
        source_type="SAFETY_PROTOCOL",
        topic="thunderstorm",
        language="en",
        authority_level="AUTHORITATIVE_GOVERNMENT",
        version="2024.1",
        updated_at="2024-05-01",
        content="""## Lightning Safety and Shelter Standards
- Apply the 30-30 Rule: If the time between seeing lightning and hearing thunder is less than 30 seconds, immediately take shelter. Remain indoors for at least 30 minutes after the last thunder clap.
- Seek shelter in fully enclosed buildings or metal-roofed vehicles.
- Avoid open fields, elevated ridges, metal fences, and standing under isolated tall trees.
- Disconnect AC mains power to computers, television sets, and sensitive appliances during active electrical storms.
""",
        metadata={"domain": "lightning_safety", "authority": "NDMA"}
    ),
    KnowledgeDocument(
        id="doc_ndma_heatwave_standards",
        title="IMD Criteria and NDMA Safety Measures for Heatwaves",
        source="India Meteorological Department (IMD)",
        source_type="METEOROLOGICAL_STANDARD",
        topic="heatwave",
        language="en",
        authority_level="AUTHORITATIVE_GOVERNMENT",
        version="2024.1",
        updated_at="2024-03-25",
        content="""## IMD Heatwave Criteria
- Plains: Heatwave declared when maximum temperature reaches >= 40.0°C and departure from normal is >= 4.5°C, or maximum temperature >= 45.0°C unconditionally.
- Severe Heatwave: Departure from normal >= 6.5°C, or maximum temperature >= 47.0°C.
- Coastal Areas: Maximum temperature reaches >= 37.0°C with departure >= 4.5°C.

## Safety Guidelines
- Maintain hydration with water, Oral Rehydration Solutions (ORS), buttermilk, and coconut water.
- Minimize direct outdoor sun exposure between 12:00 PM and 3:00 PM.
- Wear lightweight, loose, light-colored cotton clothing.
""",
        metadata={"domain": "heatwave", "authority": "IMD/NDMA"}
    ),
    # Tamil language document
    KnowledgeDocument(
        id="doc_tnsdma_safety_tamil",
        title="தமிழ்நாடு பேரிடர் மேலாண்மை ஆணையம் — புயல், கனமழை மற்றும் இடிமின்னல் பாதுகாப்பு நெறிமுறைகள்",
        source="Tamil Nadu SDMA (TNSDMA)",
        source_type="SAFETY_PROTOCOL",
        topic="cyclone",
        language="ta",
        authority_level="AUTHORITATIVE_GOVERNMENT",
        version="2024.1",
        updated_at="2024-07-01",
        content="""## புயல் பாதுகாப்பு நெறிமுறைகள்
- மீனவர்கள் கடலுக்குள் மீன்பிடிக்கச் செல்ல வேண்டாம் என எச்சரிக்கப்படுகிறார்கள்.
- அவசர விளக்குகள், வானொலி மற்றும் முதலுதவி பெட்டிகளைத் தயார் நிலையில் வைக்கவும்.
- கதவுகள், ஜன்னல்களைப் பாதுகாப்பாகப் பூட்டவும். தற்காலிக மேற்கூரைகளைப் பலப்படுத்தவும்.
- தேவைப்பட்டால் அதிகாரப்பூர்வ புயல் பாதுகாப்பு முகாம்களுக்குச் செல்லவும்.

## கனமழை மற்றும் வெள்ள பாதுகாப்பு
- நீர் தேங்கிய பகுதிகள் மற்றும் மின் கம்பங்களை விட்டு தள்ளி இருக்கவும்.
- மரங்கள் அல்லது பலவீனமான கூரைகளின் கீழ் வாகனங்களை நிறுத்த வேண்டாம்.
- விவசாயிகள் வயல்களில் தேங்கும் நீரை வெளியேற்ற வடிகால்களைச் சரிசெய்யவும்.

## இடி மின்னல் பாதுகாப்பு
- இடி மின்னலின் போது கான்கிரீட் கட்டிடங்கள் அல்லது வாகனங்களுக்குள் தஞ்சமடையவும்.
- தனித்து நிற்கும் மரங்கள் அல்லது திறந்த வெளிகளில் நிற்க வேண்டாம்.
- மின்னணு சாதனங்களை இணைப்பிலிருந்து துண்டிக்கவும்.
""",
        metadata={"domain": "disaster_safety", "language": "Tamil", "jurisdiction": "Tamil Nadu"}
    )
]
