from backend.db.session import engine, Base
from backend.db import models # Ensure all models are registered

def init_db():
    """Create all database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    print("Initializing WeatherGPT Database...")
    init_db()
    print("Database initialization complete.")
