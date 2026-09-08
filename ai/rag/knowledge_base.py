"""Weather Knowledge Base & RAG Safety Guidance for WeatherGPT.

Provides curated official safety advice, disaster protocols,
and meteorological terminology per docs/06_Data_sources.md and docs/09_AI_Design.md.
"""

from typing import Dict, List, Optional

# Curated meteorological domain knowledge & IMD disaster safety protocols
SAFETY_KNOWLEDGE_CORPUS: Dict[str, Dict[str, str]] = {
    "cyclone": {
        "title": "IMD Cyclone Safety Guidance",
        "guidance_en": (
            "Keep emergency battery lights, radio, and first-aid kits ready. "
            "Secure doors, windows, and outdoor tin sheets. "
            "Fishermen must completely avoid venturing into open sea or coastal waters. "
            "Move to higher ground or designated cyclone relief shelters if advised by authorities."
        ),
        "guidance_ta": (
            "அவசர விளக்குகள், வானொலி மற்றும் முதலுதவி பெட்டிகளைத் தயார் நிலையில் வைக்கவும். "
            "கதவுகள், ஜன்னல்களைப் பாதுகாப்பாகப் பூட்டவும். "
            "மீனவர்கள் கடலுக்குள் செல்ல வேண்டாம். "
            "தேவைப்பட்டால் அதிகாரப்பூர்வ புயல் பாதுகாப்பு முகாம்களுக்குச் செல்லவும்."
        )
    },
    "heavy_rain": {
        "title": "IMD Heavy Rain & Flood Safety Protocol",
        "guidance_en": (
            "Stay clear of waterlogged roads, electrical poles, and low-lying storm drains. "
            "Avoid parking vehicles under large trees or weak structures. "
            "Farmers should ensure clear drainage channels to prevent field inundation."
        ),
        "guidance_ta": (
            "நீர் தேங்கிய பகுதிகள் மற்றும் மின் கம்பங்களை விட்டு தள்ளி இருக்கவும். "
            "மரங்கள் அல்லது பலவீனமான கூரைகளின் கீழ் வாகனங்களை நிறுத்த வேண்டாம். "
            "விவசாயிகள் வயல்களில் தேங்கும் நீரை வெளியேற்ற வடிகால்களைச் சரிசெய்யவும்."
        )
    },
    "thunderstorm": {
        "title": "Lightning & Thunderstorm Safety Precautions",
        "guidance_en": (
            "Seek shelter inside a sturdy, enclosed building or vehicle. "
            "Do not stand under isolated trees, metal towers, or in open agricultural fields. "
            "Unplug sensitive electronic equipment during active lightning activity."
        ),
        "guidance_ta": (
            "இடி மின்னலின் போது கான்கிரீட் கட்டிடங்கள் அல்லது வாகனங்களுக்குள் தஞ்சமடையவும். "
            "தனித்து நிற்கும் மரங்கள் அல்லது திறந்த வெளிகளில் நிற்க வேண்டாம். "
            "மின்னணு சாதனங்களை இணைப்பிலிருந்து துண்டிக்கவும்."
        )
    },
    "heatwave": {
        "title": "National Disaster Management Authority (NDMA) Heatwave Guidance",
        "guidance_en": (
            "Stay hydrated by consuming water, ORS, or traditional drinks like buttermilk. "
            "Avoid direct sun exposure between 12:00 PM and 3:00 PM. "
            "Wear light-colored, loose cotton clothing."
        ),
        "guidance_ta": (
            "அடிக்கடி தண்ணீர், மோர் அல்லது எலுமிச்சை சாறு அருந்தி நீர்ச்சத்துடன் இருக்கவும். "
            "நண்பகல் 12 மணி முதல் பிற்பகல் 3 மணி வரை நேரடி வெயிலில் செல்வதைத் தவிர்க்கவும். "
            "மெல்லிய பருத்தி ஆடைகளை அணியவும்."
        )
    }
}


def retrieve_safety_guidance(hazard_keywords: List[str], language: str = "en") -> List[str]:
    """Retrieves relevant meteorological safety notes based on detected hazards."""
    results: List[str] = []
    is_tamil = language in ("ta", "tanglish")

    for key, item in SAFETY_KNOWLEDGE_CORPUS.items():
        if any(key in h.lower() for h in hazard_keywords):
            text = item["guidance_ta"] if is_tamil else item["guidance_en"]
            results.append(f"{item['title']}: {text}")

    return results
