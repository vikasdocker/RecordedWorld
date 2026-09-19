"""
Tests for Location Visibility and Moderation management endpoints.
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.location import Location


client = TestClient(app)


@pytest.fixture(scope="module")
def setup_db():
    """Create tables and test data."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"vis_test_{uid}",
            email=f"vis_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Visibility Test User",
            location_sharing=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        loc = Location(
            creator_id=user.id,
            title="Test Location",
            latitude=37.7749,
            longitude=-122.4194,
            visibility="public",
            moderation_state="pending",
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)

        return {"user_id": user.id, "location_id": loc.id}
    finally:
        db.close()


class TestVisibilityManagement:
    def test_update_visibility_public(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/visibility"
            f"?visibility=public&user_id={setup_db['user_id']}"
        )
        assert response.status_code == 200
        assert response.json()["visibility"] == "public"

    def test_update_visibility_private(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/visibility"
            f"?visibility=private&user_id={setup_db['user_id']}"
        )
        assert response.status_code == 200
        assert response.json()["visibility"] == "private"

    def test_update_visibility_friends_only(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/visibility"
            f"?visibility=friends_only&user_id={setup_db['user_id']}"
        )
        assert response.status_code == 200
        assert response.json()["visibility"] == "friends_only"

    def test_update_visibility_unlisted(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/visibility"
            f"?visibility=unlisted&user_id={setup_db['user_id']}"
        )
        assert response.status_code == 200
        assert response.json()["visibility"] == "unlisted"

    def test_update_visibility_invalid(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/visibility"
            f"?visibility=invalid&user_id={setup_db['user_id']}"
        )
        assert response.status_code == 400

    def test_update_visibility_not_creator(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/visibility"
            f"?visibility=public&user_id=999999"
        )
        assert response.status_code == 403

    def test_update_visibility_not_found(self, setup_db):
        response = client.put(
            f"/api/locations/999999/visibility"
            f"?visibility=public&user_id={setup_db['user_id']}"
        )
        assert response.status_code == 404


class TestModerationManagement:
    def test_approve_location(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/moderation"
            f"?state=approved"
        )
        assert response.status_code == 200
        assert response.json()["moderation_state"] == "approved"

    def test_reject_location(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/moderation"
            f"?state=rejected&notes=Spam+content"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["moderation_state"] == "rejected"

    def test_restrict_location(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/moderation"
            f"?state=restricted"
        )
        assert response.status_code == 200
        assert response.json()["moderation_state"] == "restricted"

    def test_moderation_invalid_state(self, setup_db):
        response = client.put(
            f"/api/locations/{setup_db['location_id']}/moderation"
            f"?state=invalid"
        )
        assert response.status_code == 400

    def test_moderation_not_found(self, setup_db):
        response = client.put(
            f"/api/locations/999999/moderation"
            f"?state=approved"
        )
        assert response.status_code == 404


class TestModeratedList:
    def test_list_pending(self, setup_db):
        response = client.get("/api/locations/moderated/list?state=pending")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_approved(self, setup_db):
        response = client.get("/api/locations/moderated/list?state=approved")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
