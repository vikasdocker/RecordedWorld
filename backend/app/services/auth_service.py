"""
Auth Service

User authentication, token management, and authorization.
"""

from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.models.user import User
from app.services.secret_manager import get_secret_manager


class AuthService:
    """Handles user authentication and authorization."""

    @staticmethod
    def create_user(
        db: Session,
        username: str,
        email: str,
        password: str,
        display_name: Optional[str] = None,
    ) -> User:
        """Register a new user."""
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            if existing.username == username:
                raise ValueError("Username already taken")
            raise ValueError("Email already registered")

        secret_mgr = get_secret_manager()
        password_hash = secret_mgr.hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            display_name=display_name or username,
            location_sharing=True,
            approximate_location=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate(
        db: Session,
        username: str,
        password: str,
    ) -> Optional[User]:
        """Authenticate user by username and password. Returns User or None."""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None

        secret_mgr = get_secret_manager()
        if not secret_mgr.verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_token(user: User) -> str:
        """Create a JWT access token for a user."""
        secret_mgr = get_secret_manager()
        return secret_mgr.create_access_token(
            user_id=user.id,
            username=user.username
        )

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify and decode a JWT token. Returns payload or None."""
        secret_mgr = get_secret_manager()
        return secret_mgr.verify_access_token(token)

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_profile(
        db: Session,
        user_id: int,
        display_name: Optional[str] = None,
        location_sharing: Optional[bool] = None,
        approximate_location: Optional[bool] = None,
    ) -> User:
        """Update user profile fields."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        if display_name is not None:
            user.display_name = display_name
        if location_sharing is not None:
            user.location_sharing = location_sharing
        if approximate_location is not None:
            user.approximate_location = approximate_location
        db.commit()
        db.refresh(user)
        return user
