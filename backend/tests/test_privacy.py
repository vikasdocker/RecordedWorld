"""Tests for Phase 16: Player Privacy + Safety — deletion, reporting, moderation, restrictions."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.location import Location
from app.core.geospatial import WGS84Coordinate
from app.core.spatial_index import compute_grid_cell_id

DEFAULT_CELL_SIZE = 100.0


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def privacy_user_ids():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ids = []
        for i in range(3):
            username = f"privacy_user_{i}"
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                ids.append(existing.id)
            else:
                user = User(
                    username=username,
                    email=f"privacy_{i}@test.com",
                    password_hash="salt:hash",
                    display_name=f"Privacy User {i}",
                    location_sharing=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                ids.append(user.id)
        return ids
    finally:
        db.close()


@pytest.fixture(scope="module")
def privacy_locations(privacy_user_ids):
    db = SessionLocal()
    try:
        locs = [
            ("Privacy Test Loc A", 40.785, -73.968, privacy_user_ids[0], "approved", "public"),
            ("Privacy Test Loc B", 40.779, -73.963, privacy_user_ids[1], "pending", "public"),
            ("Privacy Test Loc C", 40.790, -73.970, privacy_user_ids[2], "approved", "friends_only"),
        ]
        loc_ids = []
        for title, lat, lon, creator_id, mod_state, vis in locs:
            existing = db.query(Location).filter(Location.title == title).first()
            if existing:
                existing.grid_cell_id = compute_grid_cell_id(
                    WGS84Coordinate(lat, lon, 0.0), DEFAULT_CELL_SIZE
                )
                existing.moderation_state = mod_state
                existing.visibility = vis
                db.commit()
                loc_ids.append(existing.id)
                continue
            loc = Location(
                creator_id=creator_id,
                title=title,
                latitude=lat,
                longitude=lon,
                moderation_state=mod_state,
                visibility=vis,
                grid_cell_id=compute_grid_cell_id(
                    WGS84Coordinate(lat, lon, 0.0), DEFAULT_CELL_SIZE
                ),
            )
            db.add(loc)
            db.commit()
            db.refresh(loc)
            loc_ids.append(loc.id)
        return loc_ids
    finally:
        db.close()


class TestSoftDelete:
    def test_creator_can_soft_delete(self, client, privacy_locations, privacy_user_ids):
        """Creator can soft-delete their own location."""
        resp = client.delete(
            f"/api/privacy/locations/{privacy_locations[0]}",
            params={"user_id": privacy_user_ids[0]},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify soft-deleted state
        db = SessionLocal()
        try:
            loc = db.query(Location).filter(Location.id == privacy_locations[0]).first()
            assert loc.moderation_state == "deleted"
            assert loc.visibility == "private"
        finally:
            db.close()

    def test_non_creator_cannot_delete(self, client, privacy_locations):
        """Non-creator cannot delete someone else's location."""
        resp = client.delete(
            f"/api/privacy/locations/{privacy_locations[2]}",
            params={"user_id": 999},
        )
        assert resp.status_code == 403

    def test_restore_deleted_location(self, client, privacy_locations, privacy_user_ids):
        """Creator can restore a soft-deleted location."""
        resp = client.post(
            f"/api/privacy/locations/{privacy_locations[0]}/restore",
            params={"user_id": privacy_user_ids[0]},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "restored"

        # Verify restored state
        db = SessionLocal()
        try:
            loc = db.query(Location).filter(Location.id == privacy_locations[0]).first()
            assert loc.moderation_state == "pending"
            assert loc.visibility == "public"
        finally:
            db.close()

    def test_cannot_restore_non_deleted(self, client, privacy_locations, privacy_user_ids):
        """Cannot restore a location that isn't deleted."""
        resp = client.post(
            f"/api/privacy/locations/{privacy_locations[2]}/restore",
            params={"user_id": privacy_user_ids[2]},
        )
        assert resp.status_code == 400


class TestReporting:
    def test_create_report(self, client):
        """Can create a report for a location."""
        resp = client.post(
            "/api/privacy/reports",
            json={
                "target_type": "location",
                "target_id": 999,
                "reason": "inappropriate",
                "description": "Test report",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_type"] == "location"
        assert data["reason"] == "inappropriate"
        assert data["status"] == "pending"

    def test_create_player_report(self, client):
        """Can create a report for a player."""
        resp = client.post(
            "/api/privacy/reports",
            json={
                "target_type": "player",
                "target_id": 42,
                "reason": "harassment",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["target_type"] == "player"

    def test_invalid_report_reason(self, client):
        """Invalid report reason is rejected."""
        resp = client.post(
            "/api/privacy/reports",
            json={
                "target_type": "location",
                "target_id": 1,
                "reason": "invalid_reason",
            },
        )
        assert resp.status_code == 400

    def test_list_reports(self, client):
        """Can list reports."""
        resp = client.get("/api/privacy/reports")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_reports_by_status(self, client):
        """Can filter reports by status."""
        resp = client.get("/api/privacy/reports", params={"status": "pending"})
        assert resp.status_code == 200
        for r in resp.json():
            assert r["status"] == "pending"

    def test_update_report_status(self, client):
        """Can update a report's status."""
        # Create a report first
        resp = client.post(
            "/api/privacy/reports",
            json={
                "target_type": "location",
                "target_id": 100,
                "reason": "spam",
            },
        )
        report_id = resp.json()["id"]

        resp = client.patch(
            f"/api/privacy/reports/{report_id}",
            params={"status": "resolved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_update_nonexistent_report(self, client):
        """Updating a nonexistent report returns 404."""
        resp = client.patch("/api/privacy/reports/99999", params={"status": "dismissed"})
        assert resp.status_code == 404


class TestModeration:
    def test_moderation_queue(self, client, privacy_locations):
        """Can get the moderation queue."""
        resp = client.get("/api/privacy/moderation/queue")
        assert resp.status_code == 200
        queue = resp.json()
        assert isinstance(queue, list)
        # At least one pending location
        pending_ids = [loc["id"] for loc in queue]
        assert privacy_locations[1] in pending_ids  # Loc B was pending

    def test_approve_location(self, client, privacy_locations):
        """Can approve a pending location."""
        resp = client.post(
            f"/api/privacy/moderation/locations/{privacy_locations[1]}/approve",
            params={"notes": "Looks good"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_reject_location(self, client, privacy_locations, privacy_user_ids):
        """Can reject a location."""
        resp = client.post(
            f"/api/privacy/moderation/locations/{privacy_locations[2]}/reject",
            params={"notes": "Policy violation"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        # Verify rejected state
        db = SessionLocal()
        try:
            loc = db.query(Location).filter(Location.id == privacy_locations[2]).first()
            assert loc.moderation_state == "rejected"
            assert loc.visibility == "private"
        finally:
            db.close()

    def test_approve_nonexistent_location(self, client):
        """Approving a nonexistent location returns 404."""
        resp = client.post("/api/privacy/moderation/locations/99999/approve")
        assert resp.status_code == 404


class TestSensitiveZones:
    def test_check_sensitive_zone_inside(self, client):
        """Check detects location inside a sensitive zone."""
        resp = client.get(
            "/api/privacy/sensitive-zones/check",
            params={"latitude": 37.235, "longitude": -115.810},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["restricted"] is True
        assert data["zone_name"] == "Area 51"

    def test_check_sensitive_zone_outside(self, client):
        """Check passes for location outside any sensitive zone."""
        resp = client.get(
            "/api/privacy/sensitive-zones/check",
            params={"latitude": 40.785, "longitude": -73.968},
        )
        assert resp.status_code == 200
        assert resp.json()["restricted"] is False

    def test_list_sensitive_zones(self, client):
        """Can list all sensitive zones."""
        resp = client.get("/api/privacy/sensitive-zones/list")
        assert resp.status_code == 200
        zones = resp.json()
        assert isinstance(zones, list)
        assert len(zones) >= 3
        zone_names = [z["name"] for z in zones]
        assert "Area 51" in zone_names


class TestLocationsEndpointPrivacy:
    def test_delete_with_user_id(self, client, privacy_locations, privacy_user_ids):
        """Locations endpoint supports soft delete with user_id."""
        resp = client.delete(
            f"/api/locations/{privacy_locations[0]}",
            params={"user_id": privacy_user_ids[0]},
        )
        assert resp.status_code == 200

    def test_delete_without_user_id(self, client):
        """Locations endpoint supports hard delete without user_id (legacy)."""
        # Create a fresh location to delete
        db = SessionLocal()
        try:
            loc = Location(
                creator_id=1,
                title="Delete Me Hard",
                latitude=40.785,
                longitude=-73.968,
                moderation_state="approved",
                visibility="public",
                grid_cell_id=compute_grid_cell_id(
                    WGS84Coordinate(40.785, -73.968, 0.0), DEFAULT_CELL_SIZE
                ),
            )
            db.add(loc)
            db.commit()
            db.refresh(loc)
            loc_id = loc.id
        finally:
            db.close()

        resp = client.delete(f"/api/locations/{loc_id}")
        assert resp.status_code == 200
