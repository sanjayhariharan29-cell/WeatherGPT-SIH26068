import uuid
import bcrypt
import hashlib
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Set
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.config.settings import settings
from backend.db.session import get_db
from backend.db.models import User, RevokedToken

# In-memory revocation cache for instant lookup
_REVOKED_JTIS: Set[str] = set()

security_scheme = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Hashes password securely using bcrypt."""
    if not password:
        raise ValueError("Password cannot be empty")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against stored hash (bcrypt or fallback sha256)."""
    if not plain_password or not hashed_password:
        return False
    try:
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$") or hashed_password.startswith("$2y$"):
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        # Fallback for old sha256 hashes
        sha256_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return sha256_hash == hashed_password
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token with expiration and unique JTI."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    jti = to_encode.get("jti") or str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "iat": now,
        "jti": jti
    })
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token

def decode_access_token(token: str) -> dict:
    """Decodes and validates JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )

def revoke_token(jti_or_token: str, db: Session) -> None:
    """Revokes a JWT token by adding its JTI to the revocation list."""
    jti = jti_or_token
    # If a full token was passed, extract JTI from it
    if len(jti_or_token) > 50 and "." in jti_or_token:
        try:
            payload = jwt.decode(jti_or_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={"verify_exp": False})
            jti = payload.get("jti", jti_or_token)
        except Exception:
            jti = jti_or_token

    _REVOKED_JTIS.add(jti)
    # Persist in DB
    existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if not existing:
        db.add(RevokedToken(jti=jti))
        db.commit()

def is_token_revoked(jti: str, db: Session) -> bool:
    """Checks if a token JTI has been revoked."""
    if jti in _REVOKED_JTIS:
        return True
    revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if revoked:
        _REVOKED_JTIS.add(jti)
        return True
    return False

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency to extract and validate the authenticated user from Bearer token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    # Support backward compatibility with legacy token format token_<user_id>
    if token.startswith("token_"):
        user_id = token.replace("token_", "")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token or user not found"
            )
        return user

    payload = decode_access_token(token)
    jti = payload.get("jti")
    if jti and is_token_revoked(jti, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user

def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """FastAPI dependency to get current user if authenticated, else None."""
    if not credentials or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None

def require_role(required_role: str):
    """Dependency factory to enforce role-based access control."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation"
            )
        return current_user
    return role_checker
