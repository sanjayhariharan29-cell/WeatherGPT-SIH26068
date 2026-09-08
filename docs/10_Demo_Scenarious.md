# WeatherGPT — Demo Scenarios

## 1. Purpose

The demo must prove that WeatherGPT is more than a normal weather application or chatbot.

The demonstration should show:

- Real-time weather retrieval
- Natural-language understanding
- Multilingual interaction
- Weather reasoning
- Official warning prioritization
- Personalized decision support
- Historical/climate analysis
- Voice interaction
- Source transparency

The demo should focus on a small number of strong scenarios rather than showing every feature.

---

## 2. Demo Strategy

The main demo should follow:

Problem
↓
User asks naturally
↓
WeatherGPT understands intent/context
↓
Live meteorological data retrieved
↓
Weather Reasoner analyses information
↓
Decision Engine determines relevance
↓
AI explains result
↓
User receives actionable answer

---

## 3. Hero Scenario — "Should I Go Outside?"

### User

"Naalaiku college pogalama?"

Meaning:

"Can I go to college tomorrow?"

### System detects

- Language = Tanglish
- Intent = outdoor_decision
- Activity = college travel
- Date = tomorrow
- Persona = student
- Location = current/default location

### System retrieves

- Forecast
- Rain probability
- Wind
- Temperature
- Official warnings

### Weather Reasoner determines

- Expected hazard
- Hazard severity
- Forecast consistency
- Official warning status

### Decision Engine

Student
+
College travel
+
Weather risk
↓
Actionable recommendation

### Example response

"நாளை கனமழைக்கான வாய்ப்பு உள்ளது. வெளிப்பயணத்திற்கு முன்னர் அதிகாரப்பூர்வ வானிலை எச்சரிக்கையை சரிபார்க்கவும்."

### Important

WeatherGPT must NOT claim:

"Your college will be closed."

It can recommend checking the institution's official announcement.

---

## 4. Live Weather Scenario

### User

"What is the weather in Coimbatore right now?"

### Expected behavior

1. Resolve location.
2. Retrieve current weather.
3. Display temperature.
4. Display rainfall/precipitation information.
5. Display wind and humidity.
6. Display source.
7. Display data timestamp.

### Judge-visible result

The answer is based on retrieved meteorological data rather than a static LLM response.

---

## 5. Tamil Scenario

### User

"இன்று கோயம்புத்தூரில் மழை வருமா?"

### Expected behavior

- Detect Tamil
- Extract location
- Identify rainfall intent
- Retrieve forecast
- Respond in Tamil

The underlying weather data must remain unchanged.

---

## 6. Tanglish Scenario

### User

"Naalaiku morning Coimbatore la mazhai varuma?"

### Expected extraction

- Language = Tanglish
- Intent = rain_forecast
- Location = Coimbatore
- Date = tomorrow
- Time = morning
- Variable = rainfall

The system should answer naturally without requiring formal English.

---

## 7. Follow-up Question Scenario

### User

"Will it rain tomorrow?"

WeatherGPT:

"Rain is possible tomorrow afternoon."

### Follow-up

"What about 7 AM?"

### Expected behavior

The system remembers:

- Location
- Date
- Weather variable

and changes only:

- Time = 07:00

This demonstrates conversational context.

---

## 8. Official Warning Scenario

### User

"Is it safe to travel tomorrow?"

### System checks

- Forecast
- Active official warnings
- Hazard severity

If an official severe-weather warning exists:

Official Warning
↓
Highest priority
↓
AI explanation

### Example response

"An official weather warning is active for this location during the requested period.

Avoid unnecessary travel and follow official authorities' instructions."

The AI must never weaken or contradict an official warning.

---

## 9. Source Agreement Scenario

WeatherGPT can compare available forecast sources.

Example:

IMD:
Heavy rainfall expected

Secondary source:
Heavy rainfall expected

Result:

Source Agreement = High

The UI should explain that multiple available sources indicate a similar outcome.

---

## 10. Conflicting Sources Scenario

Example:

IMD:
Low rainfall indication

Secondary source:
High rainfall indication

Result:

Source Agreement = Low

### Expected response

"Forecast sources differ for this period. The official warning status should be treated as the higher-priority safety signal."

The system must not artificially create certainty.

---

## 11. Farmer Advisory Scenario

### User

"I'm a farmer. Heavy rain is expected tomorrow. What should I do?"

### System detects

- Persona = Farmer
- Hazard = Heavy rain
- Date = tomorrow

### Example response

"Heavy rainfall is expected. Check field drainage, protect vulnerable crops, and avoid unnecessary irrigation immediately before the expected rainfall."

The advice must remain general guidance and must not guarantee an agricultural outcome.

---

## 12. Fisherman / Marine Safety Scenario

### User

"I'm planning to go fishing tomorrow. What should I check?"

### System checks

- Weather forecast
- Wind
- Official warnings
- Relevant marine information if available

The response should direct the user toward official marine/weather warnings when relevant.

WeatherGPT must not present itself as a replacement for official marine safety instructions.

---

