"""
Tests for Events and Virtual Meetups API endpoints.
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.gameplay import GameEvent, VirtualMeetup


client = TestClient(app)


@pytest.fixture(scope="module")
def setup_db():
    """Create tables and test user."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        import uuid
        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"api_event_test_{uid}",
            email=f"api_event_{uid}@example.com",
            password_hash="salt:hash",
            display_name="API Event Test User",
            location_sharing=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


class TestEventsAPI:
    def test_list_events(self):
        response = client.get("/api/events/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_event(self, setup_db):
        now = datetime.now(timezone.utc)
        response = client.post("/api/events/", json={
            "title": "Test API Event",
            "description": "Created via API",
            "event_type": "virtual",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
            "reward_xp": 150,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test API Event"
        assert data["event_type"] == "virtual"
        assert data["status"] == "scheduled"
        assert data["reward_xp"] == 150

    def test_get_event(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post("/api/events/", json={
            "title": "Get Test Event",
            "event_type": "community",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        })
        event_id = create.json()["id"]
        response = client.get(f"/api/events/{event_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Get Test Event"

    def test_get_event_not_found(self):
        response = client.get("/api/events/999999")
        assert response.status_code == 404

    def test_register_event(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post("/api/events/", json={
            "title": "Register Test Event",
            "event_type": "challenge",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "max_participants": 10,
        })
        event_id = create.json()["id"]
        response = client.post(f"/api/events/{event_id}/register?user_id={setup_db}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "registered"
        assert data["user_id"] == setup_db

    def test_register_event_duplicate(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post("/api/events/", json={
            "title": "Dup Register Event",
            "event_type": "virtual",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        })
        event_id = create.json()["id"]
        client.post(f"/api/events/{event_id}/register?user_id={setup_db}")
        response = client.post(f"/api/events/{event_id}/register?user_id={setup_db}")
        assert response.status_code == 409

    def test_list_event_participants(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post("/api/events/", json={
            "title": "Participants Test Event",
            "event_type": "virtual",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        })
        event_id = create.json()["id"]
        response = client.get(f"/api/events/{event_id}/participants")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestMeetupsAPI:
    def test_list_meetups(self):
        response = client.get("/api/meetups/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_meetup(self, setup_db):
        now = datetime.now(timezone.utc)
        response = client.post(f"/api/meetups/?host_id={setup_db}", json={
            "title": "Test API Meetup",
            "description": "Created via API",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "max_participants": 5,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test API Meetup"
        assert data["host_id"] == setup_db
        assert data["max_participants"] == 5

    def test_get_meetup(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post(f"/api/meetups/?host_id={setup_db}", json={
            "title": "Get Test Meetup",
            "start_time": now.isoformat(),
        })
        meetup_id = create.json()["id"]
        response = client.get(f"/api/meetups/{meetup_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Get Test Meetup"

    def test_get_meetup_not_found(self):
        response = client.get("/api/meetups/999999")
        assert response.status_code == 404

    def test_join_meetup(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post(f"/api/meetups/?host_id={setup_db}", json={
            "title": "Join Test Meetup",
            "start_time": now.isoformat(),
            "max_participants": 5,
        })
        meetup_id = create.json()["id"]
        response = client.post(f"/api/meetups/{meetup_id}/join?user_id={setup_db}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "joined"

    def test_join_meetup_duplicate(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post(f"/api/meetups/?host_id={setup_db}", json={
            "title": "Dup Join Meetup",
            "start_time": now.isoformat(),
        })
        meetup_id = create.json()["id"]
        client.post(f"/api/meetups/{meetup_id}/join?user_id={setup_db}")
        response = client.post(f"/api/meetups/{meetup_id}/join?user_id={setup_db}")
        assert response.status_code == 409

    def test_leave_meetup(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post(f"/api/meetups/?host_id={setup_db}", json={
            "title": "Leave Test Meetup",
            "start_time": now.isoformat(),
        })
        meetup_id = create.json()["id"]
        client.post(f"/api/meetups/{meetup_id}/join?user_id={setup_db}")
        response = client.post(f"/api/meetups/{meetup_id}/leave?user_id={setup_db}")
        assert response.status_code == 200

    def test_list_meetup_participants(self, setup_db):
        now = datetime.now(timezone.utc)
        create = client.post(f"/api/meetups/?host_id={setup_db}", json={
            "title": "Participants Meetup",
            "start_time": now.isoformat(),
        })
        meetup_id = create.json()["id"]
        response = client.get(f"/api/meetups/{meetup_id}/participants")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
