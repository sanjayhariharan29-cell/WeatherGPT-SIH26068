from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, ConfigDict
import re

class RegisterRequest(BaseModel):
    """Payload for user registration."""
    name: str = Field(default="", min_length=0, max_length=100, description="User full name")
    full_name: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, max_length=100, description="Plaintext password")
    confirm_password: Optional[str] = Field(default=None, max_length=100)
    persona: str = Field(default="student", max_length=50)
    language: str = Field(default="ta", max_length=10)
    role: str = Field(default="user", max_length=20)
    admin_secret: Optional[str] = Field(default=None, max_length=255, description="Secret required for admin registration")

    @model_validator(mode="before")
    @classmethod
    def handle_full_name_and_confirm(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map full_name to name if name is missing or empty
            if not data.get("name") and data.get("full_name"):
                data["name"] = data["full_name"]
            # Validate confirm_password if present
            if "confirm_password" in data and data["confirm_password"] is not None:
                if data.get("password") != data.get("confirm_password"):
                    raise ValueError("Passwords do not match")
        return data

    @field_validator("name")
    def name_must_not_be_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Name cannot be empty or whitespace only")
        return s

    @field_validator("password")
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v

    @field_validator("role")
    def validate_role(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean not in ["user", "admin"]:
            raise ValueError("Role must be 'user' or 'admin'")
        return v_clean


class LoginRequest(BaseModel):
    """Payload for user login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class VerifyEmailRequest(BaseModel):
    """Payload for email verification."""
    token: str = Field(..., min_length=1, max_length=255, description="Verification token")


class ResendVerificationRequest(BaseModel):
    """Payload to request a new email verification code."""
    email: EmailStr = Field(..., description="User email address")


class ForgotPasswordRequest(BaseModel):
    """Payload for requesting a password reset link/token."""
    email: EmailStr = Field(..., description="User email address")


class VerifyResetTokenRequest(BaseModel):
    """Payload for verifying a password reset token."""
    token: str = Field(..., min_length=1, max_length=255, description="Password reset token")


class ResetPasswordRequest(BaseModel):
    """Payload for resetting password with a token."""
    token: str = Field(..., min_length=1, max_length=255, description="Password reset token")
    new_password: str = Field(..., min_length=6, max_length=100, description="New plaintext password")
    confirm_password: Optional[str] = Field(default=None, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def validate_matching_passwords(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "confirm_password" in data and data["confirm_password"] is not None:
                if data.get("new_password") != data.get("confirm_password"):
                    raise ValueError("Passwords do not match")
        return data

    @field_validator("new_password")
    def validate_new_password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("New password must be at least 6 characters long")
        return v


class UserResponse(BaseModel):
    """User profile response object."""
    id: str
    name: str
    full_name: Optional[str] = None
    email: str
    language: str = "ta"
    preferred_language: Optional[str] = None
    persona: str = "student"
    role: str = "user"
    is_verified: bool = False
    onboarding_completed: bool = False

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Token response payload."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserResponse


class ProfileResponse(BaseModel):
    """Full authenticated profile response model."""
    id: str
    name: str
    full_name: str
    email: str
    role: str = "user"
    persona: str = "student"
    language: str = "ta"
    preferred_language: str = "ta"
    is_verified: bool = False
    onboarding_completed: bool = False
    notification_enabled: bool = True
    last_known_location: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_location_source: Optional[str] = None
    last_location_updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdateRequest(BaseModel):
    """Payload for updating user profile and completing onboarding."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="User full name")
    full_name: Optional[str] = Field(None, min_length=1, max_length=100, description="User full name alias")
    persona: Optional[str] = Field(None, max_length=50, description="User persona/role")
    role: Optional[str] = Field(None, max_length=50, description="User persona/role alias")
    language: Optional[str] = Field(None, max_length=20, description="Preferred language code")
    preferred_language: Optional[str] = Field(None, max_length=20, description="Preferred language alias")
    notification_enabled: Optional[bool] = Field(None, description="Basic notification alert preference")
    onboarding_completed: Optional[bool] = Field(None, description="Onboarding completion flag")
    last_known_location: Optional[str] = Field(None, max_length=100, description="Last known location name")
    last_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Last known latitude")
    last_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Last known longitude")
    last_location_source: Optional[str] = Field(None, max_length=50, description="Location source")
    last_location_updated_at: Optional[str] = Field(None, description="ISO timestamp of last known location")

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map full_name to name
            if not data.get("name") and data.get("full_name"):
                data["name"] = data["full_name"]
            # Map role to persona if role is a recognized persona string
            if not data.get("persona") and data.get("role"):
                data["persona"] = data["role"]
            # Map preferred_language to language
            if not data.get("language") and data.get("preferred_language"):
                data["language"] = data["preferred_language"]
        return data

    @field_validator("name")
    def validate_name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Name cannot be blank")
            return s
        return v

    @field_validator("persona")
    def normalize_persona(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.strip().lower()
        persona_map = {
            "student": "student",
            "commuter": "commuter",
            "farmer": "farmer",
            "fisherman": "fisherman",
            "disaster": "disaster_response",
            "emergency": "disaster_response",
            "disaster / emergency": "disaster_response",
            "disaster_response": "disaster_response",
            "disaster response": "disaster_response",
            "general": "general",
            "general user": "general",
            "traveller": "traveller",
            "traveler": "traveller"
        }
        if cleaned not in persona_map:
            raise ValueError(f"Unsupported persona/role '{v}'. Supported: Student, Commuter, Farmer, Fisherman, Disaster / Emergency, General")
        return persona_map[cleaned]

    @field_validator("language")
    def normalize_language(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.strip().lower()
        lang_map = {
            "en": "en",
            "english": "en",
            "ta": "ta",
            "tamil": "ta",
            "hi": "hi",
            "hindi": "hi"
        }
        if cleaned not in lang_map:
            raise ValueError(f"Unsupported language '{v}'. Supported: English (en), Tamil (ta), Hindi (hi)")
        return lang_map[cleaned]


class UserUpdateRequest(BaseModel):
    """Payload for updating user profile."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    language: Optional[str] = Field(None, max_length=20)
    preferred_language: Optional[str] = Field(None, max_length=20)
    persona: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=50)
    onboarding_completed: Optional[bool] = None
    notification_enabled: Optional[bool] = None
    last_known_location: Optional[str] = Field(None, max_length=100)
    last_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    last_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    last_location_source: Optional[str] = Field(None, max_length=50)
    last_location_updated_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("name") and data.get("full_name"):
                data["name"] = data["full_name"]
            if not data.get("persona") and data.get("role"):
                data["persona"] = data["role"]
            if not data.get("language") and data.get("preferred_language"):
                data["language"] = data["preferred_language"]
        return data


class UserPreferenceSchema(BaseModel):
    """User preferences response and update schema."""
    preferred_units: str = Field(default="metric", max_length=20)
    persona: str = Field(default="student", max_length=50)
    notification_enabled: bool = Field(default=True)
    last_known_location: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_location_source: Optional[str] = "manual"
    last_location_updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SavedLocationCreate(BaseModel):
    """Schema for saving a new user location."""
    name: str = Field(..., min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class SavedLocationResponse(BaseModel):
    """Response schema for a saved location."""
    id: str
    user_id: str
    name: str
    latitude: float
    longitude: float

    model_config = ConfigDict(from_attributes=True)
