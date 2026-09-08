# WeatherGPT — API Contracts

## 1. Purpose

This document defines communication between the WeatherGPT mobile
application, backend, AI services and weather-data services.

The API contract allows frontend and backend development to happen
in parallel.

---

# 2. Base API

Development:

http://localhost:8000/api/v1

Production:

To be finalized after deployment selection.

All API responses should use JSON unless explicitly specified.

---

# 3. Authentication

## POST /auth/register

Creates a new user.

### Request

{
  "name": "Sanjay",
  "email": "user@example.com",
  "password": "********"
}

### Response

{
  "user_id": "123",
  "message": "Registration successful"
}

---

## POST /auth/login

Authenticates a user.

### Request

{
  "email": "user@example.com",
  "password": "********"
}

### Response

{
  "access_token": "TOKEN",
  "user": {
    "id": "123",
    "name": "Sanjay",
    "language": "ta",
    "persona": "student"
  }
}

Passwords must never be returned.

---

# 4. Weather API

## GET /weather/current

Returns current weather for a location.

### Parameters

lat
lon

### Example

GET /weather/current?lat=11.0168&lon=76.9558

### Response

{
  "location": {
    "name": "Coimbatore",
    "latitude": 11.0168,
    "longitude": 76.9558
  },
  "weather": {
    "temperature": 29,
    "humidity": 72,
    "rain_probability": 65,
    "wind_speed": 18,
    "condition": "Rain"
  },
  "source": "IMD",
  "observed_at": "2026-09-08T10:00:00",
  "retrieved_at": "2026-09-08T10:10:00"
}

---

# 5. Forecast API

## GET /weather/forecast

Returns forecast information.

### Parameters

lat
lon
date
hours (optional)

### Example

GET /weather/forecast?lat=11.0168&lon=76.9558&date=tomorrow

### Response

{
  "location": "Coimbatore",
  "forecast": [
    {
      "time": "07:00",
      "temperature": 27,
      "rain_probability": 70,
      "wind_speed": 14,
      "condition": "Rain"
    }
  ],
  "source": "IMD",
  "retrieved_at": "2026-09-08T10:10:00"
}

---

# 6. Alert API

## GET /weather/alerts

Returns active weather alerts.

### Parameters

lat
lon

### Response

{
  "location": "Nagapattinam",
  "alerts": [
    {
      "type": "heavy_rain",
      "severity": "high",
      "title": "Heavy Rain Warning",
      "description": "Official warning information",
      "source": "IMD",
      "issued_at": "2026-09-08T08:00:00",
      "expires_at": "2026-09-08T20:00:00"
    }
  ]
}

---

# 7. AI Chat API

## POST /chat

Main WeatherGPT endpoint.

### Request

{
  "message": "Naalaiku morning Coimbatore la mazhai varuma?",
  "language": "ta",
  "location": {
    "latitude": 11.0168,
    "longitude": 76.9558,
    "name": "Coimbatore"
  },
  "persona": "student",
  "conversation_id": "abc123"
}

### Backend Processing

Request
  ↓
Language Detection
  ↓
Intent Detection
  ↓
Entity Extraction
  ↓
Location/Time Resolution
  ↓
Weather Data Retrieval
  ↓
Warning Check
  ↓
Weather Reasoner
  ↓
Decision Engine
  ↓
RAG
  ↓
LLM
  ↓
Response Validation
  ↓
Final Response

### Response

{
  "conversation_id": "abc123",
  "answer": "நாளை காலை மழைக்கான வாய்ப்பு அதிகமாக உள்ளது...",
  "language": "ta",
  "intent": "rain_forecast",
  "location": "Coimbatore",
  "risk": {
    "level": "medium",
    "consistency": "high"
  },
  "source": "IMD",
  "data_timestamp": "2026-09-08T10:00:00"
}

---

# 8. Voice API

## POST /voice/query

Accepts user voice input.

### Request

Multipart/form-data

audio file
language (optional)
location (optional)

### Processing

Audio
 ↓
Speech-to-Text
 ↓
NLP
 ↓
WeatherGPT Engine
 ↓
Response
 ↓
Text-to-Speech

### Response

