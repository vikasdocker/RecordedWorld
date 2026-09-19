"""
Role Model

RBAC system for user authorization.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


# Association table for many-to-many user-role relationship
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("assigned_at", DateTime(timezone=True), server_default=func.now()),
)


class Role(Base):
    """
    A named role with a permission level.

    Built-in roles:
      - viewer: default, read-only access
      - creator: can create locations and captures
      - moderator: can moderate content (approve/reject)
      - admin: full access
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    level = Column(Integer, nullable=False, default=0)  # higher = more permissions

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", secondary=user_roles, backref="roles")


# Role hierarchy levels
ROLE_LEVELS = {
    "viewer": 0,
    "creator": 10,
    "moderator": 50,
    "admin": 100,
}


def get_role_level(role_name: str) -> int:
    """Get the permission level for a role name."""
    return ROLE_LEVELS.get(role_name, 0)
