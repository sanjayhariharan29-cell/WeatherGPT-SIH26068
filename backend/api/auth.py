import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.db.models import User, UserPreference

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    persona: str = "student"
    language: str = "ta"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

@router.post("/register")
async def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user and creates default preferences."""
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    user = User(
        name=req.name,
        email=req.email,
        password_hash=hash_password(req.password),
        persona=req.persona,
        language=req.language
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    pref = UserPreference(
        user_id=user.id,
        persona=req.persona,
        preferred_units="metric"
    )
    db.add(pref)
    db.commit()

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "message": "Registration successful"
    }

@router.post("/login")
async def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates a user."""
    hashed = hash_password(req.password)
    user = db.query(User).filter(User.email == req.email, User.password_hash == hashed).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    return {
        "access_token": f"token_{user.id}",
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "language": user.language,
            "persona": user.persona
        }
    }
