# WeatherGPT — Data Sources & Data Strategy

## 1. Purpose

This document defines where WeatherGPT obtains weather,
forecast, warning, historical and supporting information.

WeatherGPT must prioritize reliable and authoritative sources.

The system must never invent weather information when
data is unavailable.

---

# 2. Data Categories

WeatherGPT requires the following major data categories:

1. Current weather
2. Weather forecasts
3. Official weather warnings
4. Historical weather
5. Climate information
6. Geographic/location data
7. Weather knowledge and safety guidance
8. User/application data

---

# 3. Primary Meteorological Source — IMD

## India Meteorological Department

IMD should be treated as the primary authoritative source
for official Indian meteorological information wherever
the required data is available.

Potential data:

- Current weather
- Forecasts
- District forecasts
- Rainfall information
- Weather warnings
- Cyclone information
- Severe-weather information
- Meteorological bulletins

### Architecture

Mobile App
    ↓
FastAPI
    ↓
IMD Adapter
    ↓
IMD Data
    ↓
Normalization
    ↓
Weather Reasoner

---

# 4. IMD Adapter

We will NOT allow the rest of the application to depend
directly on IMD-specific formats.

Create an independent:

`IMDAdapter`

Responsibilities:

- Request IMD data
- Parse responses
- Validate data
- Convert data to our common schema
- Handle errors
- Record timestamps
- Handle unavailable endpoints

This allows the data source to be replaced without
changing the rest of the application.

---

# 5. Secondary Forecast Source

A secondary weather provider may be used for:

- Cross-checking forecasts
- Filling non-critical missing information
- Forecast comparison
- Demonstrating multi-source consistency

Candidate:

Open-Meteo

However, the exact provider must be validated before
production use.

---

# 6. Historical Weather Data

Candidate:

NASA POWER

Potential uses:

- Historical temperature
- Historical precipitation
- Climate analysis
- Long-term trends
- Historical comparisons

Historical data must be clearly separated from
real-time forecast information.

---

# 7. Multi-Source Comparison

Where appropriate, WeatherGPT may compare multiple
forecast sources.

Example:

IMD → Rain likely
Source B → Rain likely
Source C → Rain possible

↓

WeatherGPT:

"Forecast sources broadly agree that rain is possible."

If sources disagree:

"Forecast sources currently show disagreement."

IMPORTANT:

This is a source-consistency analysis.

It must NOT be presented as a scientifically
calibrated forecast probability.

---

# 8. Official Warning Data

Official warnings must receive the highest priority.

Potential warning information:

- Heavy rainfall
- Cyclone
- Thunderstorm
- Lightning
- Strong winds
- Heatwave
- Other severe weather

Processing:

Official Warning
      ↓
Validation
      ↓
Severity
      ↓
Location Matching
      ↓
User Notification
      ↓
AI Explanation

The LLM must never override an official warning.

---

# 9. Location Data

WeatherGPT requires location information.

Sources:

### A. Device GPS

Used when the user grants location permission.

### B. Manual Search

User searches for:

"Coimbatore"

### C. Conversational Location

Example:

"Weather there tomorrow?"

The system uses the previously identified
location when context is clear.

---

# 10. Geocoding

User location names must be converted into:

- Latitude
- Longitude
- Administrative region

Example:

Coimbatore
    ↓
Latitude
Longitude
District
State

The exact geocoding provider will be selected
after testing.

---

# 11. Weather Knowledge Base

The RAG system may contain trusted supporting
knowledge such as:

- Weather terminology
- Meteorological concepts
- Official safety guidance
- Disaster-management guidance
- Approved advisory information
- Definitions of weather alerts

This information is used for explanation.

IMPORTANT:

The knowledge base must NOT be treated as a source
of current weather conditions.

Current weather must come from live/verified
meteorological data.

---

# 12. User Data

The database may store:

### User

- User ID
- Name/optional display name
- Preferred language
- Location preference

### Preferences

- Preferred units
- Preferred language
- Notification settings
- Persona

### Persona

Possible values:

- Student
- Farmer
- Fisherman
- Traveller
- Disaster Response

Only necessary personal information should be stored.

---

# 13. Weather Data Schema

All external weather sources should eventually
be converted into a common internal structure.

Example:

```json
{
  "location": {
    "name": "Coimbatore",
    "latitude": 11.0168,
    "longitude": 76.9558
  },
  "observed_at": "2026-09-08T10:00:00",
  "temperature": 29,
  "humidity": 72,
  "rain_probability": 65,
  "wind_speed": 18,
  "weather_condition": "Rain",
  "source": "IMD",
  "retrieved_at": "2026-09-08T10:10:00"
}