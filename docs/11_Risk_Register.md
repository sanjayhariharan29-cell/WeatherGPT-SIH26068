# WeatherGPT — Risk Register

## 1. Purpose

This document identifies the major technical, data, AI, security,
deployment and demonstration risks associated with WeatherGPT.

Each risk should have:

- Risk description
- Impact
- Likelihood
- Prevention
- Fallback
- Owner

The goal is to identify failure points before implementation and
prepare alternatives so that the project remains functional during
development and judging.

---

## 2. Risk Rating

Likelihood:

- Low
- Medium
- High

Impact:

- Low
- Medium
- High
- Critical

Priority:

- P0 = Critical
- P1 = High
- P2 = Medium
- P3 = Low

---

## 3. Risk — Weather API Failure

### Description

The primary weather-data provider may become unavailable,
slow or return an unexpected response.

### Likelihood

Medium

### Impact

Critical

### Prevention

- Implement API timeout handling.
- Validate API responses.
- Maintain a secondary weather source.
- Cache recent valid data.
- Log provider failures.

### Fallback

Primary source
↓
Secondary source
↓
Valid cache
↓
Unavailable response

The system must never fabricate weather information.

### Priority

P0

---

## 4. Risk — Official Warning Data Unavailable

### Description

An official warning endpoint or warning dataset may be temporarily
unavailable.

### Likelihood

Medium

### Impact

Critical

### Prevention

- Separate warning retrieval from normal weather retrieval.
- Cache active warning information where appropriate.
- Display warning timestamp and validity period.
- Monitor warning API failures.

### Fallback

If warning status cannot be verified, the system must clearly say
that warning information could not be retrieved.

It must NOT claim that there is no warning.

### Priority

P0

---

## 5. Risk — AI Hallucination

### Description

The LLM may generate weather values, warnings or recommendations
that are not supported by retrieved data.

### Likelihood

Medium

### Impact

Critical

### Prevention

- Structured weather context
- Grounded prompts
- Source attribution
- Response validation
- Numeric consistency checks
- Missing-data checks

### Fallback

Return a structured data-based response instead of an unsupported
LLM response.

### Priority

P0

---

## 6. Risk — AI Contradicts Official Warning

### Description

The generated response could incorrectly minimize or contradict
an official warning.

### Likelihood

Low

### Impact

Critical

### Prevention

Use a strict priority hierarchy:

Official Warning
↓
Verified Weather Data
↓
Weather Reasoner
↓
AI Explanation

The LLM must never override official warning information.

### Fallback

If validation detects a contradiction:

- Reject generated response.
- Regenerate.
- If regeneration fails, return a predefined safety response.

### Priority

P0

---

## 7. Risk — Forecast Sources Disagree

### Description

Different weather sources may provide different forecasts.

### Likelihood

High

### Impact

High

### Prevention

- Compare source values.
- Track source timestamps.
- Calculate source agreement.
- Prioritize authoritative warning information.
- Communicate uncertainty.

### Fallback

Tell the user that forecasts differ instead of creating false certainty.

### Priority

P1

---

## 8. Risk — Stale Weather Data

### Description

The application may display outdated weather information.

### Likelihood

Medium

### Impact

High

### Prevention

Every weather record should contain:

- Observation time
- Retrieval time
- Source
- Expiration/freshness information

### Fallback

Clearly display:

"Latest available data was retrieved at..."

Never present stale information as current.

### Priority

P1

---

## 9. Risk — Location Resolution Failure

### Description

The system may incorrectly identify the user's requested location.

### Likelihood

Medium

### Impact

High

### Prevention

- Validate coordinates.
- Use geocoding.
- Ask for clarification when multiple locations match.
- Never silently guess ambiguous locations.

### Fallback

Ask:

"Which location should I check?"

### Priority

P1

---

## 10. Risk — Tamil/Tanglish Understanding Failure

### Description

The AI may incorrectly understand Tamil, Tanglish or
mixed-language questions.

### Likelihood

Medium

### Impact

High

### Prevention

Build a dedicated evaluation dataset containing:

- Tamil
- English
- Tanglish
- Mixed Tamil-English
- Different spellings
- Common conversational phrases

Example:

"Naalaiku mazhai varuma?"

"Naalaiku rain iruka?"

"நாளைக்கு மழை வருமா?"

These should map to the appropriate weather intent.

### Fallback

Ask the user to rephrase or switch language.

### Priority

P1

---

## 11. Risk — Voice Recognition Failure

### Description

Speech-to-text may incorrectly transcribe regional accents,
background noise or Tanglish.

