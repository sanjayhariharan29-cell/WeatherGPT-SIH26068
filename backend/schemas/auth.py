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
    email: str
    language: str = "ta"
    persona: str = "student"
    role: str = "user"
    is_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Token response payload."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserResponse


class UserUpdateRequest(BaseModel):
    """Payload for updating user profile."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    language: Optional[str] = Field(None, max_length=10)
    persona: Optional[str] = Field(None, max_length=50)


class UserPreferenceSchema(BaseModel):
    """User preferences response and update schema."""
    preferred_units: str = Field(default="metric", max_length=20)
    persona: str = Field(default="student", max_length=50)
    notification_enabled: bool = Field(default=True)

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
