"""
Events and Virtual Meetups API endpoints.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.gameplay import (
    GameEvent, EventParticipant, VirtualMeetup, MeetupParticipant
)
from app.models.user import User
from app.schemas.event import (
    EventCreate, EventResponse, EventParticipantResponse,
    MeetupCreate, MeetupResponse, MeetupParticipantResponse
)

router = APIRouter(prefix="/api/events", tags=["events"])


# ── Events ──────────────────────────────────────────────────────────────

@router.get("/", response_model=List[EventResponse])
def list_events(
    event_type: str = Query(None, description="Filter by type"),
    status: str = Query("active", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(GameEvent)
    if event_type:
        query = query.filter(GameEvent.event_type == event_type)
    if status:
        query = query.filter(GameEvent.status == status)
    return query.order_by(GameEvent.start_time.desc()).limit(limit).all()


@router.post("/", response_model=EventResponse)
def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
):
    db_event = GameEvent(
        event_id=f"evt-{uuid.uuid4().hex[:12]}",
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        location_id=event.location_id,
        latitude=event.latitude,
        longitude=event.longitude,
        radius_meters=event.radius_meters,
        start_time=event.start_time,
        end_time=event.end_time,
        reward_xp=event.reward_xp,
        reward_title=event.reward_title,
        max_participants=event.max_participants,
        status="scheduled",
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = db.query(GameEvent).filter(GameEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/{event_id}/register", response_model=EventParticipantResponse)
def register_event(
    event_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db),
):
    event = db.query(GameEvent).filter(GameEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    existing = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already registered")

    if event.max_participants:
        count = db.query(EventParticipant).filter(
            EventParticipant.event_id == event_id
        ).count()
        if count >= event.max_participants:
            raise HTTPException(status_code=400, detail="Event is full")

    participant = EventParticipant(
        event_id=event_id,
        user_id=user_id,
        status="registered",
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


@router.get("/{event_id}/participants", response_model=List[EventParticipantResponse])
def list_event_participants(
    event_id: int,
    db: Session = Depends(get_db),
):
    return db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id
    ).all()


# ── Virtual Meetups ─────────────────────────────────────────────────────

meetup_router = APIRouter(prefix="/api/meetups", tags=["meetups"])


@meetup_router.get("/", response_model=List[MeetupResponse])
def list_meetups(
    status: str = Query("active", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(VirtualMeetup)
    if status:
        query = query.filter(VirtualMeetup.status == status)
    return query.order_by(VirtualMeetup.start_time.desc()).limit(limit).all()


@meetup_router.post("/", response_model=MeetupResponse)
def create_meetup(
    meetup: MeetupCreate,
    host_id: int = Query(..., description="Host user ID"),
    db: Session = Depends(get_db),
):
    db_meetup = VirtualMeetup(
        meetup_id=f"mt-{uuid.uuid4().hex[:12]}",
        title=meetup.title,
        description=meetup.description,
        host_id=host_id,
        location_id=meetup.location_id,
        start_time=meetup.start_time,
        end_time=meetup.end_time,
        max_duration_minutes=meetup.max_duration_minutes,
        max_participants=meetup.max_participants,
        status="scheduled",
    )
    db.add(db_meetup)
    db.commit()
    db.refresh(db_meetup)
    return db_meetup


@meetup_router.get("/{meetup_id}", response_model=MeetupResponse)
def get_meetup(
    meetup_id: int,
    db: Session = Depends(get_db),
):
    meetup = db.query(VirtualMeetup).filter(VirtualMeetup.id == meetup_id).first()
    if not meetup:
        raise HTTPException(status_code=404, detail="Meetup not found")
    return meetup


@meetup_router.post("/{meetup_id}/join", response_model=MeetupParticipantResponse)
def join_meetup(
    meetup_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db),
):
    meetup = db.query(VirtualMeetup).filter(VirtualMeetup.id == meetup_id).first()
    if not meetup:
        raise HTTPException(status_code=404, detail="Meetup not found")

    existing = db.query(MeetupParticipant).filter(
        MeetupParticipant.meetup_id == meetup_id,
        MeetupParticipant.user_id == user_id,
        MeetupParticipant.status == "joined",
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already joined")

    count = db.query(MeetupParticipant).filter(
        MeetupParticipant.meetup_id == meetup_id,
        MeetupParticipant.status == "joined",
    ).count()
    if count >= meetup.max_participants:
        raise HTTPException(status_code=400, detail="Meetup is full")

    participant = MeetupParticipant(
        meetup_id=meetup_id,
        user_id=user_id,
        status="joined",
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


@meetup_router.post("/{meetup_id}/leave")
def leave_meetup(
    meetup_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db),
):
    participant = db.query(MeetupParticipant).filter(
        MeetupParticipant.meetup_id == meetup_id,
        MeetupParticipant.user_id == user_id,
        MeetupParticipant.status == "joined",
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Not a participant")

    participant.status = "left"
    participant.left_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Left meetup"}


@meetup_router.get("/{meetup_id}/participants", response_model=List[MeetupParticipantResponse])
def list_meetup_participants(
    meetup_id: int,
    db: Session = Depends(get_db),
):
    return db.query(MeetupParticipant).filter(
        MeetupParticipant.meetup_id == meetup_id
    ).all()
