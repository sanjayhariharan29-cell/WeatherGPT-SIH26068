# SkyZen Phase 31 — Disaster and Government Operations Dashboard

## Executive Summary
Phase 31 introduces an administrative disaster-weather monitoring dashboard using SkyZen's existing verified meteorological pipelines (IMD authoritative warnings, Open-Meteo observational data, and developer-declared alerts). The system strictly segregates administrative capabilities from normal citizen access, prevents LLM reasoning engines from modifying or overriding official disaster warnings, and enforces a zero-tolerance policy against synthetic or fabricated warning geometry.

---

## Key Capabilities Implemented

### 1. Authoritative Warning Lifecycle
- **Scheduled Warnings**: `issued_at > now` (future advisories).
- **Active Warnings**: `issued_at <= now <= expires_at` (current, active alerts requiring immediate civilian or administrative attention).
- **Expired Warnings**: `expires_at < now` (historical records and archive telemetry).

### 2. Strict Safety & Geometry Invariants
- **Authoritative Hierarchy**: Official IMD and civil authority warnings remain immutable. No AI LLM statement can edit, downgrade, or cancel an official warning.
- **Genuine Geometry vs. Text Scoping**:
  - Genuine GeoJSON polygons, multipolygons, and points with valid coordinate structures are visualized directly on the administrative map.
  - When genuine geometry is unavailable, the affected area is displayed strictly as formatted text (e.g., district, state, coordinates).
  - **Zero Fake Warning Polygons**: The system never generates synthetic bounding boxes or fictitious boundary shapes.

### 3. Notification Targeting & Delivery Tracking
- Summarizes FCM and SMS notification delivery metrics per warning:
  - Total users in affected geographic area
  - Total dispatched (`SENT`)
  - Total skipped (`SKIPPED`) with granular reason categorization (`out_of_area`, `notification_disabled`, `already_delivered`, `no_active_tokens`)
  - Delivery failures (`FAILED`) with cause codes
  - Real-time registered device token counts

### 4. RBAC & Security Isolation
- Endpoints are isolated under `/api/v1/operations/disaster/...` and guarded by `require_operations_access` (requiring `admin` or `developer` role).
- Normal citizen accounts (`role="user"`) receive `403 Forbidden`.
- Unauthenticated requests receive `401 Unauthorized`.
- Infrastructure secrets, private service keys, and database passwords are sanitized and redacted from all health and telemetry payloads.

### 5. Multi-Criteria Operations Filtering
- District search (case-insensitive substring)
- Warning type (`heavy_rain`, `thunderstorm`, `cyclone`, `heat_wave`, etc.)
- Warning severity (`low`, `medium`, `high`, `extreme`)
- Lifecycle phase (`active`, `scheduled`, `expired`, `all`)
- Date range (`date_from`, `date_to`)

---

## File Manifest
1. `backend/services/disaster_operations_service.py`: Core operations logic, lifecycle evaluation, geometry validation, targeting aggregation, and provider health.
2. `backend/api/disaster_operations.py`: Administrative REST API router with RBAC guards.
3. `frontend/operations_dashboard.html`: Glassmorphic, dark/light theme responsive dashboard with Leaflet map visualization and text fallbacks.
4. `backend/main.py`: Mounted disaster operations router and guarded web routes.
5. `tests/test_disaster_operations_dashboard.py`: 11 deterministic integration tests covering authorization, lifecycle, filtering, notification metrics, missing geometry fallback, and safety invariance.
