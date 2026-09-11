from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User, UserPreference
from backend.schemas.auth import UserUpdateRequest, UserPreferenceSchema
from backend.core.security import get_current_user, get_optional_current_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me")
@router.get("/profile")
async def get_user_profile(
    current_user: Optional[User] = Depends(get_optional_current_user),
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Returns profile for currently authenticated user or requested profile if owned."""
    if current_user:
        # If user_id requested and differs from current_user.id (and not admin), enforce ownership check
        if user_id and user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot view another user's profile"
            )
        pref = current_user.preferences
        notif = pref.notification_enabled if pref else True
        return {
            "id": current_user.id,
            "name": current_user.name,
            "full_name": current_user.name,
            "email": current_user.email,
            "language": current_user.language,
            "preferred_language": current_user.language,
            "persona": current_user.persona,
            "role": current_user.role,
            "is_verified": bool(current_user.is_verified),
            "onboarding_completed": bool(current_user.onboarding_completed),
            "notification_enabled": bool(notif),
            "last_known_location": pref.last_known_location if pref else None,
            "last_latitude": pref.last_latitude if pref else None,
            "last_longitude": pref.last_longitude if pref else None,
            "last_location_source": pref.last_location_source if pref else None,
            "last_location_updated_at": pref.last_location_updated_at.isoformat() if (pref and pref.last_location_updated_at) else None
        }

    # Reject unauthenticated access to specific registered profiles (Prevent IDOR / Account Enumeration)
    if user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required to access user profiles"
        )
            
    return {
        "id": "guest_user",
        "name": "Guest User",
        "full_name": "Guest User",
        "email": "guest@weathergpt.moes.gov.in",
        "language": "ta",
        "preferred_language": "ta",
        "persona": "student",
        "role": "guest",
        "is_verified": False,
        "onboarding_completed": True,
        "notification_enabled": True,
        "last_known_location": None,
        "last_latitude": None,
        "last_longitude": None,
        "last_location_source": None,
        "last_location_updated_at": None
    }

@router.put("/me")
@router.put("/profile")
@router.patch("/profile")
async def update_user_profile(
    req: UserUpdateRequest,
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates the authenticated user's profile information (User Ownership Enforced)."""
    if user_id and user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot modify another user's profile"
        )

    if req.name is not None:
        current_user.name = req.name.strip()
    if req.language is not None:
        current_user.language = req.language
    if req.persona is not None:
        current_user.persona = req.persona
        if current_user.preferences:
            current_user.preferences.persona = req.persona
    if req.onboarding_completed is not None:
        current_user.onboarding_completed = req.onboarding_completed
    
    if not current_user.preferences:
        pref = UserPreference(
            user_id=current_user.id,
            persona=current_user.persona,
            notification_enabled=req.notification_enabled if req.notification_enabled is not None else True
        )
        db.add(pref)
        current_user.preferences = pref

    if req.notification_enabled is not None:
        current_user.preferences.notification_enabled = req.notification_enabled

    if req.last_known_location is not None:
        current_user.preferences.last_known_location = req.last_known_location
    if req.last_latitude is not None:
        current_user.preferences.last_latitude = req.last_latitude
    if req.last_longitude is not None:
        current_user.preferences.last_longitude = req.last_longitude
    if req.last_location_source is not None:
        current_user.preferences.last_location_source = req.last_location_source
    if req.last_known_location is not None or req.last_latitude is not None:
        from backend.db.models import utc_now
        current_user.preferences.last_location_updated_at = utc_now()
    
    db.commit()
    db.refresh(current_user)

    pref = current_user.preferences
    notif = pref.notification_enabled if pref else True
    user_dict = {
        "id": current_user.id,
        "name": current_user.name,
        "full_name": current_user.name,
        "email": current_user.email,
        "language": current_user.language,
        "preferred_language": current_user.language,
        "persona": current_user.persona,
        "role": current_user.role,
        "is_verified": bool(current_user.is_verified),
        "onboarding_completed": bool(current_user.onboarding_completed),
        "notification_enabled": bool(notif),
        "last_known_location": pref.last_known_location if pref else None,
        "last_latitude": pref.last_latitude if pref else None,
        "last_longitude": pref.last_longitude if pref else None,
        "last_location_source": pref.last_location_source if pref else None,
        "last_location_updated_at": pref.last_location_updated_at.isoformat() if (pref and pref.last_location_updated_at) else None
    }
    return {
        "message": "Profile updated successfully",
        "user": user_dict,
        **user_dict
    }

@router.get("/preferences")
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves user preferences for the authenticated user."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(
            user_id=current_user.id,
            persona=current_user.persona,
            preferred_units="metric",
            notification_enabled=True
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    
    return {
        "user_id": pref.user_id,
        "preferred_units": pref.preferred_units,
        "persona": pref.persona,
        "notification_enabled": pref.notification_enabled,
        "last_known_location": pref.last_known_location,
        "last_latitude": pref.last_latitude,
        "last_longitude": pref.last_longitude,
        "last_location_source": pref.last_location_source,
        "last_location_updated_at": pref.last_location_updated_at.isoformat() if pref.last_location_updated_at else None
    }

@router.put("/preferences")
async def update_user_preferences(
    req: UserPreferenceSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates user preferences for the authenticated user (User Ownership Enforced)."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)

    pref.preferred_units = req.preferred_units
    pref.persona = req.persona
    pref.notification_enabled = req.notification_enabled
    if req.last_known_location is not None:
        pref.last_known_location = req.last_known_location
    if req.last_latitude is not None:
        pref.last_latitude = req.last_latitude
    if req.last_longitude is not None:
        pref.last_longitude = req.last_longitude
    if req.last_location_source is not None:
        pref.last_location_source = req.last_location_source
    if req.last_known_location is not None or req.last_latitude is not None:
        from backend.db.models import utc_now
        pref.last_location_updated_at = utc_now()
        
    db.commit()

    pref_dict = {
        "user_id": current_user.id,
        "preferred_units": pref.preferred_units,
        "persona": pref.persona,
        "notification_enabled": pref.notification_enabled,
        "last_known_location": pref.last_known_location,
        "last_latitude": pref.last_latitude,
        "last_longitude": pref.last_longitude,
        "last_location_source": pref.last_location_source,
        "last_location_updated_at": pref.last_location_updated_at.isoformat() if pref.last_location_updated_at else None
    }
    return {
        "message": "Preferences updated successfully",
        "preferences": pref_dict,
        **pref_dict
    }
