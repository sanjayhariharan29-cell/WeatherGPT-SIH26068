# WeatherGPT — AI Design

## 1. Purpose

The AI layer converts natural-language weather questions into accurate, source-grounded and actionable responses.

The AI must NOT independently invent weather information.

Weather data and official warnings come from trusted data sources.

The AI is responsible for:

- Understanding the user's question
- Extracting intent and entities
- Resolving location and time
- Retrieving relevant weather data
- Reasoning over available data
- Generating personalized explanations
- Supporting Indian languages
- Producing safe and understandable responses

---

## 2. Core AI Principle

User Question
↓
Understand
↓
Retrieve Real Data
↓
Validate
↓
Reason
↓
Generate
↓
Validate Response
↓
User

The LLM is NOT the weather-data source.

---

## 3. AI Pipeline

Input
↓
Language Detection
↓
Intent Classification
↓
Entity Extraction
↓
Context Resolution
↓
Weather Data Retrieval
↓
Source Validation
↓
Weather Reasoner
↓
Decision Engine
↓
Knowledge Retrieval
↓
LLM Response Generation
↓
Safety / Grounding Validation
↓
Final Response

---

## 4. Language Detection

The system should detect:

- English
- Tamil
- Hindi
- Other supported Indian languages
- Tanglish / mixed-language input

Examples:

"Will it rain tomorrow?"
→ English

"நாளைக்கு மழை வருமா?"
→ Tamil

"Naalaiku rain varuma?"
→ Tanglish

"Kal baarish hogi?"
→ Hindi

The system should preserve the user's preferred language when generating the answer.

---

## 5. Intent Classification

The AI should classify the user's request into a canonical intent.

Initial intents:

- current_weather
- forecast
- rain_forecast
- temperature
- wind
- humidity
- weather_alert
- travel_advisory
- outdoor_decision
- agriculture_advisory
- historical_weather
- climate_trend
- location_weather
- forecast_comparison
- weather_explanation
- general_weather_question

Example:

"Will it rain tomorrow?"

→ intent = rain_forecast

---

## 6. Entity Extraction

The system should extract relevant entities.

Possible entities:

- Location
- Date
- Time
- Weather variable
- Duration
- Persona
- Activity
- Language

Example:

"Tomorrow morning in Coimbatore, will it rain?"

Location = Coimbatore
Date = tomorrow
Time = morning
Variable = rainfall

---

## 7. Context Resolution

WeatherGPT should remember relevant context during a conversation.

Example:

User:

"Will it rain tomorrow?"

System:

"Coimbatore has a moderate chance of rain tomorrow."

User:

"What about 7 AM?"

The system should understand:

Location = Coimbatore
Date = tomorrow
Time = 07:00
Variable = rainfall

The user should not need to repeat the location.

---

## 8. Weather Reasoner

The Weather Reasoner is the core intelligence layer.

It compares available information before generating an answer.

Inputs:

- Current weather
- Forecast
- Official warnings
- Multiple forecast sources
- Historical context
- Data freshness

Outputs:

- hazard
- severity
- source_agreement
- data_freshness
- consistency_level
- recommended_action

---

## 9. Source Agreement

When multiple weather sources are available, WeatherGPT can compare them.

Example:

IMD:
Rain probability = High

Secondary forecast:
Rain probability = High

Result:

Source Agreement = High

If sources disagree:

IMD:
Low rain probability

Secondary source:
High rain probability

Result:

Source Agreement = Low

The system should communicate uncertainty rather than pretend that the prediction is certain.

---

## 10. Consistency Score

WeatherGPT may calculate an application-level Forecast Consistency Score.

Possible factors:

- Agreement between trusted sources
- Data freshness
- Official warning presence
- Availability/completeness of required data

Conceptual model:

Consistency Score =
    Source Agreement
  + Data Freshness
  + Official Warning Signal
  + Data Completeness

IMPORTANT:

This is NOT a scientific probability of rain.

Never display it as:

"85% scientifically accurate"

or

"85% chance of rain"

unless that percentage comes directly from a legitimate meteorological forecast source.

