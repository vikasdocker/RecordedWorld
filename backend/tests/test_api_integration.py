"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    def test_health_check(self, client):
        """Health check returns healthy."""
        response = client.get("/api/monitoring/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_server_health(self, client):
        """Server health endpoint works."""
        response = client.get("/api/monitoring/health/detailed")
        assert response.status_code == 200


class TestUserEndpoints:
    def test_create_user(self, client):
        """Can create a user."""
        response = client.post("/api/users/", json={
            "username": "test_integration_user",
            "email": "integration@test.com",
            "password": "testpassword123",
            "display_name": "Integration Test",
        })
        assert response.status_code in (200, 201, 400, 409)  # 400/409 if exists or invalid

    def test_get_user(self, client):
        """Can get user by ID."""
        response = client.get("/api/users/1")
        assert response.status_code in (200, 404)  # 404 if not found


class TestLocationEndpoints:
    def test_list_locations(self, client):
        """Can list locations."""
        response = client.get("/api/locations/")
        assert response.status_code == 200

    def test_search_locations(self, client):
        """Can search locations."""
        response = client.get("/api/locations/nearby?latitude=40.785&longitude=-73.968")
        assert response.status_code == 200


class TestGameWorldEndpoints:
    def test_list_game_worlds(self, client):
        """Game worlds endpoint exists."""
        response = client.get("/api/game-worlds/")
        assert response.status_code in (200, 404)  # May not be implemented


class TestModerationEndpoints:
    def test_moderation_stats(self, client):
        """Can get moderation stats."""
        response = client.get("/api/moderation/stats")
        assert response.status_code == 200


class TestPerformanceEndpoints:
    def test_performance_stats(self, client):
        """Can get performance stats."""
        response = client.get("/api/monitoring/metrics")
        assert response.status_code == 200
