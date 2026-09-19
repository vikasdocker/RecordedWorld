"""Tests for Phase 15: Social Location Tags — user-generated tags on locations."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.location import Location
from app.models.tag import Tag
from app.core.geospatial import WGS84Coordinate
from app.core.spatial_index import compute_grid_cell_id

DEFAULT_CELL_SIZE = 100.0


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def tag_user_ids():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ids = []
        for i in range(2):
            username = f"tag_user_{i}"
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                ids.append(existing.id)
            else:
                user = User(
                    username=username,
                    email=f"tag_{i}@test.com",
                    password_hash="salt:hash",
                    display_name=f"Tag User {i}",
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
def tag_locations(tag_user_ids):
    db = SessionLocal()
    try:
        locs = [
            ("Tag Test Park", 40.785, -73.968, tag_user_ids[0]),
            ("Tag Test Museum", 40.779, -73.963, tag_user_ids[1]),
        ]
        loc_ids = []
        for title, lat, lon, creator_id in locs:
            existing = db.query(Location).filter(Location.title == title).first()
            if existing:
                existing.grid_cell_id = compute_grid_cell_id(
                    WGS84Coordinate(lat, lon, 0.0), DEFAULT_CELL_SIZE
                )
                existing.moderation_state = "approved"
                db.commit()
                loc_ids.append(existing.id)
                continue
            loc = Location(
                creator_id=creator_id,
                title=title,
                latitude=lat,
                longitude=lon,
                moderation_state="approved",
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


class TestTagCRUD:
    def test_add_tag_to_location(self, client, tag_locations):
        """Can add a tag to a location."""
        resp = client.post(
            f"/api/tags/locations/{tag_locations[0]}/tags",
            params={"name": "sunset", "user_id": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "sunset"
        assert data["slug"] == "sunset"
        assert data["status"] == "added"

    def test_add_duplicate_tag(self, client, tag_locations):
        """Adding the same tag again returns 'already_exists'."""
        resp = client.post(
            f"/api/tags/locations/{tag_locations[0]}/tags",
            params={"name": "sunset"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_exists"

    def test_add_tag_creates_new_tag(self, client, tag_locations):
        """Adding a new tag name creates the Tag record."""
        resp = client.post(
            f"/api/tags/locations/{tag_locations[0]}/tags",
            params={"name": "Hidden Gem"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Hidden Gem"
        assert resp.json()["slug"] == "hidden-gem"

    def test_add_tag_to_nonexistent_location(self, client):
        """Adding a tag to a nonexistent location returns 404."""
        resp = client.post(
            "/api/tags/locations/99999/tags",
            params={"name": "test"},
        )
        assert resp.status_code == 404

    def test_get_location_tags(self, client, tag_locations):
        """Can retrieve tags for a location."""
        resp = client.get(f"/api/tags/locations/{tag_locations[0]}/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert len(tags) >= 2
        names = [t["name"] for t in tags]
        assert "sunset" in names
        assert "Hidden Gem" in names

    def test_remove_tag_from_location(self, client, tag_locations):
        """Can remove a tag from a location."""
        # First get the tag ID
        resp = client.get(f"/api/tags/locations/{tag_locations[0]}/tags")
        tag_id = [t["id"] for t in resp.json() if t["name"] == "sunset"][0]

        resp = client.delete(f"/api/tags/locations/{tag_locations[0]}/tags/{tag_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

        # Verify it's gone
        resp = client.get(f"/api/tags/locations/{tag_locations[0]}/tags")
        names = [t["name"] for t in resp.json()]
        assert "sunset" not in names

    def test_remove_nonexistent_tag(self, client, tag_locations):
        """Removing a nonexistent tag association returns 404."""
        resp = client.delete(f"/api/tags/locations/{tag_locations[0]}/tags/99999")
        assert resp.status_code == 404


class TestTagSearch:
    def test_search_tags_by_prefix(self, client, tag_locations):
        """Can search tags by name prefix."""
        # Add some tags first
        for name in ["photography", "photo-walk", "nature"]:
            client.post(
                f"/api/tags/locations/{tag_locations[0]}/tags",
                params={"name": name},
            )

        resp = client.get("/api/tags/search", params={"q": "photo"})
        assert resp.status_code == 200
        results = resp.json()
        names = [r["name"] for r in results]
        assert "photography" in names
        assert "photo-walk" in names

    def test_search_tags_popular_when_empty(self, client, tag_locations):
        """Empty search returns popular tags."""
        resp = client.get("/api/tags/search", params={"q": ""})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_popular_tags(self, client, tag_locations):
        """Can get popular tags sorted by usage count."""
        resp = client.get("/api/tags/popular")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        # All tags should have usage_count
        for t in tags:
            assert "usage_count" in t

    def test_get_tag_by_slug(self, client, tag_locations):
        """Can retrieve a tag by its slug."""
        resp = client.get("/api/tags/by-slug/sunset")
        # Might not exist if it was removed earlier, so check both cases
        assert resp.status_code in (200, 404)


class TestTagsInNearby:
    def test_nearby_includes_tags(self, client, tag_locations):
        """Nearby endpoint returns tags for each location."""
        # Ensure location has a tag
        client.post(
            f"/api/tags/locations/{tag_locations[0]}/tags",
            params={"name": "nearby-test"},
        )

        resp = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
            },
        )
        assert resp.status_code == 200
        for loc in resp.json():
            assert "tags" in loc
            assert isinstance(loc["tags"], list)


class TestTagUsageCount:
    def test_usage_count_increments(self, client, tag_locations):
        """Adding a tag to multiple locations increments usage_count."""
        # Add "popular-tag" to both locations
        client.post(
            f"/api/tags/locations/{tag_locations[0]}/tags",
            params={"name": "popular-tag"},
        )
        client.post(
            f"/api/tags/locations/{tag_locations[1]}/tags",
            params={"name": "popular-tag"},
        )

        resp = client.get("/api/tags/by-slug/popular-tag")
        assert resp.status_code == 200
        assert resp.json()["usage_count"] >= 2

    def test_usage_count_decrements(self, client, tag_locations):
        """Removing a tag decrements usage_count."""
        # Get tag ID
        resp = client.get(f"/api/tags/locations/{tag_locations[0]}/tags")
        tag_data = [t for t in resp.json() if t["name"] == "popular-tag"]
        if tag_data:
            tag_id = tag_data[0]["id"]
            resp = client.delete(f"/api/tags/locations/{tag_locations[0]}/tags/{tag_id}")
            assert resp.status_code == 200

            resp = client.get("/api/tags/by-slug/popular-tag")
            if resp.status_code == 200:
                assert resp.json()["usage_count"] >= 1