The UI should call it:

- Forecast Consistency
or
- Data Confidence Indicator

---

## 11. Decision Engine

The Decision Engine converts weather conditions into actionable recommendations.

Concept:

Persona
+
Activity
+
Weather
+
Hazard
+
Severity
↓
Recommendation

Example:

Persona = Student
Activity = Travel to college
Rain = Heavy
Official Warning = Active

Recommendation:

"Carry rain protection and avoid unnecessary outdoor travel during the warning period."

Another example:

Persona = Farmer
Hazard = Heavy rainfall

Recommendation:

"Check field drainage and avoid irrigation immediately before the expected rainfall."

Recommendations must remain conservative and must not present the system as an authority beyond the underlying weather data.

---

## 12. Persona System

Initial personas:

- General User
- Student
- Farmer
- Fisherman
- Traveller
- Disaster Response

The persona changes the explanation and recommendation, not the underlying weather facts.

Example:

Same weather:

Heavy Rain

Student:

"Consider postponing unnecessary outdoor travel."

Farmer:

"Check drainage and protect vulnerable crops."

Fisherman:

"Check official marine/weather warnings before departure."

---

## 13. RAG Knowledge Layer

RAG is used for weather-related knowledge and advisory explanations.

Possible knowledge sources:

- Official meteorological guidance
- Weather safety guidelines
- Disaster-management guidance
- Agricultural advisory material
- Weather terminology
- Hazard definitions
- Indian-language weather terminology

RAG should NOT replace live weather data.

Live Weather Data
+
Retrieved Knowledge
↓
LLM

---

## 14. LLM Role

The LLM is responsible for natural-language generation.

It should:

- Explain retrieved information
- Answer questions
- Translate/adapt responses
- Summarize weather conditions
- Generate personalized advisories
- Maintain conversational context

It should NOT:

- Invent weather values
- Invent warnings
- Override official warnings
- Generate unsupported predictions
- Pretend unavailable data exists

---

## 15. Grounding Rules

Every weather answer should be grounded in retrieved data.

Example structured context:

{
  "location": "Coimbatore",
  "temperature": 29,
  "rain_probability": 70,
  "condition": "Rain",
  "official_warning": false,
  "source": "IMD",
  "observed_at": "2026-09-08T10:00:00"
}

The LLM generates language from this context.

---

## 16. Prompt Structure

The production prompt should contain:

SYSTEM RULES

USER QUESTION

USER CONTEXT

LOCATION

CURRENT WEATHER

FORECAST

OFFICIAL WARNINGS

SOURCE INFORMATION

RELEVANT KNOWLEDGE

CONVERSATION CONTEXT

The model should be instructed to:

1. Use only supplied weather data.
2. Clearly identify uncertainty.
3. Prioritize official warnings.
4. Never fabricate missing values.
5. Give concise answers first.
6. Explain reasoning when useful.
7. Match the user's language.
8. Provide actionable advice when requested.

---

## 17. Safety Priority

Weather safety hierarchy:

Official Warning
↓
Verified Weather Data
↓
Source Comparison
↓
Weather Reasoner
↓
AI Explanation

The AI must NEVER downgrade or contradict an active official warning.

Example:

If an official severe-weather warning exists, the response must clearly communicate it.

---

## 18. Missing Data Handling

If required information is unavailable:

DO NOT hallucinate.

Instead:

"I couldn't retrieve the latest forecast for this location. Please try again shortly."

If cached data exists:

"The latest available forecast was retrieved 35 minutes ago."

The timestamp should be visible.

---

## 19. API Failure Handling

Example:

IMD available
Secondary source unavailable

The system can continue using IMD.

If all sources fail:

Live weather unavailable
↓
Check cache
↓
If valid → use cached data + timestamp
↓
Otherwise → return unavailable response

---

## 20. Hallucination Prevention

The system should use:

- Structured weather data
- Tool/API retrieval
- Restricted prompts
- Response validation
- Source attribution
- Missing-data checks
- Numeric consistency checks

Before sending a response, validate:

