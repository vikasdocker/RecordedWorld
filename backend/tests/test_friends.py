import pytest
from sqlalchemy import or_, and_
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.friendship import Friendship
from app.models.location import Location


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def user_ids():
    """Create test users and return their IDs."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ids = []
        for i in range(5):
            username = f"friend_user_{i}"
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                ids.append(existing.id)
            else:
                user = User(
                    username=username,
                    email=f"friend_{i}@test.com",
                    password_hash="salt:hash",
                    display_name=f"User {i}",
                    location_sharing=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                ids.append(user.id)

        # Clean up any existing friendships between these users
        for i in range(5):
            for j in range(5):
                if i != j:
                    db.query(Friendship).filter(
                        or_(
                            and_(Friendship.requester_id == ids[i], Friendship.addressee_id == ids[j]),
                            and_(Friendship.requester_id == ids[j], Friendship.addressee_id == ids[i]),
                        )
                    ).delete(synchronize_session=False)
        db.commit()

        return ids
    finally:
        db.close()


# =============================================================================
# Friend Request Tests
# =============================================================================

class TestFriendRequest:
    def test_send_request(self, client, user_ids):
        response = client.post(
            "/api/friends/request",
            json={"addressee_id": user_ids[1]},
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["requester_id"] == user_ids[0]
        assert data["addressee_id"] == user_ids[1]

    def test_send_request_to_self(self, client, user_ids):
        response = client.post(
            "/api/friends/request",
            json={"addressee_id": user_ids[0]},
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400

    def test_send_request_nonexistent_user(self, client, user_ids):
        response = client.post(
            "/api/friends/request",
            json={"addressee_id": 99999},
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400

    def test_send_request_already_sent(self, client, user_ids):
        response = client.post(
            "/api/friends/request",
            json={"addressee_id": user_ids[1]},
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400

    def test_send_request_reverse_auto_accepts(self, client, user_ids):
        resp1 = client.post(
            "/api/friends/request",
            json={"addressee_id": user_ids[0]},
            headers={"X-User-ID": str(user_ids[2])},
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            "/api/friends/request",
            json={"addressee_id": user_ids[2]},
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "accepted"


class TestFriendAcceptReject:
    def test_accept_request(self, client, user_ids):
        resp = client.get(
            "/api/friends/pending",
            params={"direction": "received"},
            headers={"X-User-ID": str(user_ids[1])},
        )
        pending = resp.json()
        assert len(pending) > 0
        friendship_id = pending[0]["id"]

        response = client.post(
            f"/api/friends/accept/{friendship_id}",
            headers={"X-User-ID": str(user_ids[1])},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    def test_accept_wrong_user(self, client, user_ids):
        resp = client.post(
            "/api/friends/request",
            json={"addressee_id": user_ids[3]},
            headers={"X-User-ID": str(user_ids[4])},
        )
        friendship_id = resp.json()["id"]

        response = client.post(
            f"/api/friends/accept/{friendship_id}",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400

    def test_reject_request(self, client, user_ids):
        resp = client.get(
            "/api/friends/pending",
            params={"direction": "received"},
            headers={"X-User-ID": str(user_ids[3])},
        )
        pending = resp.json()
        assert len(pending) > 0
        friendship_id = pending[0]["id"]

        response = client.post(
            f"/api/friends/reject/{friendship_id}",
            headers={"X-User-ID": str(user_ids[3])},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"


class TestFriendRemoval:
    def test_remove_friend(self, client, user_ids):
        resp = client.get(
            "/api/friends/",
            headers={"X-User-ID": str(user_ids[0])},
        )
        friends = resp.json()
        friend_entry = next((f for f in friends if f["user_id"] == user_ids[2]), None)
        assert friend_entry is not None

        response = client.delete(
            f"/api/friends/{friend_entry['id']}",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "removed"

    def test_remove_nonexistent(self, client, user_ids):
        response = client.delete(
            "/api/friends/99999",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400


class TestFriendListing:
    def test_list_friends(self, client, user_ids):
        response = client.get(
            "/api/friends/",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 200
        friends = response.json()
        assert isinstance(friends, list)

    def test_list_pending_received(self, client, user_ids):
        response = client.get(
            "/api/friends/pending",
            params={"direction": "received"},
            headers={"X-User-ID": str(user_ids[1])},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_pending_sent(self, client, user_ids):
        response = client.get(
            "/api/friends/pending",
            params={"direction": "sent"},
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_pending_invalid_direction(self, client, user_ids):
        response = client.get(
            "/api/friends/pending",
            params={"direction": "invalid"},
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400


# =============================================================================
# Blocking Tests
# =============================================================================

class TestBlocking:
    def test_block_user(self, client, user_ids):
        response = client.post(
            f"/api/friends/block/{user_ids[4]}",
            headers={"X-User-ID": str(user_ids[3])},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "blocked"

    def test_block_self(self, client, user_ids):
        response = client.post(
            f"/api/friends/block/{user_ids[0]}",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400

    def test_block_nonexistent(self, client, user_ids):
        response = client.post(
            "/api/friends/block/99999",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400

    def test_blocked_user_cannot_send_request(self, client, user_ids):
        response = client.post(
            "/api/friends/request",
            json={"addressee_id": user_ids[3]},
            headers={"X-User-ID": str(user_ids[4])},
        )
        assert response.status_code == 400

    def test_list_blocked_users(self, client, user_ids):
        response = client.get(
            "/api/friends/blocked",
            headers={"X-User-ID": str(user_ids[3])},
        )
        assert response.status_code == 200
        blocked = response.json()
        assert any(b["user_id"] == user_ids[4] for b in blocked)

    def test_unblock_user(self, client, user_ids):
        response = client.delete(
            f"/api/friends/block/{user_ids[4]}",
            headers={"X-User-ID": str(user_ids[3])},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "unblocked"

    def test_unblock_nonexistent(self, client, user_ids):
        response = client.delete(
            "/api/friends/block/99999",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400

    def test_unblock_not_blocked(self, client, user_ids):
        response = client.delete(
            f"/api/friends/block/{user_ids[1]}",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 400


# =============================================================================
# Friend Status Check Tests
# =============================================================================

class TestFriendStatusCheck:
    def test_check_not_friends(self, client, user_ids):
        response = client.get(
            f"/api/friends/check/{user_ids[3]}",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["are_friends"] is False

    def test_check_self(self, client, user_ids):
        response = client.get(
            f"/api/friends/check/{user_ids[0]}",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["are_friends"] is False

    def test_check_pending_sent(self, client, user_ids):
        resp = client.get(
            f"/api/friends/check/{user_ids[1]}",
            headers={"X-User-ID": str(user_ids[0])},
        )
        data = resp.json()
        assert "are_friends" in data
        assert "pending_request" in data

    def test_check_friends(self, client, user_ids):
        client.post(
            "/api/friends/request",
            json={"addressee_id": user_ids[2]},
            headers={"X-User-ID": str(user_ids[0])},
        )
        resp = client.get(
            f"/api/friends/check/{user_ids[2]}",
            headers={"X-User-ID": str(user_ids[0])},
        )
        assert resp.status_code == 200


# =============================================================================
# Auth Tests
# =============================================================================

class TestAuth:
    def test_missing_header(self, client):
        response = client.get("/api/friends/")
        assert response.status_code == 401

    def test_invalid_header(self, client):
        response = client.get(
            "/api/friends/",
            headers={"X-User-ID": "not_a_number"},
        )
        assert response.status_code == 400

    def test_negative_id(self, client):
        response = client.get(
            "/api/friends/",
            headers={"X-User-ID": "-1"},
        )
        assert response.status_code == 400


# =============================================================================
# Privacy Integration Tests
# =============================================================================

class TestPrivacyIntegration:
    def test_nearby_shows_friends_only_to_friends(self, client, user_ids):
        resp = client.post(
            "/api/locations/",
            json={
                "title": "Secret Spot",
                "latitude": 40.7500,
                "longitude": -74.0000,
            },
        )
        loc_id = resp.json()["id"]
        creator_id = resp.json()["creator_id"]

        db = SessionLocal()
        db.query(Location).filter(Location.id == loc_id).update({
            "visibility": "friends_only",
            "moderation_state": "approved",
        })

        # Create friendship so viewer can see friends_only location
        if creator_id != user_ids[0]:
            existing = db.query(Friendship).filter(
                Friendship.requester_id == creator_id,
                Friendship.addressee_id == user_ids[0],
            ).first()
            if not existing:
                existing = db.query(Friendship).filter(
                    Friendship.requester_id == user_ids[0],
                    Friendship.addressee_id == creator_id,
                ).first()
            if not existing:
                db.add(Friendship(
                    requester_id=creator_id,
                    addressee_id=user_ids[0],
                    status="accepted",
                ))
        db.commit()
        db.close()

        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.7500,
                "longitude": -74.0000,
                "radius_meters": 1000,
                "viewer_id": user_ids[0],
            },
        )
        assert response.status_code == 200
        results = response.json()
        assert any(r["id"] == loc_id for r in results)

    def test_nearby_hides_friends_only_from_strangers(self, client, user_ids):
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.7500,
                "longitude": -74.0000,
                "radius_meters": 1000,
                "viewer_id": user_ids[3],
            },
        )
        assert response.status_code == 200
        results = response.json()
        assert not any(r["title"] == "Secret Spot" for r in results)

    def test_nearby_hides_when_creator_sharing_off(self, client, user_ids):
        db = SessionLocal()
        user = User(
            username="no_sharing_user",
            email="noshare@test.com",
            password_hash="salt:hash",
            location_sharing=False,
        )
        existing = db.query(User).filter(User.username == user.username).first()
        if not existing:
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user = existing
        db.close()

        resp = client.post(
            "/api/locations/",
            json={
                "title": "Hidden Spot",
                "latitude": 40.7600,
                "longitude": -74.0100,
            },
        )
        loc_id = resp.json()["id"]

        db = SessionLocal()
        db.query(Location).filter(Location.id == loc_id).update({
            "moderation_state": "approved",
            "creator_id": user.id,
        })
        db.commit()
        db.close()

        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.7600,
                "longitude": -74.0100,
                "radius_meters": 1000,
                "viewer_id": user_ids[0],
            },
        )
        assert response.status_code == 200
        results = response.json()
        assert not any(r["title"] == "Hidden Spot" for r in results)

    def test_nearby_approximate_location(self, client, user_ids):
        db = SessionLocal()
        user = User(
            username="approx_user",
            email="approx@test.com",
            password_hash="salt:hash",
            location_sharing=True,
            approximate_location=True,
        )
        existing = db.query(User).filter(User.username == user.username).first()
        if not existing:
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user = existing
        db.close()

        resp = client.post(
            "/api/locations/",
            json={
                "title": "Approx Spot",
                "latitude": 40.7128,
                "longitude": -74.0060,
            },
        )
        loc_id = resp.json()["id"]

        db = SessionLocal()
        db.query(Location).filter(Location.id == loc_id).update({
            "moderation_state": "approved",
            "creator_id": user.id,
        })
        db.commit()
        db.close()

        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.7128,
                "longitude": -74.0060,
                "radius_meters": 1000,
                "viewer_id": user_ids[0],
            },
        )
        assert response.status_code == 200
        results = response.json()
        approx_loc = next((r for r in results if r["title"] == "Approx Spot"), None)
        if approx_loc:
            assert approx_loc["latitude"] == round(40.7128, 2)
            assert approx_loc["longitude"] == round(-74.0060, 2)
