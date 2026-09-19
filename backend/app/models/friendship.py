from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Friendship(Base):
    """
    Bidirectional friendship relationship between two users.

    A single row represents the relationship. Status values:
    - pending: requester sent request, awaiting addressee response
    - accepted: both users are friends
    - rejected: addressee rejected the request (row can be deleted or reused)
    - blocked: addressee blocked the requester (prevents future requests)
    """
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    addressee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")  # pending, accepted, rejected, blocked

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    requester = relationship("User", foreign_keys=[requester_id], backref="sent_friend_requests")
    addressee = relationship("User", foreign_keys=[addressee_id], backref="received_friend_requests")

    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
    )
