# WeatherGPT — User Flows

## 1. Core User Flow

User
  ↓
Open WeatherGPT App
  ↓
Select / Detect Location
  ↓
Enter Text or Voice Query
  ↓
Language Detection
  ↓
Intent + Entity Extraction
  ↓
Retrieve Relevant Weather Data
  ↓
Check Official Warnings
  ↓
Weather Reasoner
  ↓
Decision / Advisory Engine
  ↓
LLM Response Generation
  ↓
Answer + Source/Freshness + Risk Information
  ↓
User

---

# 2. Flow — Basic Weather Query

Example:

"What's the weather tomorrow?"

### Process

1. Receive user query
2. Detect intent = forecast
3. Determine location
4. Determine date = tomorrow
5. Retrieve forecast
6. Check active warnings
7. Process weather information
8. Generate simple response
9. Display result

### Example Output

"Tomorrow in Coimbatore, rain is possible during the
morning. The latest forecast was updated at 06:00 AM."

---

# 3. Flow — Tamil Query

Example:

"நாளைக்கு கோயம்புத்தூர்ல மழை வருமா?"

### NLP Output

Language = Tamil

Intent = Rain Forecast

Location = Coimbatore

Date = Tomorrow

Weather Variable = Rain

↓

Retrieve forecast

↓

Generate response

↓

Return Tamil answer

---

# 4. Flow — Tanglish Query

Example:

"Naalaiku Coimbatore la mazhai varuma?"

The system should interpret Tanglish naturally.

Expected structured output:

Intent = Rain Forecast

Location = Coimbatore

Date = Tomorrow

Variable = Rain

The system should NOT require the user to use formal English.

---

# 5. Flow — Voice Query

User speaks:

"Naalaiku morning college pogalama?"

↓

Speech-to-Text

↓

Language detection

↓

NLP

↓

Intent = Travel Advisory

Location = User Location

Date = Tomorrow

Time = Morning

User Persona = Student

↓

Weather retrieval

↓

Warning check

↓

Reasoning

↓

Personalized advisory

↓

Text + Voice response

---

# 6. Flow — Extreme Weather Warning

Example:

User asks:

"Is there any cyclone warning for Nagapattinam?"

↓

Intent = Active Warning

↓

Location = Nagapattinam

↓

Retrieve official warning

↓

Check warning severity

↓

Display official warning FIRST

↓

Generate explanation

↓

Provide safety-oriented advisory

IMPORTANT:

AI must never weaken, contradict or replace
an official warning.

---

# 7. Flow — "Should I Go Outside?"

Example:

"Can I travel to college tomorrow morning?"

The system should NOT simply answer YES/NO.

It should evaluate:

- Rain
- Wind
- Temperature
- Lightning
- Active warnings
- Forecast consistency
- Time
- Location
- User persona

Then produce:

Risk level
+
Reason
+
Actionable recommendation

---

# 8. Flow — Forecast Change

Example:

"Yesterday it said no rain. Why is it raining now?"

↓

Identify intent = Forecast Change

↓

Retrieve:

- Previous forecast
- Current forecast
- Current observation
- Forecast update times

↓

Compare information

↓

Explain possible change

Example:

"The latest forecast was updated at 06:00 AM.
The current forecast has increased the rain probability
because the latest weather data differs from the previous
forecast."

The system must avoid inventing a meteorological reason
when the required data is unavailable.

---

# 9. Flow — Persona-Based Advisory

User profile:

Student

Query:

"Weather tomorrow morning?"

↓

Weather data

↓

Hazard detection

↓

Persona = Student

↓

Decision Engine

↓

Student-specific advisory

---

## Possible Personas

### Student

Focus:
- Travel
- Rain
- Heat
- Lightning
- School/college commute

### Farmer

Focus:
- Rain
- Temperature
- Wind
- Crop-related weather conditions

### Fisherman

Focus:
- Wind
- Marine warnings
- Cyclone
- Wave/severe-weather information

### Traveller

Focus:
- Travel conditions
- Rain
- Visibility
- Severe weather

