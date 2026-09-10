import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User, UserPreference
from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    VerifyEmailRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    VerifyResetTokenRequest,
    ResetPasswordRequest,
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


def _is_expired(expires_at: Optional[datetime]) -> bool:
    """Helper to check expiration safely handling naive or timezone-aware datetimes."""
    if not expires_at:
        return True
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return now > expires_at


@router.post("/register", status_code=status.HTTP_200_OK)
async def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user securely with hashed password, email verification token, and default preferences."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Hash password using bcrypt
    hashed = hash_password(req.password)
    
    # Generate 6-digit email verification token (expires in 24 hours)
    verification_token = f"{secrets.randbelow(900000) + 100000}"
    verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)

    user = User(
        name=req.name,
        email=req.email.lower(),
        password_hash=hashed,
        persona=req.persona,
        language=req.language,
        role=req.role,
        is_verified=False,
        verification_token=verification_token,
        verification_token_expires=verification_expires
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
        "is_verified": False,
        "verification_token": verification_token,
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
            "role": user.role,
            "is_verified": bool(user.is_verified)
        }
    }


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Validates real server-side email verification token and marks account as verified."""
    token = req.token.strip()
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )
    
    if _is_expired(user.verification_token_expires):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one."
        )

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.commit()

    return {
        "message": "Email verified successfully.",
        "is_verified": True,
        "email": user.email
    }


@router.post("/resend-verification")
async def resend_verification(req: ResendVerificationRequest, db: Session = Depends(get_db)):
    """Generates a fresh verification token for unverified accounts."""
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user:
        return {"message": "If the account exists, a new verification code has been issued."}
    
    if user.is_verified:
        return {"message": "Account is already verified.", "is_verified": True}
    
    verification_token = f"{secrets.randbelow(900000) + 100000}"
    user.verification_token = verification_token
    user.verification_token_expires = datetime.now(timezone.utc) + timedelta(hours=24)
    db.commit()

    return {
        "message": "Verification code resent successfully.",
        "verification_token": verification_token
    }


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Generates a secure password reset token with 1-hour expiration."""
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user:
        # Prevent account enumeration
        return {"message": "If the email is registered, password reset instructions have been generated."}
    
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()

    return {
        "message": "If the email is registered, password reset instructions have been generated.",
        "reset_token": reset_token
    }


@router.post("/verify-reset-token")
async def verify_reset_token(req: VerifyResetTokenRequest, db: Session = Depends(get_db)):
    """Validates that a password reset token exists and has not expired."""
    token = req.token.strip()
    user = db.query(User).filter(User.reset_token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    if _is_expired(user.reset_token_expires):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired"
        )

    return {"valid": True, "email": user.email}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Resets user password securely using a verified reset token."""
    token = req.token.strip()
    user = db.query(User).filter(User.reset_token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    if _is_expired(user.reset_token_expires):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired"
        )

    # Hash new password
    user.password_hash = hash_password(req.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password reset successfully. You may now log in with your new password."}


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
        "role": current_user.role,
        "is_verified": bool(current_user.is_verified)
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
            "is_verified": bool(u.is_verified),
            "created_at": u.created_at.isoformat() if u.created_at else None
        }
        for u in users
    ]