- Does every weather number exist in retrieved data?
- Does the response mention a warning that actually exists?
- Does the location match the requested location?
- Does the time period match the question?
- Is the language correct?
- Is the recommendation supported by the weather condition?

---

## 21. Response Validator

The Response Validator checks the generated answer.

LLM Output
↓
Extract claims
↓
Compare with retrieved data
↓
Check warning consistency
↓
Check location/time
↓
Safety check
↓
Approved

If validation fails:

Regenerate

or

Return structured fallback response

---

## 22. Example End-to-End Reasoning

User:

"Naalaiku college pogalama?"

Interpretation:

Language = Tanglish
Intent = outdoor_decision
Activity = college travel
Date = tomorrow
Location = user's current/default location
Persona = student

Retrieve:

- Forecast
- Rain probability
- Temperature
- Wind
- Official warnings

Reason:

Heavy rain expected
+
Official warning active

Decision:

Outdoor travel risk = High

Response:

"நாளை கனமழைக்கான வாய்ப்பு உள்ளது, மேலும் அதிகாரப்பூர்வ எச்சரிக்கை இருந்தால் தேவையற்ற வெளிப்பயணத்தைத் தவிர்ப்பது நல்லது. கல்லூரி தொடர்பான அதிகாரப்பூர்வ அறிவிப்பையும் சரிபார்க்கவும்."

The final response must make clear that WeatherGPT does not decide whether the college is closed.

---

## 23. Model Strategy

Initial development should support a replaceable LLM layer.

Architecture:

LLM Interface
│
├── Primary Model
├── Fallback Model
└── Local/Alternative Model

The application should not tightly couple business logic to a single model provider.

---

## 24. Embeddings

Embeddings may be used for:

- Intent matching
- Knowledge retrieval
- Semantic similarity
- Conversation context retrieval

Canonical intents should be represented using example phrases.

Example:

"Will it rain?"
"Is rain expected?"
"மழை வருமா?"
"Naalaiku mazhai ah?"

All can map to:

rain_forecast

---

## 25. Tamil and Tanglish Strategy

Tamil support should not depend only on translation.

The system should understand:

- Tamil
- Tanglish
- English
- Mixed Tamil-English

Examples:

"Naalaiku mazhai varuma?"
"நாளைக்கு மழை வருமா?"
"Tomorrow mazhai varuma?"

These should resolve to the same underlying intent where appropriate.

---

## 26. AI Evaluation

The AI system should be tested using a fixed evaluation set.

Categories:

- Current weather
- Forecast
- Rain questions
- Location questions
- Tamil
- Tanglish
- Voice transcription
- Alerts
- Follow-up questions
- Conflicting sources
- Missing data
- API failures
- Historical analysis
- Persona recommendations

Metrics:

- Intent accuracy
- Location extraction accuracy
- Date/time resolution accuracy
- Grounding accuracy
- Alert consistency
- Language accuracy
- Response latency
- Hallucination rate

---

## 27. AI MVP

MVP capabilities:

- Natural-language weather questions
- Location extraction
- Date/time extraction
- Tamil
- English
- Tanglish
- Forecast retrieval
- Official alert detection
- Basic weather reasoning
- Personalized advisory
- Source/timestamp display
- Follow-up questions

Advanced capabilities:

- More Indian languages
- Advanced climate reasoning
- More personas
- Advanced source disagreement analysis
- Voice conversation
- Long-term personalization

---

## 28. Critical Design Rule

WeatherGPT is NOT an autonomous meteorologist.

It is a:

**Conversational Meteorological Decision Engine**

It retrieves trusted weather information, reasons over that information, and converts it into understandable, location-specific and user-specific guidance.

The underlying meteorological source remains authoritative.

---

## 29. AI Design Status

Status: DRAFT

Before implementation:

- Select initial LLM
- Select embedding model
- Define intent dataset
- Define RAG corpus
- Implement weather reasoner
- Implement decision engine
- Design grounding validator
- Create AI evaluation dataset
- Test Tamil/Tanglish
- Test hallucination/failure cases
































































































