### Disaster Response

Focus:
- Active warnings
- Hazard severity
- Location
- Time
- Emergency information

---

# 10. Flow — Historical Weather Query

Example:

"How much rain did Coimbatore receive last year?"

↓

Intent = Historical Weather

↓

Extract:

Location = Coimbatore

Time Range = Previous Year

Variable = Rainfall

↓

Retrieve historical data

↓

Calculate / summarize

↓

Return result

---

# 11. Flow — Climate Trend Query

Example:

"Has Coimbatore become hotter over the last 10 years?"

↓

Intent = Climate Trend

↓

Retrieve historical temperature data

↓

Calculate trend

↓

Generate explanation

↓

Show:

- Historical values
- Trend
- Time period
- Data source

The system must clearly distinguish
historical analysis from weather forecasting.

---

# 12. Flow — Location Handling

Possible inputs:

### Automatic

GPS → Current Location

### Manual

User searches:

"Nagapattinam"

### Conversational

"How is the weather there?"

The system should maintain conversational context
when the referenced location is known.

---

# 13. Flow — Follow-Up Question

User:

"Will it rain tomorrow?"

WeatherGPT:

"Rain is possible..."

User:

"What about 7 AM?"

↓

System remembers:

Location
+
Date
+
Weather variable

↓

Updates only:

Time = 7 AM

↓

Returns specific answer.

---

# 14. Flow — Conflicting Weather Sources

If different sources disagree:

Source A → Rain likely

Source B → Low rain probability

↓

Weather Reasoner detects disagreement

↓

Do NOT hide the disagreement.

Return:

"Forecast sources currently disagree.
The latest available information indicates..."

↓

Show consistency indicator.

---

# 15. Flow — Stale Data

If weather data is old:

↓

Detect timestamp

↓

Mark data as stale

↓

Do NOT present it as live information.

Example:

"The latest available weather data is from 3 hours ago."

---

# 16. Flow — API Failure

Live API unavailable:

↓

Try backup source

↓

If backup unavailable:

Use cached verified information

↓

Clearly show timestamp

↓

Do NOT fabricate a new forecast.

---

# 17. Flow — No Location

User:

"Will it rain tomorrow?"

If location is unknown:

Ask:

"Which location should I check?"

OR use the user's permitted current location.

---

# 18. Core Safety Flow

Every weather response:

Weather Data
     ↓
Validation
     ↓
Official Warning Check
     ↓
Reasoning
     ↓
LLM
     ↓
Response

Never:

User
 ↓
LLM
 ↓
Invented weather information

---

# 19. MVP User Journey

The first complete demo should prove:

Voice/Text
    ↓
Tamil/Tanglish Query
    ↓
NLP
    ↓
Location + Time + Intent
    ↓
Weather Data
    ↓
Official Warning
    ↓
Weather Reasoner
    ↓
Decision Engine
    ↓
LLM
    ↓
Tamil/English Answer
    ↓
Mobile App

This is the primary end-to-end flow.

---

# 20. Hero Demo Scenario

Location:

Nagapattinam

Persona:

Fisherman

Input:

Voice query in Tamil

Example:

"நாளைக்கு கடலுக்கு போகலாமா?"

System:

1. Converts voice to text
2. Detects Tamil
3. Understands intent
4. Identifies location
5. Retrieves marine/weather information
6. Checks official warning
7. Evaluates risk
8. Shows warning if active
9. Generates simple Tamil explanation
10. Provides actionable guidance

This should be our primary disaster-management demonstration.

---

# 21. Secondary Demo Scenario

Location:

Coimbatore

Persona:

Student

Input:

"Naalaiku morning college pogalama?"

System:

Voice/Text
→ NLP
→ Forecast
→ Rain/Wind/Lightning check
→ Warning check
→ Student persona
→ Risk reasoning
→ Actionable answer

---

# 22. User Flow Status

Status: DRAFT

Next:

1. Validate flows against SIH requirements
2. Finalize personas
3. Finalize hero scenario
4. Design screens
5. Define API contracts
6. Begin implementation