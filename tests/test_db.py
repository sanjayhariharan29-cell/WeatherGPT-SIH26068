import pytest
from backend.db.session import SessionLocal, Base, engine
from backend.db.models import User, Location, WeatherRecord, Conversation, Message, Advisory

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_user_creation():
    db = SessionLocal()
    user = User(
        name="Test Student",
        email="student@test.com",
        password_hash="hashed_secret",
        persona="student",
        language="ta"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.id is not None
    assert user.name == "Test Student"
    assert user.persona == "student"

    fetched = db.query(User).filter(User.email == "student@test.com").first()
    assert fetched is not None
    assert fetched.email == "student@test.com"
    db.close()

def test_location_and_weather_record():
    db = SessionLocal()
    rec = WeatherRecord(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature=29.0,
        humidity=72.0,
        rain_probability=65.0,
        wind_speed=18.0,
        condition="Moderate Rain",
        source="IMD"
    )
    db.add(rec)
    db.commit()

    assert rec.id is not None
    assert rec.location_name == "Coimbatore"
    assert rec.source == "IMD"
    db.close()

def test_conversation_and_messages():
    db = SessionLocal()
    conv = Conversation(title="College Travel Query")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    msg = Message(
        conversation_id=conv.id,
        sender="user",
        content="Naalaiku morning college pogalama?",
        intent="outdoor_decision",
        language="ta"
    )
    db.add(msg)
    db.commit()

    assert msg.id is not None
    assert msg.conversation_id == conv.id
    db.close()