### Likelihood

Medium

### Impact

Medium

### Prevention

- Use noise-tolerant input.
- Display the transcript before processing when appropriate.
- Allow text correction.
- Test Tamil and Tanglish speech.

### Fallback

Allow immediate text input.

### Priority

P2

---

## 12. Risk — LLM/API Cost

### Description

Frequent LLM requests may increase cost or exceed API limits.

### Likelihood

Medium

### Impact

Medium

### Prevention

- Keep prompts concise.
- Avoid unnecessary LLM calls.
- Use deterministic logic for simple weather responses.
- Cache repeated results.
- Apply rate limits.

### Fallback

Use a lower-cost or alternative model.

### Priority

P2

---

## 13. Risk — LLM Latency

### Description

AI generation may be too slow for a live conversational experience.

### Likelihood

Medium

### Impact

Medium

### Prevention

- Retrieve weather data efficiently.
- Keep prompts compact.
- Use fast models for routine responses.
- Cache frequently requested information.

### Fallback

Return structured weather information first and generate
the detailed explanation afterward.

### Priority

P2

---

## 14. Risk — Database Failure

### Description

The database may become unavailable or lose connectivity.

### Likelihood

Low

### Impact

High

### Prevention

- Connection pooling
- Transactions
- Error handling
- Database backups
- Migration control

### Fallback

The core weather query system should be capable of retrieving
live data without depending on historical conversation storage.

### Priority

P1

---

## 15. Risk — Internet Failure During Demo

### Description

The venue may have poor or unstable internet connectivity.

### Likelihood

Medium

### Impact

Critical

### Prevention

Prepare:

- Cached weather data
- Demo datasets
- Local backend
- Preloaded UI
- Screen recording
- Backup demonstration

### Fallback

Switch to deterministic demo mode.

The UI must clearly distinguish demo/simulated data from live data.

### Priority

P0

---

## 16. Risk — External API Format Changes

### Description

A weather provider may change API fields or response formats.

### Likelihood

Low

### Impact

High

### Prevention

Use separate provider adapters.

Weather Provider
↓
Provider Adapter
↓
Normalized Weather Schema

The rest of the system should not directly depend on provider-specific
field names.

### Fallback

Update only the affected adapter.

### Priority

P1

---

## 17. Risk — Incorrect Personalized Advice

### Description

A recommendation may be inappropriate for a user's activity.

### Likelihood

Medium

### Impact

High

### Prevention

- Use conservative recommendation rules.
- Keep weather facts separate from recommendations.
- Use predefined decision rules for high-risk situations.
- Ground recommendations in retrieved data.
- Clearly communicate limitations.

### Fallback

Return general safety guidance and direct users to official
authorities when appropriate.

### Priority

P1

---

## 18. Risk — Overclaiming AI Capabilities

### Description

The project may be presented as if the AI independently predicts
weather.

### Likelihood

Medium

### Impact

High

### Prevention

Clearly communicate:

"WeatherGPT retrieves meteorological information, reasons over
available data, and communicates it conversationally."

It is NOT an independent numerical weather prediction model.

### Priority

P1

---

## 19. Risk — Security Vulnerability

### Description

Authentication, APIs or user data could be exposed.

### Likelihood

Medium

### Impact

High

### Prevention

- HTTPS in production
- Password hashing
- JWT/session security
- Input validation
- Rate limiting
- Secure environment variables
- No API keys in frontend
- No sensitive data in logs

### Priority

P1

---

## 20. Risk — API Keys Exposed

### Description

Weather or LLM provider credentials may accidentally be included
in the APK or frontend code.

### Likelihood

Medium

### Impact

High

### Prevention

All provider credentials must remain on the backend.

Correct:

Mobile App
↓
Backend API
↓
Weather/LLM Providers

Incorrect:

Mobile App
↓
Provider API Key

### Priority

P0

---

## 21. Risk — Scope Creep

### Description

Too many features may prevent completion of the core product.

### Likelihood

High

### Impact

High

### Prevention

Follow strict priority.

P0:

- Weather retrieval
- Conversational queries
- Location handling
- Forecast
- Official warnings
- Weather reasoning
- Basic personalization

P1:

- Tamil/Tanglish
- Voice
- Historical analysis

P2:

- Advanced climate intelligence
- Additional personas
- Advanced analytics

### Rule

A working P0 system is more valuable than ten unfinished features.

### Priority

P0

---

## 22. Risk — Team Dependency

### Description

Development may slow down if one team member becomes a bottleneck.

### Likelihood

Medium

### Impact

High

### Prevention

Use clearly separated responsibilities:

Backend/AI
↓
API Contract
↓
Mobile App

Both developers should work independently against documented
API contracts.

### Fallback

Use mocked API responses so frontend development can continue
without the backend.

### Priority

P1

---

## 23. Risk — Integration Failure

### Description

Frontend, backend, database and AI components may work separately
but fail when integrated.

### Likelihood

Medium

### Impact

High

### Prevention

Integrate early.

Development order:

Backend health endpoint
↓
Weather endpoint
↓
Mobile connection
↓
Chat endpoint
↓
AI pipeline
↓
Alerts
↓
Voice
↓
Historical analysis

Do not wait until the final week for integration.

### Priority

P1

---

## 24. Risk — Poor Demo Reproducibility

### Description

The required weather condition may not occur naturally during
the judging period.

### Likelihood

High

### Impact

High

### Prevention

Prepare deterministic scenarios for:

- Heavy rain
- Official warning
- Normal weather
- Conflicting sources
- API failure

### Fallback

Use clearly labelled simulation/demo mode.

### Priority

P0

---

## 25. Risk — Inaccurate Historical Trend Analysis

### Description

Historical data may be incomplete or incorrectly interpreted.

### Likelihood

Medium

### Impact

Medium

### Prevention

- Record data source.
- Record date range.
- Handle missing values.
- Use clearly defined calculations.
- Distinguish observation from inference.

### Fallback

Display the underlying historical data and explain limitations.

### Priority

P2

---

## 26. Risk — Database Overengineering

### Description

Too many tables or complex infrastructure could slow development.

### Likelihood

Medium

### Impact

Medium

### Prevention

Start with the MVP schema.

Implement advanced storage only when required.

### MVP tables

- Users
- UserPreferences
- Locations
- WeatherRecords
- Forecasts
- Alerts
- Conversations
- Messages

### Priority

P2

---

## 27. Risk — UI Too Complex

### Description

Too much information may make the application confusing.

### Likelihood

Medium

### Impact

Medium

### Prevention

Prioritize:

1. Weather
2. Alert
3. User question
4. Answer
5. Recommendation
6. Source
7. Timestamp

Advanced reasoning information can be expandable.

### Priority

P2

---

## 28. Risk — Response Too Long

### Description

AI may generate unnecessarily long answers.

### Likelihood

High

### Impact

Low

### Prevention

Use a concise response format:

Answer
↓
Reason
↓
Action
↓
Source

Detailed explanation should only appear when requested.

### Priority

P3

---

## 29. Risk — False Sense of Safety

### Description

Users may interpret WeatherGPT's response as a guarantee
that an activity is safe.

### Likelihood

Medium

### Impact

Critical

### Prevention

Use cautious language.

Avoid:

"100% safe."

Prefer:

"Based on the available forecast..."

For severe conditions:

"Follow official authorities' instructions."

### Priority

P0

---

## 30. Risk — Demo Device Failure

### Description

The demonstration phone, laptop or network may fail.

### Likelihood

Medium

### Impact

High

### Prevention

Prepare:

- Primary phone
- Backup phone
- Laptop demo
- Local backend
- Screenshots
- Screen recording
- Demo dataset

### Priority

P1

---

## 31. Risk — APK Build Failure

### Description

The Android application may fail to build or install before
the final demonstration.

### Likelihood

Medium

### Impact

High

### Prevention

- Build APK early.
- Test installation on at least two Android devices.
- Maintain a development build.
- Avoid last-minute dependency changes.

### Fallback

Run the application as a PWA/web application if required.

### Priority

P1

---

## 32. Risk — Requirements Misinterpretation

### Description

The implementation may drift away from the official SIH
problem statement.

### Likelihood

Medium

### Impact

Critical

### Prevention

Every major feature must map to one or more official requirements.

Maintain:

Requirement
↓
Feature
↓
Implementation
↓
Demo Evidence

### Priority

P0

---

## 33. Risk — Existing Solution Overlap

### Description

WeatherGPT may appear too similar to existing weather apps,
chatbots or AI weather projects.

### Likelihood

High

### Impact

Critical

### Prevention

The project should emphasize its specific differentiation:

- Conversational meteorological interaction
- Multilingual/Tanglish understanding
- Source-aware reasoning
- Forecast consistency analysis
- Official warning prioritization
- Persona-aware decision support
- Explainable weather recommendations

Do not claim that conversational weather systems do not already exist.

The differentiation must be demonstrated through implementation
and measurable behavior.

### Priority

P0

---

## 34. Risk — Weak Novelty

### Description

