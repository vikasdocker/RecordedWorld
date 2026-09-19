"""Tests for Phase 17: Content Moderation — policy, audit log, restrict, bulk."""

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
def mod_user_ids():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ids = []
        for i in range(2):
            username = f"mod_user_{i}"
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                ids.append(existing.id)
            else:
                user = User(
                    username=username,
                    email=f"mod_{i}@test.com",
                    password_hash="salt:hash",
                    display_name=f"Mod User {i}",
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
def mod_locations(mod_user_ids):
    db = SessionLocal()
    try:
        locs = [
            ("Mod Test Loc A", 40.785, -73.968, mod_user_ids[0], "pending"),
            ("Mod Test Loc B", 40.779, -73.963, mod_user_ids[1], "approved"),
        ]
        loc_ids = []
        for title, lat, lon, creator_id, mod_state in locs:
            existing = db.query(Location).filter(Location.title == title).first()
            if existing:
                existing.grid_cell_id = compute_grid_cell_id(
                    WGS84Coordinate(lat, lon, 0.0), DEFAULT_CELL_SIZE
                )
                existing.moderation_state = mod_state
                db.commit()
                loc_ids.append(existing.id)
                continue
            loc = Location(
                creator_id=creator_id,
                title=title,
                latitude=lat,
                longitude=lon,
                moderation_state=mod_state,
                visibility="public",
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


class TestContentAnalysis:
    def test_clean_content_passes(self, client):
        """Clean content passes automated checks."""
        resp = client.post(
            "/api/moderation/analyze",
            params={"title": "Beautiful Park", "description": "A nice park for walking"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passes"] is True
        assert len(data["violations"]) == 0

    def test_blocked_word_in_title(self, client):
        """Content with blocked word fails."""
        resp = client.post(
            "/api/moderation/analyze",
            params={"title": "spam location", "description": "Some description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passes"] is False
        assert any("spam" in v for v in data["violations"])

    def test_blocked_word_in_description(self, client):
        """Blocked word in description fails."""
        resp = client.post(
            "/api/moderation/analyze",
            params={"title": "Normal Title", "description": "This is nsfw content"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passes"] is False

    def test_title_too_short(self, client):
        """Title that is too short fails."""
        resp = client.post(
            "/api/moderation/analyze",
            params={"title": "Hi"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passes"] is False
        assert any("too short" in v for v in data["violations"])

    def test_title_too_long(self, client):
        """Title that is too long fails."""
        resp = client.post(
            "/api/moderation/analyze",
            params={"title": "A" * 201},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passes"] is False
        assert any("too long" in v for v in data["violations"])

    def test_url_in_title(self, client):
        """URL in title is blocked."""
        resp = client.post(
            "/api/moderation/analyze",
            params={"title": "Visit http://bit.ly/abc123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passes"] is False

    def test_phone_number_in_description(self, client):
        """Phone number in description is blocked."""
        resp = client.post(
            "/api/moderation/analyze",
            params={
                "title": "Normal Title",
                "description": "Call me at 555-123-4567",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passes"] is False


class TestRestrictWorkflow:
    def test_restrict_location(self, client, mod_locations):
        """Can restrict a location (soft reject)."""
        resp = client.post(
            f"/api/moderation/locations/{mod_locations[0]}/restrict",
            params={"notes": "Needs review"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "restricted"

        # Verify state
        db = SessionLocal()
        try:
            loc = db.query(Location).filter(Location.id == mod_locations[0]).first()
            assert loc.moderation_state == "restricted"
            assert loc.visibility == "friends_only"
        finally:
            db.close()

    def test_restrict_already_restricted(self, client, mod_locations):
        """Cannot restrict an already restricted location."""
        resp = client.post(
            f"/api/moderation/locations/{mod_locations[0]}/restrict",
            params={"notes": "Already restricted"},
        )
        assert resp.status_code == 400


class TestBulkModeration:
    def test_bulk_approve(self, client, mod_locations):
        """Can bulk approve multiple locations."""
        resp = client.post(
            "/api/moderation/bulk",
            json={
                "location_ids": mod_locations,
                "action": "approve",
                "notes": "Bulk approved",
            },
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert all(r["status"] == "approve" for r in results)

    def test_bulk_reject(self, client, mod_locations):
        """Can bulk reject multiple locations."""
        resp = client.post(
            "/api/moderation/bulk",
            json={
                "location_ids": mod_locations,
                "action": "reject",
                "notes": "Bulk rejected",
            },
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert all(r["status"] == "reject" for r in results)

    def test_bulk_restrict(self, client, mod_locations):
        """Can bulk restrict multiple locations."""
        resp = client.post(
            "/api/moderation/bulk",
            json={
                "location_ids": mod_locations[:1],
                "action": "restrict",
            },
        )
        assert resp.status_code == 200

    def test_bulk_invalid_action(self, client, mod_locations):
        """Invalid bulk action is rejected."""
        resp = client.post(
            "/api/moderation/bulk",
            json={
                "location_ids": mod_locations[:1],
                "action": "invalid",
            },
        )
        assert resp.status_code == 400

    def test_bulk_nonexistent_location(self, client):
        """Bulk action on nonexistent location returns not_found."""
        resp = client.post(
            "/api/moderation/bulk",
            json={
                "location_ids": [99999],
                "action": "approve",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["results"][0]["status"] == "not_found"


class TestAuditLog:
    def test_audit_log_records_actions(self, client, mod_locations):
        """Moderation actions are recorded in the audit log."""
        # Approve a location
        client.post(
            f"/api/moderation/locations/{mod_locations[0]}/approve",
            params={"notes": "Test approve for audit"},
        )

        resp = client.get("/api/moderation/audit-log")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) > 0

        # Check that our action is logged
        loc_actions = [l for l in logs if l["location_id"] == mod_locations[0]]
        assert len(loc_actions) > 0
        assert any(l["action"] == "approve" for l in loc_actions)

    def test_filter_audit_log_by_location(self, client, mod_locations):
        """Can filter audit log by location ID."""
        resp = client.get(
            "/api/moderation/audit-log",
            params={"location_id": mod_locations[0]},
        )
        assert resp.status_code == 200
        for log in resp.json():
            assert log["location_id"] == mod_locations[0]

    def test_filter_audit_log_by_action(self, client):
        """Can filter audit log by action type."""
        resp = client.get(
            "/api/moderation/audit-log",
            params={"action": "approve"},
        )
        assert resp.status_code == 200
        for log in resp.json():
            assert log["action"] == "approve"


class TestModerationStats:
    def test_get_stats(self, client, mod_locations):
        """Can get moderation statistics."""
        resp = client.get("/api/moderation/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert isinstance(stats, dict)
        # Should have at least some states
        assert len(stats) > 0
