import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Recorded World API"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_monitoring_health(client):
    response = client.get("/api/monitoring/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_user(client):
    uid = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/users/",
        json={
            "username": f"testuser_{uid}",
            "email": f"test_{uid}@example.com",
            "password": "securepass123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == f"testuser_{uid}"
    assert "id" in data


def test_get_user(client):
    response = client.get("/api/users/1")
    assert response.status_code == 200


def test_list_captures(client):
    response = client.get("/api/captures/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_metrics(client):
    response = client.get("/api/monitoring/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "counters" in data
    assert "gauges" in data


def test_alerts(client):
    response = client.get("/api/monitoring/alerts")
    assert response.status_code == 200
    assert "alerts" in response.json()


def test_create_alert(client):
    response = client.post(
        "/api/monitoring/alerts",
        json={"level": "info", "message": "Test alert"},
    )
    assert response.status_code == 200


def test_testing_summary(client):
    response = client.get("/api/testing/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_feedback" in data


# --- Location API tests ---

def test_create_location(client):
    response = client.post(
        "/api/locations/",
        json={
            "title": "Test Location",
            "description": "A test location",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 10.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Location"
    assert data["latitude"] == 40.7128
    assert "id" in data


def test_get_location(client):
    response = client.get("/api/locations/1")
    assert response.status_code == 200


def test_list_locations(client):
    response = client.get("/api/locations/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_find_nearby_locations(client):
    # Create user with location_sharing enabled for nearby search
    from app.core.database import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, username="nearby_test_user", email="nearby@test.com", password_hash="x:y")
        db.add(user)
    user.location_sharing = True
    db.commit()
    db.close()

    # Create a few locations near NYC (approved so they appear in nearby search)
    for i in range(3):
        resp = client.post(
            "/api/locations/",
            json={
                "title": f"NYC Spot {i}",
                "latitude": 40.7128 + i * 0.001,
                "longitude": -74.0060 + i * 0.001,
            },
        )
        loc_id = resp.json()["id"]
        # Approve so they show up in nearby results
        db = SessionLocal()
        from app.models.location import Location
        db.query(Location).filter(Location.id == loc_id).update({"moderation_state": "approved"})
        db.commit()
        db.close()

    # Search near the first one
    response = client.get(
        "/api/locations/nearby",
        params={"latitude": 40.7128, "longitude": -74.0060, "radius_meters": 500},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert "distance_meters" in results[0]


def test_delete_location(client):
    response = client.delete("/api/locations/1")
    assert response.status_code == 200
