# WeatherGPT — SIH26068 Requirements

## 1. Problem Statement

**PS ID:** SIH26068

**Title:** WeatherGPT: Conversational AI for Weather Forecasting, Alerts, and Climate Information

**Organization:** Ministry of Earth Sciences (MoES)

**Department:** India Meteorological Department (IMD)

**Category:** Software

**Theme:** Disaster Management

---

## 2. Objective

Build an AI-powered conversational platform that integrates meteorological
datasets, forecasting models, and disaster-warning systems to provide
accurate, contextual, multilingual weather intelligence through
conversational interfaces.

---

# 3. Mandatory PS Capabilities

These are the capabilities explicitly mentioned in SIH26068.

### M1 — Real-Time Weather Information
The system must retrieve and provide current weather information.

### M2 — Natural-Language Weather Queries
Users must be able to ask weather-related questions using natural language.

### M3 — NWP Integration
The solution should integrate numerical weather prediction models such
as GFS/WRF.

### M4 — Extreme-Weather Alerts
The system should provide extreme-weather alerts and support
early-warning dissemination.

### M5 — Location-Based Forecasting
The system must provide location-specific forecasts and advisories.

### M6 — Indian-Language Support
The system must support multilingual interaction for Indian languages.

### M7 — Historical / Climate Analysis
The system should provide historical weather information and climate
trend analysis.

### M8 — Voice Interaction
The system should support voice interaction, particularly to improve
accessibility for rural users.

---

# 4. Expected Solution

The SIH problem statement expects:

- Mobile-based conversational AI platform
- Backend integration with meteorological databases
- Integration with meteorological websites/APIs
- AI/LLM-based query-understanding engine
- Scalable architecture for real-time data ingestion

---

# 5. Expected Outcomes

WeatherGPT should aim to provide:

- Faster weather-information dissemination
- Better accessibility to forecasts
- Improved disaster preparedness and response
- Intelligent weather decision support

Potential application areas include:

- Agriculture
- Aviation
- Marine activities
- Urban planning
- Disaster management
- General public weather awareness

---

# 6. Evaluation Areas

Our implementation should be optimized for:

- Accuracy
- Relevance
- Response latency
- Multilingual capability
- User interface
- Accessibility
- Scalability
- Innovation
- Real-time meteorological integration
- Voice-enabled interaction

---

# 7. Our Initial Product Direction

WeatherGPT will be developed as a mobile-first application.

Basic pipeline:

User
  ↓
Voice / Text
  ↓
NLP / Query Understanding
  ↓
Location + Time + Weather Intent
  ↓
Weather Data Layer
  ↓
Weather Reasoning
  ↓
Decision / Advisory Engine
  ↓
Grounded LLM Response
  ↓
Mobile Application

---

# 8. Important Engineering Rules

### R1 — No fabricated weather information

The LLM must not invent weather values, warnings, forecasts, or
meteorological facts.

### R2 — Official warnings have priority

Official meteorological warnings must take priority over AI-generated
interpretation.

### R3 — Source awareness

Weather responses should be traceable to the underlying weather data
or official information used to generate them.

### R4 — Data freshness

Every weather response should consider when the underlying data was
last updated.

### R5 — Failure handling

The application must have a fallback when a live weather source is
unavailable.

### R6 — Clear uncertainty

If the available data is uncertain, conflicting, stale, or incomplete,
WeatherGPT must communicate that uncertainty rather than pretending
to be certain.

---

# 9. Proposed MVP

The first working version should support:

- Mobile application
- User location
- Current weather
- Forecast
- Weather-related natural-language questions
- Tamil + English
- Voice input/output
- Weather alerts
- AI-generated grounded responses
- Conversation history
- Basic user profile/persona
- Database persistence

---

# 10. Not Building Initially

The following are NOT part of the first MVP:

- Training an LLM from scratch
- Building our own numerical weather prediction model
- Building our own weather satellite system
- Native SMS/WhatsApp alert infrastructure
- Large-scale Kubernetes infrastructure
- Supporting every Indian language initially

These can be considered later if time permits.

---

# 11. Requirement Priority

### 🔴 P0 — Critical

- Weather data retrieval
- Natural-language queries
- Location-based forecasting
- AI/LLM query understanding
- Mobile application
- Backend
- Real-time data integration
- Weather alerts
- Basic multilingual support

### 🟠 P1 — High Priority

- Voice interaction
- Weather reasoning
- Personalized advisories
- Historical weather analysis
- Data freshness
- Confidence/consistency information

### 🟢 P2 — Optional

- Additional Indian languages
- Advanced personalization
- Advanced climate analytics
- Proactive notifications
- Additional personas
- Advanced visualizations

---

# 12. Current Status

Status: PRE-CODING

Next steps:

1. Validate existing solutions
2. Identify our genuine innovation/gap
3. Define target users
4. Define user journeys
5. Finalize architecture
6. Finalize data sources
7. Design database
8. Define API contracts
9. Define AI/NLP architecture
10. Begin implementation
