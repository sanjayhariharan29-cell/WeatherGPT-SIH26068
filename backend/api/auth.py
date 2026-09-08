from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User, UserPreference
from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse
)
from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    revoke_token,
    get_current_user,
    require_role,
    security_scheme
)
from backend.config.settings import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", status_code=status.HTTP_200_OK)
async def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user securely with hashed password and default preferences."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Hash password using bcrypt
    hashed = hash_password(req.password)
    
    user = User(
        name=req.name,
        email=req.email.lower(),
        password_hash=hashed,
        persona=req.persona,
        language=req.language,
        role=req.role
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
        "role": user.role,
        "message": "Registration successful"
    }

@router.post("/login")
async def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates user and returns JWT token. Uses generic error messages for security."""
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token = create_access_token(data={
        "sub": user.id,
        "email": user.email,
        "role": user.role
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "language": user.language,
            "persona": user.persona,
            "role": user.role
        }
    }

@router.post("/logout")
async def logout_user(
    current_user: User = Depends(get_current_user),
    credentials=Depends(security_scheme),
    db: Session = Depends(get_db)
):
    """Revokes the current JWT session token."""
    if credentials and credentials.credentials:
        revoke_token(credentials.credentials, db)
    return {"message": "Logout successful"}

@router.get("/me")
async def get_auth_profile(current_user: User = Depends(get_current_user)):
    """Returns profile for currently authenticated user."""
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "language": current_user.language,
        "persona": current_user.persona,
        "role": current_user.role
    }

@router.get("/admin/users", dependencies=[Depends(require_role("admin"))])
async def list_users_admin(db: Session = Depends(get_db)):
    """Protected admin endpoint to list registered users."""
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None
        }
        for u in users
    ]
