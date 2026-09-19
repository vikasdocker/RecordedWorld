"""
Permission Model

Granular permission system for resources.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Permission(Base):
    """
    Granular permissions for resources.
    
    Permission Types:
      - location:read, location:write, location:delete, location:moderate
      - capture:read, capture:write, capture:delete
      - user:read, user:write, user:admin
      - world:read, world:write, world:admin
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Resource identification
    resource_type = Column(String, nullable=False)  # location, capture, user, world, etc.
    resource_id = Column(Integer, nullable=False)  # ID of the resource
    
    # Permission details
    permission = Column(String, nullable=False)  # read, write, delete, moderate, admin
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Who granted this
    
    # Grantee
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Specific user
    group = Column(String, nullable=True, index=True)  # Group permission (friends, public, etc.)
    
    # Expiry
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    grantor = relationship("User", foreign_keys=[granted_by], backref="granted_permissions")
    grantee = relationship("User", foreign_keys=[user_id], backref="received_permissions")

    __table_args__ = (
        UniqueConstraint(
            'resource_type', 'resource_id', 'user_id', 'permission',
            name='uq_user_permission'
        ),
    )


class ResourceACL(Base):
    """
    Access Control Lists for resources.
    
    Defines who can access a resource and what level of access they have.
    """
    __tablename__ = "resource_acls"

    id = Column(Integer, primary_key=True, index=True)
    
    # Resource identification
    resource_type = Column(String, nullable=False)  # location, capture, user, world
    resource_id = Column(Integer, nullable=False)
    
    # ACL rules
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    visibility = Column(String, default="private")  # public, unlisted, private, friends_only
    
    # Access levels
    allow_anonymous_read = Column(String, default="false")  # true, false
    allow_authenticated_read = Column(String, default="true")  # true, false
    allow_friends_read = Column(String, default="false")  # true, false
    allow_owner_write = Column(String, default="true")  # true, false
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", backref="owned_resources")

    __table_args__ = (
        UniqueConstraint(
            'resource_type', 'resource_id',
            name='uq_resource_acl'
        ),
    )
