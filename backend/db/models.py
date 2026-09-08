import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.db.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    language = Column(String(10), default="ta")
    persona = Column(String(50), default="student")
    created_at = Column(DateTime(timezone=True), default=utc_now)

    preferences = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    preferred_units = Column(String(20), default="metric")
    persona = Column(String(50), default="student")
    notification_enabled = Column(Boolean, default=True)
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


class WeatherRecord(Base):
    __tablename__ = "weather_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    location_name = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    rain_probability = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    condition = Column(String(100), nullable=False)
    source = Column(String(50), default="IMD")
    observed_at = Column(DateTime(timezone=True), default=utc_now)
    retrieved_at = Column(DateTime(timezone=True), default=utc_now)


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    location_name = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    forecast_time = Column(DateTime(timezone=True), nullable=False)
    temperature = Column(Float, nullable=False)
    rain_probability = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    condition = Column(String(100), nullable=False)
    source = Column(String(50), default="IMD")
    retrieved_at = Column(DateTime(timezone=True), default=utc_now)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    location_name = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    source = Column(String(50), default="IMD")
    issued_at = Column(DateTime(timezone=True), default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    title = Column(String(255), default="New Weather Chat")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
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
    message_id = Column(String(36), ForeignKey("messages.id"), nullable=False, unique=True)
    persona = Column(String(50), nullable=False)
    target_activity = Column(String(100), nullable=True)
    risk_level = Column(String(20), nullable=False)
    recommendation = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    message = relationship("Message", back_populates="advisory")
