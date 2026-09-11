import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, validates
from backend.db.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def validate_latitude(lat: float) -> float:
    if lat is not None and not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Latitude must be between -90 and +90 degrees. Got {lat}")
    return lat

def validate_longitude(lon: float) -> float:
    if lon is not None and not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Longitude must be between -180 and +180 degrees. Got {lon}")
    return lon


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    language = Column(String(10), default="ta")
    persona = Column(String(50), default="student")
    role = Column(String(20), default="user", nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String(255), nullable=True)
    verification_token_expires = Column(DateTime(timezone=True), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    @property
    def full_name(self) -> str:
        return self.name

    @full_name.setter
    def full_name(self, value: str) -> None:
        self.name = value

    @property
    def preferred_language(self) -> str:
        return self.language

    @preferred_language.setter
    def preferred_language(self, value: str) -> None:
        self.language = value

    preferences = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    saved_locations = relationship("SavedLocation", back_populates="user", cascade="all, delete-orphan")
    device_tokens = relationship("DeviceToken", back_populates="user", cascade="all, delete-orphan")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    jti = Column(String(255), unique=True, index=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), default=utc_now)


class SavedLocation(Base):
    __tablename__ = "saved_locations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    user = relationship("User", back_populates="saved_locations")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    preferred_units = Column(String(20), default="metric")
    persona = Column(String(50), default="student")
    notification_enabled = Column(Boolean, default=True)
    last_known_location = Column(String(100), nullable=True)
    last_latitude = Column(Float, nullable=True)
    last_longitude = Column(Float, nullable=True)
    last_location_source = Column(String(50), default="manual")
    last_location_updated_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="preferences")


class Location(Base):
    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), index=True, nullable=False)
    district = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    @validates("latitude")
    def val_lat(self, key, value):
        return validate_latitude(value)

    @validates("longitude")
    def val_lon(self, key, value):
        return validate_longitude(value)


class WeatherRecord(Base):
    __tablename__ = "weather_records"
    __table_args__ = (
        Index("idx_weather_loc_observed", "location_name", "observed_at"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    location_name = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    rain_probability = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    condition = Column(String(100), nullable=False)
    source = Column(String(50), default="IMD", index=True)
    observed_at = Column(DateTime(timezone=True), default=utc_now)
    retrieved_at = Column(DateTime(timezone=True), default=utc_now)

    @validates("latitude")
    def val_lat(self, key, value):
        return validate_latitude(value)

    @validates("longitude")
    def val_lon(self, key, value):
        return validate_longitude(value)


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        Index("idx_forecast_loc_time", "location_name", "forecast_time"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    location_name = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    forecast_time = Column(DateTime(timezone=True), nullable=False)
    temperature = Column(Float, nullable=False)
    rain_probability = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    condition = Column(String(100), nullable=False)
    source = Column(String(50), default="IMD", index=True)
    retrieved_at = Column(DateTime(timezone=True), default=utc_now)

    @validates("latitude")
    def val_lat(self, key, value):
        return validate_latitude(value)

    @validates("longitude")
    def val_lon(self, key, value):
        return validate_longitude(value)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alert_loc_expires", "location_name", "expires_at"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    location_name = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    source = Column(String(50), default="IMD")
    issued_at = Column(DateTime(timezone=True), default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    @validates("latitude")
    def val_lat(self, key, value):
        return validate_latitude(value)

    @validates("longitude")
    def val_lon(self, key, value):
        return validate_longitude(value)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), default="New Weather Chat")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_msg_conv_created", "conversation_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String(20), nullable=False) # 'user' or 'bot'
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    language = Column(String(10), default="ta")
    risk_level = Column(String(20), nullable=True)
    data_timestamp = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    conversation = relationship("Conversation", back_populates="messages")
    advisory = relationship("Advisory", back_populates="message", uselist=False, cascade="all, delete-orphan")


class Advisory(Base):
    __tablename__ = "advisories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    persona = Column(String(50), nullable=False)
    target_activity = Column(String(100), nullable=True)
    risk_level = Column(String(20), nullable=False)
    recommendation = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    message = relationship("Message", back_populates="advisory")


class AlertDeliveryLog(Base):
    __tablename__ = "alert_delivery_logs"
    __table_args__ = (
        Index("idx_alert_deliv_user", "user_id", "created_at"),
        Index("idx_alert_deliv_fp", "alert_fingerprint", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    alert_id = Column(String(36), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    alert_fingerprint = Column(String(64), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    location_name = Column(String(100), nullable=False)
    channel = Column(String(20), default="fcm")
    status = Column(String(20), nullable=False)  # 'SENT', 'SKIPPED', 'FAILED'
    reason = Column(String(100), nullable=False)
    language = Column(String(10), default="ta")
    payload_preview = Column(String(255), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    __table_args__ = (
        Index("idx_device_token_user", "user_id", "is_active"),
        Index("idx_device_token_val", "token", unique=True),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(512), nullable=False, unique=True, index=True)
    platform = Column(String(20), default="android", nullable=False)
    device_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="device_tokens")
