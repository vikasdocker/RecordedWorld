from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FriendRequestCreate(BaseModel):
    addressee_id: int


class FriendshipResponse(BaseModel):
    id: int
    requester_id: int
    addressee_id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FriendshipDetail(BaseModel):
    """Extended friendship info with user details."""
    id: int
    user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FriendStatusResponse(BaseModel):
    """Response for friend status check."""
    user_id: int
    are_friends: bool
    pending_request: Optional[str] = None  # "sent", "received", or None
    blocked: bool = False