{
  "transcript": "Naalaiku morning mazhai varuma?",
  "answer": "நாளை காலை மழைக்கான வாய்ப்பு உள்ளது.",
  "language": "ta",
  "audio_url": "temporary_audio_reference"
}

Audio storage should be temporary unless there is a
specific reason to retain it.

---

# 9. Historical Weather API

## GET /weather/history

Returns historical weather information.

### Parameters

lat
lon
start_date
end_date
metric

### Example

GET /weather/history?lat=11.0168&lon=76.9558&start_date=2020-01-01&end_date=2025-01-01&metric=rainfall

### Response

{
  "location": "Coimbatore",
  "metric": "rainfall",
  "period": {
    "start": "2020-01-01",
    "end": "2025-01-01"
  },
  "data": []
}

---

# 10. Climate Trend API

## GET /weather/trends

Provides historical trend analysis.

### Parameters

lat
lon
start_year
end_year
metric

### Response

{
  "location": "Coimbatore",
  "metric": "temperature",
  "period": "2015-2025",
  "trend": "increasing",
  "analysis": "..."
}

The backend must distinguish historical analysis from
weather forecasting.

---

# 11. User Profile API

## GET /users/me

Returns current user information.

---

## PUT /users/me

Updates user preferences.

### Request

{
  "language": "ta",
  "persona": "student",
  "notification_enabled": true
}

---

# 12. Location API

## GET /locations/search

Searches for a location.

### Example

GET /locations/search?q=Coimbatore

### Response

{
  "results": [
    {
      "name": "Coimbatore",
      "district": "Coimbatore",
      "state": "Tamil Nadu",
      "latitude": 11.0168,
      "longitude": 76.9558
    }
  ]
}

---

# 13. Conversation API

## GET /conversations

Returns user's conversations.

---

## GET /conversations/{id}

Returns messages in a conversation.

---

## DELETE /conversations/{id}

Deletes a conversation.

---

# 14. Notification API

## GET /notifications

Returns user notifications.

---

## POST /notifications/{id}/read

Marks a notification as read.

---

# 15. Health Check

## GET /health

### Response

{
  "status": "ok",
  "version": "0.1.0"
}

Used for deployment and monitoring.

---

# 16. Standard Error Response

All APIs should return a consistent error structure.

Example:

{
  "error": {
    "code": "WEATHER_DATA_UNAVAILABLE",
    "message": "Current weather information is temporarily unavailable."
  }
}

Possible error codes:

- INVALID_REQUEST
- INVALID_LOCATION
- WEATHER_DATA_UNAVAILABLE
- IMD_UNAVAILABLE
- LLM_UNAVAILABLE
- VOICE_PROCESSING_FAILED
- DATABASE_ERROR
- UNAUTHORIZED
- RATE_LIMITED

---

# 17. Response Metadata

Weather-related responses should expose:

- Source
- Data timestamp
- Retrieval timestamp
- Location
- Warning status

This improves transparency and debugging.

---

# 18. API Security

Rules:

- API keys remain on backend
- Never expose provider API keys to the mobile app
- Validate all user inputs
- Authenticate protected endpoints
- Apply rate limiting
- Use HTTPS in production
- Never log passwords or sensitive tokens

---

# 19. Frontend / Backend Contract

The frontend team should build against these JSON structures.

The backend team should maintain compatibility with these
contracts.

If a contract must change:

1. Update this document
2. Notify the other developer
3. Update frontend/backend together
4. Test the integration

---

# 20. MVP API Priority

### P0

- POST /auth/register
- POST /auth/login
- GET /weather/current
- GET /weather/forecast
- GET /weather/alerts
- POST /chat
- GET /health

### P1

- POST /voice/query
- GET /weather/history
- GET /locations/search
- GET /conversations
- GET /conversations/{id}
- GET /users/me
- PUT /users/me

### P2

- GET /weather/trends
- Notifications
- Advanced analytics
- Additional APIs

---

# 21. API Status

Status: DRAFT

Before implementation:

- Validate actual IMD API responses
- Validate weather-provider responses
- Finalize authentication strategy
- Finalize exact JSON fields
- Test API failure cases
- Create OpenAPI documentation