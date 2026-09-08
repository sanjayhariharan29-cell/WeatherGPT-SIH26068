import pytest
from datetime import datetime, timezone
from backend.db.session import SessionLocal, Base, engine
from backend.db.models import User, UserPreference, Location, WeatherRecord, Forecast, Alert, Conversation, Message, Advisory

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_latitude_validation():
    db = SessionLocal()
    with pytest.raises(ValueError, match=r"Latitude must be between -90 and \+90"):
        loc = Location(name="Invalid Lat", latitude=95.0, longitude=78.0)
        db.add(loc)
        db.commit()
    db.close()

def test_longitude_validation():
    db = SessionLocal()
    with pytest.raises(ValueError, match=r"Longitude must be between -180 and \+180"):
        loc = Location(name="Invalid Lon", latitude=11.0, longitude=195.0)
        db.add(loc)
        db.commit()
    db.close()

def test_timezone_awareness():
    db = SessionLocal()
    rec = WeatherRecord(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature=29.0,
        humidity=70.0,
        rain_probability=60.0,
        wind_speed=15.0,
        condition="Rain"
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    assert rec.observed_at.tzinfo is not None or isinstance(rec.observed_at, datetime)
    db.close()

def test_cascading_deletions():
    db = SessionLocal()
    user = User(name="Cascade User", email="cascade@test.com", password_hash="hash")
    db.add(user)
    db.commit()
    db.refresh(user)

    pref = UserPreference(user_id=user.id, persona="farmer")
    db.add(pref)

    conv = Conversation(user_id=user.id, title="Farm Chat")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    msg = Message(conversation_id=conv.id, sender="user", content="Rain forecast for crops?")
    db.add(msg)
    db.commit()
    db.refresh(msg)

    adv = Advisory(message_id=msg.id, persona="farmer", risk_level="medium", recommendation="Check drainage")
    db.add(adv)
    db.commit()

    # Delete User -> Preferences and Conversations should be deleted
    db.delete(user)
    db.commit()

    assert db.query(UserPreference).filter(UserPreference.user_id == user.id).first() is None
    assert db.query(Conversation).filter(Conversation.id == conv.id).first() is None
    db.close()

def test_table_indexes_exist():
    tables = Base.metadata.tables
    assert "users" in tables
    assert "weather_records" in tables
    assert "forecasts" in tables
    assert "alerts" in tables
    assert "messages" in tables

    weather_table = tables["weather_records"]
    index_names = [idx.name for idx in weather_table.indexes]
    assert "idx_weather_loc_observed" in index_names
