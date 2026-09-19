"""
Tests for Event and Virtual Meetup models.
"""
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.gameplay import (
    GameEvent, EventParticipant, VirtualMeetup, MeetupParticipant
)


client = TestClient(app)


@pytest.fixture(scope="module")
def test_user():
    """Create a test user."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"event_test_{uid}",
            email=f"event_test_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Event Test User",
            location_sharing=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


class TestGameEvent:
    def test_create_event(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            event = GameEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                title="Test Event",
                description="A test event",
                event_type="real_world",
                start_time=now,
                end_time=now + timedelta(hours=2),
                reward_xp=200,
                created_by=test_user.id,
            )
            db.add(event)
            db.commit()
            db.refresh(event)

            assert event.id is not None
            assert event.title == "Test Event"
            assert event.status == "scheduled"
            assert event.reward_xp == 200
        finally:
            db.close()

    def test_create_virtual_event(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            event = GameEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                title="Virtual Event",
                event_type="virtual",
                start_time=now,
                end_time=now + timedelta(hours=1),
                max_participants=50,
            )
            db.add(event)
            db.commit()
            db.refresh(event)

            assert event.event_type == "virtual"
            assert event.max_participants == 50
        finally:
            db.close()

    def test_event_with_location(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            event = GameEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                title="Location Event",
                event_type="real_world",
                latitude=37.7749,
                longitude=-122.4194,
                radius_meters=500.0,
                start_time=now,
                end_time=now + timedelta(hours=3),
            )
            db.add(event)
            db.commit()
            db.refresh(event)

            assert event.latitude == 37.7749
            assert event.longitude == -122.4194
            assert event.radius_meters == 500.0
        finally:
            db.close()


class TestEventParticipant:
    def test_register_participant(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            event = GameEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                title="Join Test",
                event_type="virtual",
                start_time=now,
                end_time=now + timedelta(hours=1),
            )
            db.add(event)
            db.flush()

            participant = EventParticipant(
                event_id=event.id,
                user_id=test_user.id,
                status="registered",
            )
            db.add(participant)
            db.commit()
            db.refresh(participant)

            assert participant.id is not None
            assert participant.status == "registered"
        finally:
            db.close()

    def test_checkin_participant(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            event = GameEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                title="Checkin Test",
                event_type="virtual",
                start_time=now,
                end_time=now + timedelta(hours=1),
            )
            db.add(event)
            db.flush()

            participant = EventParticipant(
                event_id=event.id,
                user_id=test_user.id,
                status="checked_in",
                checked_in_at=datetime.now(timezone.utc),
            )
            db.add(participant)
            db.commit()
            db.refresh(participant)

            assert participant.status == "checked_in"
            assert participant.checked_in_at is not None
        finally:
            db.close()


class TestVirtualMeetup:
    def test_create_meetup(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            meetup = VirtualMeetup(
                meetup_id=f"mt-{uuid.uuid4().hex[:8]}",
                title="Test Meetup",
                description="A test meetup",
                host_id=test_user.id,
                start_time=now,
                end_time=now + timedelta(hours=1),
                max_participants=5,
            )
            db.add(meetup)
            db.commit()
            db.refresh(meetup)

            assert meetup.id is not None
            assert meetup.title == "Test Meetup"
            assert meetup.host_id == test_user.id
            assert meetup.status == "scheduled"
        finally:
            db.close()

    def test_meetup_defaults(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            meetup = VirtualMeetup(
                meetup_id=f"mt-{uuid.uuid4().hex[:8]}",
                title="Defaults Test",
                host_id=test_user.id,
                start_time=now,
            )
            db.add(meetup)
            db.commit()
            db.refresh(meetup)

            assert meetup.max_duration_minutes == 60
            assert meetup.max_participants == 10
        finally:
            db.close()


class TestMeetupParticipant:
    def test_join_meetup(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            meetup = VirtualMeetup(
                meetup_id=f"mt-{uuid.uuid4().hex[:8]}",
                title="Join Test",
                host_id=test_user.id,
                start_time=now,
            )
            db.add(meetup)
            db.flush()

            participant = MeetupParticipant(
                meetup_id=meetup.id,
                user_id=test_user.id,
                status="joined",
            )
            db.add(participant)
            db.commit()
            db.refresh(participant)

            assert participant.id is not None
            assert participant.status == "joined"
        finally:
            db.close()

    def test_leave_meetup(self, test_user):
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            meetup = VirtualMeetup(
                meetup_id=f"mt-{uuid.uuid4().hex[:8]}",
                title="Leave Test",
                host_id=test_user.id,
                start_time=now,
            )
            db.add(meetup)
            db.flush()

            participant = MeetupParticipant(
                meetup_id=meetup.id,
                user_id=test_user.id,
                status="left",
                left_at=datetime.now(timezone.utc),
            )
            db.add(participant)
            db.commit()
            db.refresh(participant)

            assert participant.status == "left"
            assert participant.left_at is not None
        finally:
            db.close()


class TestModelFields:
    def test_event_model_fields(self):
        columns = {c.name for c in GameEvent.__table__.columns}
        expected = {
            'id', 'event_id', 'title', 'description', 'event_type',
            'location_id', 'latitude', 'longitude', 'radius_meters',
            'start_time', 'end_time', 'reward_xp', 'reward_title',
            'status', 'max_participants', 'created_by', 'created_at', 'updated_at'
        }
        assert expected.issubset(columns)

    def test_meetup_model_fields(self):
        columns = {c.name for c in VirtualMeetup.__table__.columns}
        expected = {
            'id', 'meetup_id', 'title', 'description', 'host_id',
            'location_id', 'start_time', 'end_time', 'max_duration_minutes',
            'max_participants', 'status', 'created_at', 'updated_at'
        }
        assert expected.issubset(columns)

    def test_event_participant_model_fields(self):
        columns = {c.name for c in EventParticipant.__table__.columns}
        expected = {
            'id', 'event_id', 'user_id', 'status', 'score',
            'registered_at', 'checked_in_at', 'completed_at'
        }
        assert expected.issubset(columns)

    def test_meetup_participant_model_fields(self):
        columns = {c.name for c in MeetupParticipant.__table__.columns}
        expected = {
            'id', 'meetup_id', 'user_id', 'status',
            'joined_at', 'left_at'
        }
        assert expected.issubset(columns)
