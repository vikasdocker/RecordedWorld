from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.middleware.jwt_auth import get_current_user, get_optional_user


router = APIRouter(prefix="/api/users", tags=["users"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register", response_model=UserResponse)
@router.post("/", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        new_user = AuthService.create_user(
            db=db,
            username=user.username,
            email=user.email,
            password=user.password,
        )
        return new_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login and get a JWT token."""
    user = AuthService.authenticate(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = AuthService.create_token(user)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get the current authenticated user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
def update_current_user_profile(
    display_name: Optional[str] = None,
    location_sharing: Optional[bool] = None,
    approximate_location: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current authenticated user's profile."""
    try:
        return AuthService.update_profile(
            db=db,
            user_id=current_user.id,
            display_name=display_name,
            location_sharing=location_sharing,
            approximate_location=approximate_location,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Get a user by ID. Works with or without authentication."""
    db_user = AuthService.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