## 13. Historical Weather Scenario

### User

"How has rainfall changed in Coimbatore over the last five years?"

### Processing

Historical Data
↓
Aggregation
↓
Trend Analysis
↓
Explanation

The response must distinguish historical observations from future forecasts.

---

## 14. Climate Trend Scenario

### User

"Has the average temperature increased in this area?"

### Processing

1. Retrieve historical data.
2. Calculate/use a defined trend methodology.
3. Show the selected time period.
4. Explain the trend.
5. Avoid claiming correlation automatically proves causation.

### Example

"Average temperature shows an increasing trend over the selected period."

---

## 15. Voice Scenario

### User speaks

"Naalaiku mazhai varuma?"

### Pipeline

Voice
↓
Speech-to-Text
↓
Intent Detection
↓
Weather Retrieval
↓
Reasoning
↓
AI Response
↓
Text-to-Speech

The response should be available in the appropriate language.

---

## 16. No Live Data Scenario

Simulate weather-provider failure.

Live API
↓
Failure
↓
Check Cache

If valid cached data exists:

"Live data is temporarily unavailable. The latest available forecast was retrieved at 10:15 AM."

If no usable data exists:

"I couldn't retrieve current weather information for this location right now."

The system must never fabricate weather information.

---

## 17. No Location Scenario

### User

"Will it rain tomorrow?"

If no location is available:

"What location should I check?"

The system should not guess the user's location.

---

## 18. General Weather Knowledge Scenario

### User

"Why does humidity feel uncomfortable?"

### Processing

Question
↓
Weather Knowledge
↓
RAG
↓
LLM Explanation

This demonstrates that WeatherGPT can answer weather-related knowledge questions without pretending every question requires a forecast.

---

## 19. Demo UI

The main screen should contain:

WeatherGPT
Coimbatore

Weather Status

29°C
Rain: 70%
Wind: 18 km/h

Source: IMD
Updated: 10:10 AM

Ask WeatherGPT...
🎤

For important warnings:

OFFICIAL WEATHER WARNING

Heavy Rain Warning

Source: IMD
Valid until: 8:00 PM

---

## 20. Judge Interaction Flow

### Step 1

Open WeatherGPT.

### Step 2

Ask:

"What's the weather in Coimbatore?"

### Step 3

Ask in Tanglish:

"Naalaiku morning mazhai varuma?"

### Step 4

Ask:

"Should I go to college?"

### Step 5

Show:

- Weather data
- Forecast
- Reasoning
- Source
- Timestamp
- Recommendation

### Step 6

Show an official warning scenario.

### Step 7

Switch to Tamil voice interaction.

### Step 8

Show historical/climate analysis.

---

## 21. Demo Data Strategy

The live demo should use real data whenever possible.

Deterministic fallback/demo datasets should exist for scenarios that cannot be reliably reproduced during judging.

Suggested scenarios:

- Normal weather
- Heavy rainfall
- Official warning
- Conflicting sources
- API failure

Demo data must be clearly marked internally as simulation/test data.

Never present simulated information as live official data.

---

## 22. Demo Performance Targets

Target:

- Fast initial app load
- Weather response within a few seconds
- Chat response within a few seconds
- Low voice-processing latency
- Immediate warning display once data is retrieved

Exact performance targets will be finalized after implementation benchmarking.

---

## 23. What the Demo Must Prove

### 1. Understand

WeatherGPT understands natural-language weather questions.

### 2. Retrieve

WeatherGPT retrieves real meteorological information.

### 3. Reason

WeatherGPT interprets available information and uncertainty.

### 4. Personalize

WeatherGPT converts weather information into user-relevant guidance.

### 5. Communicate

WeatherGPT provides understandable multilingual and voice-friendly interaction.

---

## 24. Anti-Demo Rules

Do NOT:

- Use fake live weather without disclosure.
- Claim AI predicted weather independently.
- Claim 100% accuracy.
- Invent official warnings.
- Hide data timestamps.
- Hide sources.
- Contradict official warnings.
- Depend entirely on internet access without fallback.
- Demonstrate many weak features instead of a few strong ones.

---

## 25. Final Hero Demonstration

User speaks in Tanglish:

"Naalaiku college pogalama?"

↓

WeatherGPT understands the question.

↓

Resolves:

- Location
- Date
- Activity
- Language
- Persona

↓

Retrieves live weather.

↓

Checks official warnings.

↓

Analyses weather risk.

↓

Personalizes the recommendation for a student.

↓

Responds in Tamil/Tanglish.

↓

Shows:

- Weather information
- Source
- Timestamp
- Warning status
- Recommendation

This should be the centerpiece of the SIH demonstration.

---

## 26. Demo Status

Status: DRAFT

Before final demo:

- Select exact live locations.
- Select reproducible weather scenarios.
- Prepare fallback datasets.
- Test live APIs.
- Test warning scenario.
- Test Tamil.
- Test Tanglish.
- Test voice.
- Test API failure.
- Benchmark latency.
- Prepare 3-minute demo.
- Prepare 5-minute extended demo.














