The project may be technically functional but appear to be
"weather API + chatbot."

### Likelihood

High

### Impact

Critical

### Prevention

The core architecture must visibly demonstrate:

Live Data
+
Source Comparison
+
Weather Reasoner
+
Decision Engine
+
Personalization
+
Official Warning Priority
+
Multilingual Interaction

The demo must show the reasoning process and not only the final
chat response.

### Priority

P0

---

## 35. Risk — Unsupported Scientific Claims

### Description

The team may accidentally claim that the system produces
scientifically superior forecasts.

### Likelihood

Medium

### Impact

High

### Prevention

Use precise terminology.

Correct:

"Forecast Consistency"

"Data Confidence Indicator"

"Source Agreement"

Incorrect:

"AI-generated probability"

"Guaranteed prediction"

"Scientifically accurate weather prediction"

unless supported by the underlying meteorological source.

### Priority

P1

---

## 36. Risk — Data Privacy

### Description

Location, conversation or user information could be stored
unnecessarily.

### Likelihood

Medium

### Impact

High

### Prevention

- Store minimum required data.
- Avoid continuous GPS history unless required.
- Do not permanently store voice recordings unless necessary.
- Provide conversation deletion.
- Protect authentication information.

### Priority

P1

---

## 37. Risk — Project Becomes Too Dependent on One AI Model

### Description

A single model provider may fail, change pricing or become
unavailable.

### Likelihood

Medium

### Impact

Medium

### Prevention

Use an abstract LLM interface:

LLM Interface
├── Primary Model
├── Fallback Model
└── Alternative Model

Business logic must remain independent of the model provider.

### Priority

P2

---

## 38. Risk — Failure During Judge Questioning

### Description

Judges may ask whether WeatherGPT is actually predicting
weather or simply querying an API.

### Likelihood

High

### Impact

High

### Prepared Answer

"WeatherGPT does not replace numerical weather prediction models.
Its intelligence is in understanding natural-language questions,
orchestrating meteorological data, checking source consistency,
prioritizing official warnings, and converting that information
into location- and user-specific decisions."

### Priority

P1

---

## 39. Risk — Failure to Explain USP

### Description

The team may demonstrate features without explaining the actual
technical innovation.

### Prevention

The presentation should communicate:

Traditional Weather App
→ Shows weather

WeatherGPT
→ Understands the question
→ Retrieves relevant meteorological data
→ Checks warnings
→ Reasons over sources
→ Adapts to the user
→ Explains the decision

### Priority

P0

---

## 40. Risk Ownership

### Backend / AI

Responsible for:

- Weather APIs
- Data normalization
- Weather Reasoner
- Decision Engine
- LLM
- RAG
- Database
- API security

### Mobile / Frontend

Responsible for:

- APK
- Chat UI
- Weather dashboard
- Alert UI
- Voice interaction
- Location interface
- API integration

### Shared

- Testing
- Demo preparation
- Integration
- Documentation
- Presentation

---

## 41. Emergency Fallback Architecture

### Normal Mode

Mobile App
↓
Backend
↓
Weather APIs
↓
Weather Reasoner
↓
LLM

### Fallback Mode

Mobile App
↓
Backend
↓
Cached/Prepared Weather Data
↓
Rule-Based Reasoner
↓
Structured Response

### Final Demo Mode

Mobile App
↓
Demo Backend
↓
Deterministic Dataset
↓
Predefined Reasoning Scenario
↓
Demo Response

This ensures the project can still be demonstrated even if
external services fail.

---

## 42. Risk Review Schedule

Review risks:

- Before coding
- After database implementation
- After API integration
- After AI integration
- Before APK build
- Before final demo
- Before SIH submission

Any newly discovered failure should be added to this document.

---

## 43. Final Risk Priorities

The five most important risks are:

1. Official warning/data failure
2. AI hallucination or contradiction
3. Existing-solution overlap / weak novelty
4. Internet/API failure during judging
5. Scope creep

These risks must receive the highest attention.

---

## 44. Final Rule

WeatherGPT must always follow:

**Never invent.**
**Never hide uncertainty.**
**Never contradict official warnings.**
**Never expose private/API credentials.**
**Never present simulated data as live data.**
**Never overclaim what the AI can do.**

---

## 45. Risk Register Status

Status: DRAFT

Before implementation:

- Assign risk owners.
- Validate API fallback.
- Implement caching.
- Implement AI grounding validation.
- Prepare demo datasets.
- Test offline/failure scenarios.
- Build APK early.
- Test on multiple devices.
- Conduct integration testing.
- Review novelty/differentiation again before final submission.