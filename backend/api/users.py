from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.db.models import User, UserPreference

router = APIRouter(prefix="/users", tags=["Users"])

class UserUpdate(BaseModel):
    name: str
    language: str = "ta"
    persona: str = "student"

@router.get("/me")
async def get_user_profile(user_id: str = "default_user", db: Session = Depends(get_db)):
    """Returns current user profile information."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {
            "id": "guest_user",
            "name": "Guest User",
            "email": "guest@weathergpt.moes.gov.in",
            "language": "ta",
            "persona": "student"
        }
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "language": user.language,
        "persona": user.persona
    }

@router.put("/me")
async def update_user_profile(req: UserUpdate, user_id: str = "default_user", db: Session = Depends(get_db)):
    """Updates user persona and language preferences."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.name = req.name
        user.language = req.language
        user.persona = req.persona
        db.commit()
    return {
        "message": "Profile updated successfully",
        "user": {
            "name": req.name,
            "language": req.language,
            "persona": req.persona
        }
    }
