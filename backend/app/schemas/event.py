"""
Schemas for Events and Virtual Meetups.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    event_type: str  # real_world, virtual, community, challenge
    location_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    start_time: datetime
    end_time: datetime
    reward_xp: int = 100
    reward_title: Optional[str] = None
    max_participants: Optional[int] = None


class EventResponse(BaseModel):
    id: int
    event_id: str
    title: str
    description: Optional[str]
    event_type: str
    location_id: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    radius_meters: Optional[float]
    start_time: datetime
    end_time: datetime
    reward_xp: int
    reward_title: Optional[str]
    status: str
    max_participants: Optional[int]
    created_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class EventParticipantResponse(BaseModel):
    id: int
    event_id: int
    user_id: int
    status: str
    score: int
    registered_at: datetime
    checked_in_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class MeetupCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location_id: Optional[int] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    max_duration_minutes: int = 60
    max_participants: int = 10


class MeetupResponse(BaseModel):
    id: int
    meetup_id: str
    title: str
    description: Optional[str]
    host_id: int
    location_id: Optional[int]
    start_time: datetime
    end_time: Optional[datetime]
    max_duration_minutes: int
    max_participants: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MeetupParticipantResponse(BaseModel):
    id: int
    meetup_id: int
    user_id: int
    status: str
    joined_at: datetime
    left_at: Optional[datetime]

    class Config:
        from_attributes = True
