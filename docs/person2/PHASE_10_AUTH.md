# Phase 10 — Authentication & Authorization (Person 2)

## Overview

Phase 10 delivers a production-grade, secure authentication and authorization architecture for the WeatherGPT backend (Person 2). It secures user access, enforces password hashing, provides JWT session management with token revocation/logout, implements role-based access control (RBAC), and guarantees strict user resource ownership across profile data, user preferences, chat conversations, and saved locations.

---

## Key Components Implemented

### 1. Password Security (`backend/core/security.py`)
- **Bcrypt Hashing**: Passwords are saved exclusively as salted bcrypt hashes (`$2b$`). Raw passwords are never stored, logged, or included in API responses.
- **Verification Engine**: `verify_password` validates plain passwords against bcrypt hashes securely.

### 2. JWT Session & Token Revocation (`backend/core/security.py`)
- **JWT Standard**: Tokens are signed using PyJWT (`HS256`) with configurable secret keys and expiration time (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Unique JTI Tracking**: Every token incorporates a unique JTI (`jti`) and issued-at/expiration timestamps.
- **Token Revocation / Logout**: Calling `POST /api/v1/auth/logout` invalidates token JTIs in both an in-memory thread-safe revocation set and persistent database records (`RevokedToken`). Subsequent requests with revoked tokens are immediately rejected (401 Unauthorized).

### 3. Role-Based Access Control (RBAC) (`backend/core/security.py` & `backend/db/models.py`)
- **Roles Support**: User schema & model include `role` field (`user` vs `admin`).
- **Permission Check Dependency**: `require_role(required_role)` FastAPI dependency enforces access limits (e.g., `/auth/admin/users` requires `admin` role; returns 403 Forbidden for standard `user` accounts).

### 4. Strict User Ownership Enforcement (`backend/api/users.py`, `backend/api/chat.py`, `backend/api/locations.py`)
- **Profile & Preferences**: `/users/me` and `/users/preferences` operate directly on `current_user.id` resolved from verified JWT claims. Users cannot tamper with query IDs to view or alter another user's profile.
- **Conversation Ownership**: `GET /chat/conversations/{id}` and `DELETE /chat/conversations/{id}` verify `conversation.user_id == current_user.id`. User A attempting to inspect or modify User B's conversation receives 403 Forbidden.
- **Saved Locations Ownership**: `POST /locations/saved`, `GET /locations/saved`, `DELETE /locations/saved/{id}` enforce per-user isolation.

### 5. Input Validation & Error Sanitization (`backend/schemas/auth.py` & `backend/middleware/error_handler.py`)
- **Pydantic Validation**: Strict Pydantic models (`RegisterRequest`, `LoginRequest`, `SavedLocationCreate`) enforce name non-emptiness, password minimum length (6+ chars), email validation, and geographic boundary checks.
- **Sanitized Responses**: Login failures use generic messages ("Invalid email or password") to prevent email/account enumeration. Stack traces, secret keys, and passwords are never exposed.

---

## API Summary

| Method | Endpoint | Protection | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Public | Registers a new user with bcrypt password hashing and default preferences |
| `POST` | `/api/v1/auth/login` | Public | Authenticates credentials and issues signed JWT bearer token |
| `POST` | `/api/v1/auth/logout` | Bearer Auth | Revokes active session token (adds JTI to revocation list) |
| `GET` | `/api/v1/auth/me` | Bearer Auth | Returns current authenticated user profile |
| `GET` | `/api/v1/auth/admin/users` | Admin Role | Lists all registered users (admin privilege required) |
| `GET` | `/api/v1/users/me` | Optional/Bearer | Gets current user profile |
| `PUT` | `/api/v1/users/me` | Bearer Auth | Updates authenticated user's name, language, persona |
| `GET` | `/api/v1/users/preferences` | Bearer Auth | Gets user preferences |
| `PUT` | `/api/v1/users/preferences` | Bearer Auth | Updates user preferences |
| `POST` | `/api/v1/locations/saved` | Bearer Auth | Saves a preferred location for the authenticated user |
| `GET` | `/api/v1/locations/saved` | Bearer Auth | Lists saved locations owned by authenticated user |
| `DELETE` | `/api/v1/locations/saved/{id}`| Bearer Auth | Deletes saved location with ownership check |
| `GET` | `/api/v1/chat/conversations` | Bearer Auth | Lists user's owned conversation history |
| `GET` | `/api/v1/chat/conversations/{id}`| Bearer Auth | Gets conversation detail (user ownership check) |
| `DELETE`| `/api/v1/chat/conversations/{id}`| Bearer Auth | Deletes conversation (user ownership check) |

---

## Verification & Test Suite

The test suite in `tests/test_auth_engine.py` validates all 15 required security scenarios:

1. **Valid Registration**: User created in DB with default preferences.
2. **Duplicate Registration**: Email collision rejected with 400.
3. **Valid Login**: Returns JWT access token and user payload.
4. **Invalid Password**: Rejected with generic 401 detail.
5. **Invalid Account**: Non-existent account returns generic 401 detail.
6. **Protected Endpoint Without Auth**: Request without Bearer token returns 401.
7. **Valid Authenticated Request**: Accessing `/auth/me` with Bearer token returns 200.
8. **Expired Token**: Token with expired `exp` claim returns 401.
9. **Invalid Token**: Corrupted JWT token returns 401.
10. **User Ownership**: User A receives 403 Forbidden attempting to access User B's conversation/profile.
11. **Unauthorized User**: Non-admin accessing admin route receives 403 Forbidden; admin receives 200.
12. **Logout / Revocation**: Logging out revokes token; subsequent request returns 401 Token revoked.
13. **Malformed Credentials**: Invalid email format, short password, or invalid role rejected.
14. **Password Plaintext Prevention**: Verified `password_hash` in DB starts with `$2b$` and never equals raw password.
15. **Secret Leakage Prevention**: Verified error outputs contain zero tracebacks, passwords, or secret keys.

### Test Results

Full test suite execution (`python -m pytest -v`):
- **Passed**: 372
- **Failed**: 0
- **Time**: 27.65s
