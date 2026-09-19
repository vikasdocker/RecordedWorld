"""
Role-based access control dependency.

Usage in endpoints:
    @router.get("/admin")
    def admin_endpoint(user=Depends(require_role("admin"))):
        ...
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.models.user import User
from app.models.role import Role, ROLE_LEVELS


def get_user_roles(db: Session, user_id: int) -> list[str]:
    """Get list of role names for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []
    return [r.name for r in user.roles]


def get_user_max_role_level(db: Session, user_id: int) -> int:
    """Get the highest role level for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return -1
    levels = [ROLE_LEVELS.get(r.name, 0) for r in user.roles]
    return max(levels) if levels else -1


def require_role(min_role: str):
    """
    Dependency factory that returns a dependency requiring a minimum role level.

    Usage:
        @router.get("/admin")
        def admin_endpoint(user_id: int = Depends(require_role("moderator"))):
            ...
    """
    min_level = ROLE_LEVELS.get(min_role, 0)

    def check_role(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
        user_level = get_user_max_role_level(db, user_id)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{min_role}' (level {min_level}), user has level {user_level}",
            )
        return user_id

    return check_role


def require_any_role(*role_names: str):
    """
    Dependency factory requiring any of the listed roles.

    Usage:
        @router.get("/mod-or-admin")
        def endpoint(user_id: int = Depends(require_any_role("moderator", "admin"))):
            ...
    """
    min_level = max(ROLE_LEVELS.get(r, 0) for r in role_names)

    def check_role(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
        user_level = get_user_max_role_level(db, user_id)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles {role_names}, user has level {user_level}",
            )
        return user_id

    return check_role
