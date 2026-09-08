# WeatherGPT — Database Design

## 1. Purpose

The database stores the persistent information required by WeatherGPT.

It should support:

- User accounts
- User preferences
- Locations
- Weather records
- Forecasts
- Official alerts
- Conversations
- Messages
- Generated advisories
- System/audit events

The database must be simple enough for the hackathon while allowing
future expansion.

---

# 2. Database Choice

Initial database:

**PostgreSQL**

Reason:

- Reliable relational database
- Good FastAPI support
- Suitable for structured weather/application data
- Easy to deploy
- Supports future scaling

For local development, SQLite may be used temporarily if required.

The application should use SQLAlchemy so the database can be changed
without rewriting the application logic.

---

# 3. High-Level Relationship

```text
Users
  │
  ├── UserPreferences
  │
  ├── Locations
  │
  └── Conversations
          │
          └── Messages
                  │
                  └── Advisories

Locations
  │
  ├── WeatherRecords
  ├── Forecasts
  └── Alerts

SystemEvents