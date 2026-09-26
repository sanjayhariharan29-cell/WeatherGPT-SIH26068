"""Root entrypoint forwarding to backend.main:app.

Enables seamless compatibility with standard cloud hosting providers (Render, Heroku, Railway)
regardless of whether the Start Command is configured as 'uvicorn main:app' or 'uvicorn backend.main:app'.
"""
import os
from backend.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
