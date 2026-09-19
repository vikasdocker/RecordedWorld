"""Tests for Phase 11: Location Discovery — category filters, search, creator info, thumbnails."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base
from app.core.geospatial import WGS84Coordinate
from app.core.spatial_index import compute_grid_cell_id
from app.models.location import Location
from app.models.user import User
from app.models.category import Category


# Use the same DB as other tests (module-scoped fixtures share state)
from app.core.database import engine, SessionLocal

DEFAULT_CELL_SIZE = 100.0


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def discovery_user_ids():
    """Create test users for discovery tests."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ids = []
        for i in range(3):
            username = f"disc_user_{i}"
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                ids.append(existing.id)
            else:
                user = User(
                    username=username,
                    email=f"disc_{i}@test.com",
                    password_hash="salt:hash",
                    display_name=f"Discovery User {i}",
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
def discovery_locations(discovery_user_ids):
    """Create test locations with categories."""
    db = SessionLocal()
    try:
        # Create categories
        cats = {}
        for name, slug, icon in [("Park", "park", "🌳"), ("Museum", "museum", "🏛️"), ("Landmark", "landmark", "📍")]:
            existing = db.query(Category).filter(Category.slug == slug).first()
            if existing:
                cats[slug] = existing
            else:
                cat = Category(name=name, slug=slug, icon=icon)
                db.add(cat)
                db.commit()
                db.refresh(cat)
                cats[slug] = cat

        # Create locations
        locations_data = [
            ("Central Park", "A beautiful park", 40.785, -73.968, "park", discovery_user_ids[0]),
            ("Met Museum", "Art museum", 40.779, -73.963, "museum", discovery_user_ids[1]),
            ("Statue of Liberty", "Iconic landmark", 40.689, -74.044, "landmark", discovery_user_ids[0]),
            ("Hidden Park", "Friends only park", 40.780, -73.970, "park", discovery_user_ids[2]),
        ]

        loc_ids = []
        for title, desc, lat, lon, cat_slug, creator_id in locations_data:
            existing = db.query(Location).filter(Location.title == title).first()
            if existing:
                # Update grid_cell_id in case it was set incorrectly before
                existing.grid_cell_id = compute_grid_cell_id(
                    WGS84Coordinate(lat, lon, 0.0), DEFAULT_CELL_SIZE
                )
                existing.moderation_state = "approved"
                existing.visibility = "friends_only" if "Friends" in title else "public"
                db.commit()
                loc_ids.append(existing.id)
                continue
            loc = Location(
                creator_id=creator_id,
                title=title,
                description=desc,
                latitude=lat,
                longitude=lon,
                moderation_state="approved",
                visibility="friends_only" if "Friends" in title else "public",
                grid_cell_id=compute_grid_cell_id(
                    WGS84Coordinate(lat, lon, 0.0),
                    DEFAULT_CELL_SIZE,
                ),
            )
            loc.categories.append(cats[cat_slug])
            db.add(loc)
            db.commit()
            db.refresh(loc)
            loc_ids.append(loc.id)

        return loc_ids
    finally:
        db.close()


class TestCategoryFilter:
    def test_nearby_filter_by_category(self, client, discovery_locations):
        """Filter nearby locations by category slug."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
                "category": "museum",
            },
        )
        assert response.status_code == 200
        results = response.json()
        assert all("museum" in [c["slug"] for c in r["categories"]] for r in results)
        assert any(r["title"] == "Met Museum" for r in results)

    def test_nearby_filter_by_nonexistent_category(self, client, discovery_locations):
        """Filtering by non-existent category returns empty."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
                "category": "nonexistent",
            },
        )
        assert response.status_code == 200
        assert len(response.json()) == 0


class TestTextSearch:
    def test_nearby_search_by_title(self, client, discovery_locations):
        """Search nearby locations by title keyword."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
                "search": "Park",
            },
        )
        assert response.status_code == 200
        results = response.json()
        assert any(r["title"] == "Central Park" for r in results)

    def test_nearby_search_by_description(self, client, discovery_locations):
        """Search matches description text."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
                "search": "art",
            },
        )
        assert response.status_code == 200
        results = response.json()
        assert any(r["title"] == "Met Museum" for r in results)

    def test_nearby_search_no_results(self, client, discovery_locations):
        """Search with no matches returns empty."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
                "search": "zzzznonexistent",
            },
        )
        assert response.status_code == 200
        assert len(response.json()) == 0


class TestCreatorInfo:
    def test_nearby_includes_creator_name(self, client, discovery_locations):
        """Nearby results include creator display name."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
            },
        )
        assert response.status_code == 200
        results = response.json()
        for r in results:
            assert "creator_name" in r
            assert r["creator_name"] is not None

    def test_nearby_filter_by_creator(self, client, discovery_user_ids, discovery_locations):
        """Filter nearby by creator_id."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
                "creator_id": discovery_user_ids[0],
            },
        )
        assert response.status_code == 200
        results = response.json()
        assert all(r["creator_id"] == discovery_user_ids[0] for r in results)


class TestCategoryList:
    def test_list_categories(self, client, discovery_locations):
        """GET /api/locations/categories/list returns all categories."""
        response = client.get("/api/locations/categories/list")
        assert response.status_code == 200
        cats = response.json()
        assert len(cats) >= 3
        slugs = [c["slug"] for c in cats]
        assert "park" in slugs
        assert "museum" in slugs
        assert "landmark" in slugs

    def test_category_has_icon(self, client, discovery_locations):
        """Categories include icon field."""
        response = client.get("/api/locations/categories/list")
        assert response.status_code == 200
        for cat in response.json():
            assert "icon" in cat


class TestThumbnailEndpoint:
    def test_thumbnail_404_for_no_thumbnail(self, client, discovery_locations):
        """Thumbnail endpoint returns 404 when no thumbnail_id."""
        response = client.get(f"/api/locations/{discovery_locations[0]}/thumbnail")
        assert response.status_code == 404

    def test_thumbnail_404_for_nonexistent_location(self, client):
        """Thumbnail endpoint returns 404 for nonexistent location."""
        response = client.get("/api/locations/99999/thumbnail")
        assert response.status_code == 404


class TestCombinedFilters:
    def test_category_and_search_combined(self, client, discovery_locations):
        """Category + text search filters are combined with AND."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
                "category": "park",
                "search": "Central",
            },
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["title"] == "Central Park"

    def test_category_search_no_match(self, client, discovery_locations):
        """Category + search with no overlap returns empty."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
                "category": "museum",
                "search": "park",
            },
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_categories_in_nearby_response(self, client, discovery_locations):
        """Nearby results include categories list."""
        response = client.get(
            "/api/locations/nearby",
            params={
                "latitude": 40.780,
                "longitude": -73.965,
                "radius_meters": 5000,
            },
        )
        assert response.status_code == 200
        for r in response.json():
            assert "categories" in r
            assert isinstance(r["categories"], list)
